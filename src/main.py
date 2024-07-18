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

from discord_logging.handler import DiscordHandler
from pydantic import ValidationError
from sane_argument_parser import SaneArgumentParser
from clan_data import Clan, Member
from utils.const import CLAN_URL, CLAN_DETAILS_URL, MEMBER_DETAILS_URL

logger = logging.getLogger(__name__)

console_handler = logging.StreamHandler(sys.stdout) # sys.stderr
console_foramt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s",
                                   datefmt='%Y/%m/%d %H:%M:%S')
console_handler.setFormatter(console_foramt)
logger.addHandler(console_handler)

# seperate logger for potential  recruits
recruit_logger = logging.getLogger("recruit")
recruit_logger.setLevel(logging.INFO)

async def fetch_ids(app_id: str,
                    session: aiohttp.ClientSession,
                    limiter: AsyncLimiter,
                    clan: Clan,
                    clans: List[Clan]):
    """ fetch clan data based on clan name, 
    if the clan name return multiple values. all values will be added"""
    current_page = 1
    total_pages = 1
    while current_page <= total_pages:
        async with limiter:
            params = {'application_id': app_id,
                    'search': clan.name,
                    'page_no': current_page,
                    "fields": "name,clan_id"
                    }
            try:
                async with session.get(CLAN_URL, params=params) as response:
                    response = await response.json()
            except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,
                    aiohttp.ClientConnectorError ) as se:
                logger.error("Error fetching member Data. msg: %s", se.message)
                continue

        logger.debug("Parsing response: %s", response)
        if response.get('status') != 'ok':
            logger.error("query failed: %s", response.get('error'))
            break
        if response.get('meta').get('count') == 0:
            logger.error("No result for query: %s, will remove from list", clan.name)
            clans.remove(clan)
            break
        if current_page == 1 and total_pages == 1:
            # ceiling division. determine total amount of pages
            count = response.get('meta').get('count')
            total = response.get('meta').get('total')
            total_pages = -1 * (-1*total // count)
            logger.debug("Found {%d} page(s) in query", total_pages)
        for entry in response.get('data'):
            if entry.get("name") == clan.name:
                clan.clan_id = entry.get("clan_id")
                logger.info("Found clan_id: %s for clan name: %s", clan.clan_id, clan.name)
            else:
                new_clan = Clan(name=entry.get("name"), clan_id=entry.get("clan_id"))
                logger.info("Found new clan with clan_id: %s and clan name: %s",
                            new_clan.clan_id, new_clan.name)
                clans.append(new_clan)
        current_page += 1

async def get_clan_ids(app_id: str,
                       clans: List[Clan],
                       lock: asyncio.Lock,
                       limiter: AsyncLimiter,
                       update_interval: int) -> None:
    """Will query Wargames"""
    while True:
        async with lock:
            async with aiohttp.ClientSession() as session:
                tasks = []
                for clan in clans:
                    logger.info("Fetching Clan Data, Name: %s", clan.name)
                    tasks.append(
                        fetch_ids(app_id, session, limiter, clan, clans)
                    )
                await asyncio.gather(*tasks)
        if update_interval == 0:
            break
        await asyncio.sleep(update_interval)

def parse_difference_member_list(old_list: List[Member], current_list: List[Member]):
    """Determine if members left"""
    members_left = [member for member in old_list if member not in current_list]
    if len(members_left) > 0:
        logger.debug("Found members that left the clan:%s", members_left)
    for member in members_left:
        url = MEMBER_DETAILS_URL + member.account_name + '-' + str(member.account_id) + '/'
        recruit_logger.info("Found potential recruit. Name: %s, Account ID: %d, Stats: %s",
                            member.account_name, member.account_id, url)

async def fetch_members(app_id: str,
                    session: aiohttp.ClientSession,
                    limiter: AsyncLimiter,
                    clan: Clan):
    """ fetch clan members data based on clan id"""
    async with limiter:
        params = {'application_id': app_id,
                'clan_id': clan.clan_id,
                "fields": "name,clan_id,old_name,is_clan_disbanded,members_count,members"
                }
        try:
            async with session.get(CLAN_DETAILS_URL, params=params) as response:
                response = await response.json()
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,
                aiohttp.ClientConnectorError ) as se:
            logger.error("Error fetching member Data. msg: %s", se.message)
            return

    logger.debug("Parsing response: %s", response)
    if response.get('status') != 'ok':
        logger.error("query failed: %s", response.get('error'))
        return
    if response.get('meta').get('count') == 0:
        logger.error("No result for query name: %s, id: %d", clan.name, clan.clan_id)
        return
    new_data = response.get("data").get(str(clan.clan_id))
    try:
        tmpclan = Clan(**new_data)
        if clan.members is not None and clan.members != tmpclan.members:
            parse_difference_member_list(clan.members, tmpclan.members)
            logger.info("Members list updated of Clan %s with ID %d", clan.name, clan.clan_id)
        clan.update_values(tmpclan)
        logger.debug("Updated values of Clan %s with ID %d", clan.name, clan.clan_id)
    except ValidationError as ve:
        logger.error("Error parsing data from Clan %s with id %d, with error %s",
                     clan.name, clan.clan_id, ve.args)

async def get_members(app_id: str,
                      clans: List[Clan],
                      lock: asyncio.Lock,
                      limiter: AsyncLimiter,
                      update_interval: int) -> None:
    """query members from clan"""
    while True:
        async with lock:
            async with aiohttp.ClientSession() as session:
                tasks = []
                for clan in clans:
                    logger.info("Fetching Members Data from: %s", clan.name)
                    tasks.append(
                        fetch_members(app_id, session, limiter, clan)
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
    parser.add_argument("--clan-id-update-interval",
                        type=int,
                        help="Update Clan id associated with clan name. \
                            Time interval is in seconds, default is once a week",
                        default=os.environ.get("CLAN_ID_UPDATE_INTERVAL", 60*60*24*7))
    parser.add_argument("--members-update-interval",
                        type=int,
                        help="Update members list from clans. \
                            Time interval is in seconds, default is once a day",
                        default=os.environ.get("MEMBERS_UPDATE_INTERVAL", 60*60*24))
    args = parser.parse_args()

    logger.setLevel(args.log_level.upper())
    if args.discord_logging_url:
        discord_handler = DiscordHandler(service_name="WOT recruitement BOT",
                                         webhook_url=args.discord_logging_url)
        discord_formatter = logging.Formatter(fmt="%(message)s",
                                              datefmt='%Y/%m/%d %H:%M:%S')
        discord_handler.setFormatter(discord_formatter)
        logger.addHandler(discord_handler)
        logger.debug("Attached discord logger")
    if args.discord_recruit_url:
        recruit_handler = DiscordHandler("WOT recruitement BOT",
                                         webhook_url=args.discord_recruit_url)
        recruit_formatter = logging.Formatter(fmt="%(message)s",
                                              datefmt='%Y/%m/%d %H:%M:%S')
        recruit_handler.setFormatter(recruit_formatter)
        recruit_logger.addHandler(recruit_handler)
        logger.debug("Added discord handler to recruit logger")
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
    loop = asyncio.get_event_loop()

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop)))

    try:
        logger.info("Starting App")
        limiter = AsyncLimiter(max_rate=args.rate_limit, time_period=1)
        lock = asyncio.Lock()  # lock before you access and edit clan_data

         # get id numbers from clan name from wargames
        loop.create_task(get_clan_ids(args.id, clan_data, lock,
                                      limiter, args.clan_id_update_interval))
        loop.create_task(get_members(args.id, clan_data, lock,
                                     limiter, args.clan_id_update_interval))
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
