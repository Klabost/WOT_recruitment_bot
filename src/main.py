"""BOT that queries wargames clans. and if members apear to have left 
   a clan then their username will be posted in a discord channel"""

import signal
import logging
import os
import sys
import argparse
import csv

import asyncio
from typing import List
import aiohttp
from aiolimiter import AsyncLimiter
import pandas as pd

from discord_logging.handler import DiscordHandler
from pydantic import ValidationError
from sane_argument_parser import SaneArgumentParser
from clan_data import Clan, Member

logger = logging.getLogger(__name__)

console_handler = logging.StreamHandler(sys.stdout) # sys.stderr
console_foramt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s",
                                   datefmt='%Y/%m/%d %H:%M:%S')
console_handler.setFormatter(console_foramt)
logger.addHandler(console_handler)

# params (application_id, clan_id, search)
CLAN_URL = "https://api.worldoftanks.eu/wot/clans/list/"
CLAN_DETAILS_URL = "https://api.worldoftanks.eu/wot/clans/info/"


async def fetch(url,  session, limiter, params=None):
    """ fetch data from url"""
    async with limiter:
        async with session.get(url, params=params) as response:
            return await response.json()

async def get_clan_ids(app_id: str, datastore: pd.DataFrame, limiter) -> None:
    """Will query Wargames"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for name in datastore['Name'].to_list():
            params = {'application_id': app_id, 'search': name, "fields": "name,clan_id"}
            logger.info("Fetching Clan Data, Name: %s", name)
            tasks.append(fetch(CLAN_URL, session, limiter, params))
        responses = await asyncio.gather(*tasks)
    logger.debug("Get clan ids query results: %s", responses)
    for response in responses:
        logger.debug("Parsing response: %s", response)
        if response.get('status') != 'ok':
            logger.error("query failed: %s", response.get('error'))
        if response.get('meta').get('count') == 0:
            continue

async def consume(args: argparse.Namespace, recruit_logger: logging.Logger):
    """Will push to Discord"""
    recruit_logger = logging.getLogger("recruit")
    discord_handler = DiscordHandler("WOT recruitement BOT", webhook_url=args.discord_recruit_url)
    discord_handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt='%Y/%m/%d %H:%M:%S'))
    recruit_logger.addHandler(discord_handler)
    recruit_logger.setLevel(logging.INFO)

async def shutdown(sig: signal.signal, loop: asyncio.BaseEventLoop) -> None:
    """Cleanup tasks tied to the service's shutdown."""
    logger.info("Received exit signal %s ...", sig.name)
    tasks = [t for t in asyncio.all_tasks() if t is not
             asyncio.current_task()]

    for task in tasks:
        task.cancel()

    logger.info("Cancelling %d outstanding tasks", len(tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Flushing metrics")
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

def read_file(filename: str) -> List[Clan]:
    """ read file contain clan names and store it in a dataframe"""
    try:
        logger.info("Parsing data file: %s", filename)
        with open(filename, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            clans = []
            for row in reader:
                try:
                    logger.debug("File Contents: %s", row)
                    clan = Clan(**row)
                    clans.append(clan)
                    logger.debug("Clan object content: %s", clan)
                except ValidationError as ve:
                    logger.error("Data-file error, illegal value: %s", ve)
            return clans
    except FileNotFoundError as fnfe:
        logger.error("Data-file error: %s", fnfe.args[1])
        sys.exit(1)

def store_file(clan_data: List[Clan], filename: str) -> None:
    """Write current dataframe to csv file"""
    if len(clan_data) == 0:
        logger.error("Cannot store empty list")
        return
    try:
        with open(filename, "w", encoding="utf-8") as csvfile:
            headers = ["name", "clan_id", "is_clan_disbanded", "old_name"]
            writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter=',')
            writer.writeheader()
            logger.debug("Writeing file, headers found: %s", headers)
            for clan in clan_data:
                clan_dict = clan.model_dump()
                filtered_dict = dict((k, clan_dict[k]) for k in headers if k in clan_dict)
                logger.debug("Clan object to dict Content: %s", filtered_dict)
                writer.writerow(filtered_dict)
        logger.info("Saved Current clan list to %s", filename)
    except PermissionError as pe:
        logger.error("Cannot Store current clan info: %s", pe.args[1])

def main() -> None:
    """main"""
    args = get_arguments()
    clan_data = read_file(args.data_file)
    store_file(clan_data, args.data_file)
    # queue = asyncio.Queue()
    # loop = asyncio.get_event_loop()
    # signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    # for s in signals:
    #     loop.add_signal_handler(
    #         s, lambda s=s: asyncio.create_task(shutdown(s, loop)))
    
    # try:
    #     logger.info("Starting App")
    #     limiter = AsyncLimiter(max_rate=args.rate_limit, time_period=1)

    #     loop.create_task(get_clan_ids(args.id, clan_data, limiter))  # get data from wargames
    #     # loop.create_task(consume(queue)) # publish changes in data to discord
    #     loop.run_forever()
    # finally:
    #     loop.close()
    #     logger.info("Successfully shutdown the WOT recruitment Bot.")
    #     # store_file(datastore, args.data_file)
    #     sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e.code)
