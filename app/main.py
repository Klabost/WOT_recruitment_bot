"""BOT that queries wargames clans. and if members apear to have left
   a clan then their username will be posted in a discord channel"""

import signal
import logging
import os
import sys
import argparse

import asyncio
import aiohttp
from aiolimiter import AsyncLimiter

from discord_logging.handler import DiscordHandler
from discord import Webhook

from sane_argument_parser import SaneArgumentParser
from models import Clan

from utils.const import CLAN_DETAILS_URL, MEMBER_DETAILS_URL, LOGGER_NAME, NO_OF_CONSUMERS, MAX_NUM_OF_IDS
from utils.storage import read_file, store_file
from utils.fetcher import fetcher
from utils.parser import parse_response

logger = logging.getLogger(LOGGER_NAME)

console_handler = logging.StreamHandler(sys.stdout) 
console_foramt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s",
                                   datefmt='%Y/%m/%d %H:%M:%S')
console_handler.setFormatter(console_foramt)
logger.addHandler(console_handler)

async def get_members(app_id: str,
                      clans: dict[Clan],
                      update_interval: int,
                      queue: asyncio.Queue) -> None:
    """produce requests for member data"""
    while True:
        logger.info("Fetching Member Data")
        # group clan ids in single request to reduce traffic
        clan_id_list = list(clans.keys())
        n = MAX_NUM_OF_IDS
        clan_groups = [clan_id_list[i:i+n] for i in range(0, len(clan_id_list),n)]
        for group in clan_groups:
            clan_ids = ",".join(group)
            logger.debug("Fetching Members Data for clans: %s", clan_ids)
            params = {
                'application_id': app_id,
                'clan_id': clan_ids,
                "fields": "name,clan_id,tag,is_clan_disbanded,old_name,members_count,description,members"
            }
            await queue.put((CLAN_DETAILS_URL, params))
        if update_interval == 0:
            break
        await asyncio.sleep(update_interval)

async def recruit_members(queue: asyncio.Queue, url: str) -> None:
    """Send recruit data to discord channel.
    Webhooks are rate limited to 30 message per minute
    according to stackoverflow"""
    limiter = AsyncLimiter(30, 60)
    while True:
        reason, member, clan = await queue.get()
        try:
            if url:
                logger.info("Sending %s information to discord", member.account_name)
                async with limiter:
                    async with aiohttp.ClientSession() as session:
                        webhook = Webhook.from_url(url, session=session)
                        stat_url = f"{MEMBER_DETAILS_URL}/{member.account_name}-{member.account_id}/"
                        message = (f"Member found. Name: {member.account_name}, "
                                f"ID: {member.account_id}, stats: {stat_url} ",
                                f"Reason: {reason}",
                                f"From Clan: {clan.name} {clan.clan_id}")
                        await webhook.send(message, username='WOT_BOT')
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,
                aiohttp.ClientConnectorError ) as se:
            logger.error("Error sending Data to discord recruit channel. Error: %s",se.message)
        finally:
            queue.task_done()

async def shutdown(sig: signal.signal, loop: asyncio.BaseEventLoop) -> None:
    """Cleanup tasks tied to the service's shutdown."""
    logger.info("Received exit signal %s ...", sig.name)
    tasks = [t for t in asyncio.all_tasks() if t is not
             asyncio.current_task()]

    for task in tasks:
        task.cancel()

    logger.info("Cancelling %d outstanding tasks", len(tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("All tasks successfully canceled")
    loop.stop()

def get_arguments() -> argparse.Namespace:
    ''' Parse arguments from CLI or if none supplied get them from Environmental variables'''
    parser = SaneArgumentParser(
        prog="Wot_recruitement_bot",
        description="Query WOT server for members leaving clans and \
                     post it in specified Deiscord channels.")
    parser.add_argument('--log-level',
                        choices=['critical', 'warning', 'error', 'info', 'debug'],
                        help="Verbosity of logging",
                        default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument('--data-file',
                        type=str,
                        help="csv file containing clan names",
                        default=os.environ.get("DATAFILE"))
    parser.add_argument('--rate-limit',
                        type=int, help="Rate limit in Requests per Second of the Wargames API.",
                        default=os.environ.get("WOT_RATE_LIMIT", 10))
    parser.add_argument('--discord-logging-url',
                        type=str,
                        help="Discord channel to send logging data to",
                        default=os.environ.get("DISCORD_LOGGING_WEBHOOK",''))
    parser.add_argument('--discord-recruit-url',
                        type=str,
                        help="Discord channel to send recruit information to",
                        default=os.environ.get("DISCORD_RECRUITMENT_WEBHOOK",''))
    parser.add_argument("--application-id",
                        dest="id",
                        type=str,
                        help=" id of your Wargaming application",
                        default=os.environ.get("APPLICATION_ID"))
    parser.add_argument("--update-interval",
                        type=SaneArgumentParser.non_negative_int,
                        help="Update members list from clans. \
                            Time interval is in seconds, default is once an hour",
                        default=os.environ.get("UPDATE_INTERVAL", 60*60))
    args = parser.parse_args()

    logger.setLevel(args.log_level.upper())
    if args.discord_logging_url:
        discord_handler = DiscordHandler(service_name="WOT recruitement BOT",
                                         webhook_url=args.discord_logging_url)
        discord_formatter = logging.Formatter(fmt="%(message)s",
                                              datefmt='%Y/%m/%d %H:%M:%S')
        discord_handler.setFormatter(discord_formatter)
        if args.log_level.upper() != "DEBUG":
            # debug logs overwhelm the Discord webhook for larger clan lists
            logger.addHandler(discord_handler)
        logger.debug("Attached discord logger")
    logger.debug(args)
    return args

def main() -> None:
    """main"""
    args = get_arguments()
    clans = read_file(args.data_file)
    loop = asyncio.get_event_loop()

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop)))

    try:
        logger.info("Starting App")
        limiter = AsyncLimiter(max_rate=args.rate_limit, time_period=1)

        request_queue = asyncio.Queue()
        response_queue = asyncio.Queue()
        recruit_queue = asyncio.Queue()
        for _ in range(NO_OF_CONSUMERS):
            loop.create_task(fetcher(request_queue,response_queue, limiter))
            loop.create_task(parse_response(response_queue,
                                            recruit_queue,
                                            clans))

        loop.create_task(get_members(args.id, clans,
                                     args.update_interval,
                                     request_queue))

        loop.create_task(recruit_members(recruit_queue, args.discord_recruit_url))
        loop.run_forever()
    finally:
        loop.close()
        logger.info("Successfully shutdown the WOT recruitment Bot.")
        store_file(clans, args.data_file)
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e.code)
