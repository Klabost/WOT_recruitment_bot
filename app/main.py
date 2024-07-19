"""BOT that queries wargames clans. and if members apear to have left
   a clan then their username will be posted in a discord channel"""

import signal
import logging
import os
import sys
import argparse

import asyncio
from typing import List
import aiohttp
from aiolimiter import AsyncLimiter

from discord_logging.handler import DiscordHandler
from pydantic import ValidationError
from discord import Webhook

from sane_argument_parser import SaneArgumentParser
from clan_data import Clan
from utils.const import CLAN_URL, CLAN_DETAILS_URL, MEMBER_DETAILS_URL, LOGGER_NAME
from utils.storage import read_file, store_file

logger = logging.getLogger(LOGGER_NAME)

console_handler = logging.StreamHandler(sys.stdout) # sys.stderr
console_foramt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s",
                                   datefmt='%Y/%m/%d %H:%M:%S')
console_handler.setFormatter(console_foramt)
logger.addHandler(console_handler)

async def fetch(url: str,
                params: dict,
                session: aiohttp.ClientSession,
                limiter:AsyncLimiter) -> dict:
    """Performs webrequests"""
    async with limiter:
        try:
            async with session.get(url, params=params) as response:
                response = await response.json()
                return response
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,
                aiohttp.ClientConnectorError ) as se:
            logger.error("Error fetching member Data. msg: %s", se.message)
            return {}

async def parse_clan_ids(clans: List[Clan], queue: asyncio.Queue, lock: asyncio.Lock):
    """ parses data retrieved by feth_ids"""
    while True:
        clan, response = await queue.get()
        logger.debug("Parsing Clan response: %s", response)

        if len(response) == 0:
            logger.error("Empty response for Clan: %s", clan.name)
            queue.task_done()
            continue
        if response.get('status') != 'ok':
            logger.error("query failed: %s", response.get('error'))
            queue.task_done()
            continue
        if response.get('meta').get('count') == 0:
            logger.error("No result for query: %s, will remove from list", clan.name)
            clans.remove(clan)
            queue.task_done()
            continue
        for entry in response.get('data'):
            if entry.get("name") == clan.name:
                clan.clan_id = entry.get("clan_id")
                logger.info("Found clan_id: %s for clan name: %s", clan.clan_id, clan.name)
            else:
                new_clan = Clan(name=entry.get("name"), clan_id=entry.get("clan_id"))
                if new_clan in clans:
                    logger.debug("Double entry: %s", new_clan.name)
                    continue
                logger.info("Found new clan with clan_id: %s and clan name: %s",
                            new_clan.clan_id, new_clan.name)
                async with lock:
                    clans.append(new_clan)
        queue.task_done()

async def fetch_ids(app_id: str,
                    session: aiohttp.ClientSession,
                    limiter: AsyncLimiter,
                    clan: Clan,
                    queue: asyncio.Queue):
    """ fetch clan data based on clan name,
    if the clan name return multiple values. all values will be added"""

    current_page = 1
    total_pages = 1
    while current_page <= total_pages:
        params = {'application_id': app_id,
                'search': clan.name,
                'page_no': current_page,
                "fields": "name,clan_id"
                }
        response = await fetch(CLAN_URL, params, session, limiter)
        if len(response) != 0 and current_page == 1 and total_pages == 1:
            # ceiling division. determine total amount of pages
            count = response.get('meta').get('count')
            total = response.get('meta').get('total')
            if count and total:
                total_pages = -1 * (-1*total // count)
                logger.debug("Found {%d} page(s) in query", total_pages)
        await queue.put((clan, response))
        current_page += 1

async def get_clan_ids(app_id: str,
                       clans: List[Clan],
                       limiter: AsyncLimiter,
                       update_interval: int,
                       queue: asyncio.Queue,
                       lock: asyncio.Lock) -> None:
    """Will Fetch clan id's"""
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = []
            async with lock:
                logger.info("Updating Clan list")
                for clan in clans:
                    if clan.clan_id != 0:
                        logger.debug("Skipping Clan %s, already have clan ID %s",
                                    clan.name, clan.clan_id)
                        continue
                    logger.debug("Fetching Clan ID, Name: %s", clan.name)
                    tasks.append(
                        fetch_ids(app_id, session, limiter, clan, queue)
                    )
            await asyncio.gather(*tasks)
        if update_interval == 0:
            break
        await asyncio.sleep(update_interval)

async def recruit_members(queue: asyncio.Queue, url: str) -> None:
    """Send recruit data to discord channel.
    Webhooks are rate limited to 30 message per minute
    according to stackoverflow"""
    limiter = AsyncLimiter(30, 60)
    while True:
        reason, member = await queue.get()
        logger.debug("Sending %s information to discord", member.account_name)
        try:
            async with limiter:
                async with aiohttp.ClientSession() as session:
                    webhook = Webhook.from_url(url, session=session)
                    stat_url = f"{MEMBER_DETAILS_URL}/{member.account_name}-{member.account_id}/"
                    message = (f"Member found. Name: {member.account_name}, "
                               f"ID: {member.account_id}, stats: {stat_url} ",
                               f"Reason: {reason}")
                    await webhook.send(message, username='WOT_BOT')
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,
                aiohttp.ClientConnectorError ) as se:
            logger.error("Error sending Data to discord recruit channel. Error: %s",se.message)
        finally:
            queue.task_done()

async def parse_members(queue: asyncio.Queue, recruit_queue: asyncio.Queue):
    """ parses data retrieved by feth_ids"""
    while True:
        clan, response = await queue.get()
        logger.debug("Parsing Member response: %s", response)

        if len(response) == 0:
            logger.error("Empty response for Clan: %s", clan.name)
            queue.task_done()
            continue
        if response.get('status') != 'ok':
            logger.error("query failed: %s", response.get('error'))
            queue.task_done()
            continue
        if response.get('meta').get('count') == 0:
            logger.error("No result for query name: %s, id: %d", clan.name, clan.clan_id)
            queue.task_done()
            continue
        if response.get("data").get(str(clan.clan_id)) is None:
            logger.error("No members in Clan %s, with ID: %d", clan.name, clan.clan_id)
            queue.task_done()
            continue
        try:
            new_data = response.get("data").get(str(clan.clan_id))
            tmpclan = Clan(**new_data)
            if clan.members is not None and clan.members != tmpclan.members:
                for member in clan.members:
                    if member not in tmpclan.members:
                        logger.info("Found member %s that left the clan: %s",
                                    member.account_name, clan.name)
                        await recruit_queue.put(('left', member))
            if not clan.is_clan_disbanded and tmpclan.is_clan_disbanded:
                logger.info("Clan %s disbanded, All members are potential recruits", clan.name)
                for member in tmpclan.members:
                    await recruit_queue.put(("Clan disbanded", member))
            clan.update_values(tmpclan)
            logger.debug("Updated values of Clan %s with ID %d", clan.name, clan.clan_id)
        except ValidationError as ve:
            logger.error("Error parsing data from Clan %s with id %d, with error %s",
                        clan.name, clan.clan_id, ve.args)
        except TypeError as te:
            logger.error("Error while parsing member data. Error: %s", te.args)
        finally:
            queue.task_done()

async def fetch_members(app_id: str,
                    session: aiohttp.ClientSession,
                    limiter: AsyncLimiter,
                    clan: Clan,
                    queue: asyncio.Queue):
    """ fetch clan members data based on clan id"""
    if clan.clan_id == 0:
        logger.error("No Clan id for Clan %s yet, will wait 3 seconds", clan.name)
        await asyncio.sleep(3)
        if clan.clan_id == 0:
            logger.error("Still no clan ID for Clan %s. Quitting", clan.name)
            return
    params = {'application_id': app_id,
            'clan_id': clan.clan_id,
            "fields": "name,clan_id,old_name,is_clan_disbanded,members_count,members"
            }
    response = await fetch(CLAN_DETAILS_URL, params, session, limiter)
    await queue.put((clan, response))

async def get_members(app_id: str,
                      clans: List[Clan],
                      limiter: AsyncLimiter,
                      update_interval: int,
                      queue: asyncio.Queue,
                      lock: asyncio.Lock) -> None:
    """query members from clan"""
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = []
            async with lock:
                logger.info("Fetching Member Data")
                for clan in clans:
                    logger.debug("Fetching Members Data from: %s", clan.name)
                    tasks.append(
                        fetch_members(app_id, session, limiter, clan, queue)
                    )
            await asyncio.gather(*tasks)
        if update_interval == 0:
            break
        await asyncio.sleep(update_interval)

async def shutdown(sig: signal.signal, loop: asyncio.BaseEventLoop) -> None:
    """Cleanup tasks tied to the service's shutdown."""
    logger.info("Received exit signal %s ...", sig.name)
    tasks = [t for t in asyncio.all_tasks() if t is not
             asyncio.current_task()]

    for task in tasks:
        task.cancel()

    logger.info("Cancelling %d outstanding tasks", len(tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("All tasksk successfully canceled")
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
                        default=os.environ.get("DATAFILE", "wot.csv"))
    parser.add_argument('--rate-limit',
                        type=int, help="Rate limit in Requests per Second of the Wargames API.",
                        default=os.environ.get("WOT_RATE_LIMIT", 10))
    parser.add_argument('--discord-logging-url',
                        type=str,
                        help="Discord channel to send logging data to",
                        default=os.environ.get("DISCORD_LOGGING_WEBHOOK"))
    parser.add_argument('--discord-recruit-url',
                        type=str,
                        help="Discord channel to send recruit information to",
                        default=os.environ.get("DISCORD_RECRUITMENT_WEBHOOK"))
    parser.add_argument("--application-id",
                        dest="id",
                        type=str,
                        help=" id of your Wargaming application",
                        default=os.environ.get("APPLICATION_ID"))
    parser.add_argument("--clan-id-update-interval",
                        type=int,
                        help="Update Clan id associated with clan name. \
                            Time interval is in seconds, default is once a week",
                        default=os.environ.get("CLAN_ID_UPDATE_INTERVAL", 60*60*24*7))
    parser.add_argument("--members-update-interval",
                        type=int,
                        help="Update members list from clans. \
                            Time interval is in seconds, default is once an hour",
                        default=os.environ.get("MEMBERS_UPDATE_INTERVAL", 60*60))
    args = parser.parse_args()

    logger.setLevel(args.log_level.upper())
    if args.discord_logging_url:
        discord_handler = DiscordHandler(service_name="WOT recruitement BOT",
                                         webhook_url=args.discord_logging_url)
        discord_formatter = logging.Formatter(fmt="%(message)s",
                                              datefmt='%Y/%m/%d %H:%M:%S')
        discord_handler.setFormatter(discord_formatter)
        # logger.addHandler(discord_handler)
        logger.debug("Attached discord logger")
    logger.debug(args)
    return args

def main() -> None:
    """main"""
    args = get_arguments()
    clan_data = read_file(args.data_file)
    loop = asyncio.get_event_loop()

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop)))

    try:
        logger.info("Starting App")
        limiter = AsyncLimiter(max_rate=args.rate_limit, time_period=1)
        lock = asyncio.Lock()
        clan_queue = asyncio.Queue()
         # get id numbers from clan name from wargames
        loop.create_task(get_clan_ids(args.id, clan_data, limiter,
                                      args.clan_id_update_interval,
                                      clan_queue,
                                      lock))
        loop.create_task(parse_clan_ids(clan_data, clan_queue, lock))

        members_queue = asyncio.Queue()
        recruits_queue = asyncio.Queue()
        loop.create_task(get_members(args.id, clan_data, limiter,
                                     args.members_update_interval,
                                     members_queue,
                                     lock))
        loop.create_task(parse_members(members_queue, recruits_queue))
        loop.create_task(recruit_members(recruits_queue, args.discord_recruit_url))
        loop.run_forever()
    finally:
        loop.close()
        logger.info("Successfully shutdown the WOT recruitment Bot.")
        store_file(clan_data, args.data_file)
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e.code)
