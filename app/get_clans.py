"""Generate CSV file containing Clan data"""
import asyncio
import signal
import os
import logging
import argparse
import sys

import aiohttp
from aiolimiter import AsyncLimiter

from pydantic import ValidationError
from utils.const import LOGGER_NAME, CLAN_URL, CLAN_DETAILS_URL
from utils.fetcher import fetch
from utils.storage import store_file
from models import Clan

logger = logging.getLogger(LOGGER_NAME)

console_handler = logging.StreamHandler(sys.stdout) 
console_foramt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s",
                                   datefmt='%Y/%m/%d %H:%M:%S')
console_handler.setFormatter(console_foramt)
logger.addHandler(console_handler)

def parse_clan_response(responses: list[dict]) -> dict[Clan]:
    """Parse repsonses and create clan list"""
    clans = {}
    for response in responses:
        if len(response) == 0:
            logger.error("Empty response")
            continue
        if response.get('status') != 'ok':
            logger.error("query failed: %s", response.get('error'))
            continue
        data = response.get('data')
        for clan_id, entry in data.items():
            try:
                clan = Clan(**entry)
                clans[clan_id] = clan
            except ValidationError as ve:
                logger.error("Error parsing data: %s with error %s",
                            entry, ve.args)
            except TypeError as te:
                logger.error("Error while parsing member data. Error: %s", te.args)
    return clans

async def get_all_desciptions(app_id: str, clan_ids: list[str]) -> dict[Clan]:
    """Retrieve all clan details"""
    limiter = AsyncLimiter(max_rate=4, time_period=1)
    tasks = []
    responses = []
    async with aiohttp.ClientSession() as session:
        for clan_group in clan_ids:
            params = {
                'application_id': app_id,
                'clan_id': clan_group,
                "fields": "name,clan_id,tag,is_clan_disbanded,old_name,members_count,description,members"
            }
            task = fetch(CLAN_DETAILS_URL, params=params, session=session, limiter=limiter)
            tasks.append(task)
        logger.debug("Created all fetch tasks for Clan Data")
        responses = await asyncio.gather(*tasks)
    return parse_clan_response(responses)

def parse_id_response(response: dict) -> str:
    """Parse clan id response"""
    logger.debug("Parsing Response: %s", response)
    if len(response) == 0:
        logger.error("Empty response")
        return ''
    if response.get('status') != 'ok':
        logger.error("query failed: %s", response.get('error'))
        return ''
    clan_ids = response.get('data')
    list_of_ids = [str(clan_id.get('clan_id')) for clan_id in clan_ids]
    string_of_ids = ",".join(list_of_ids)
    return string_of_ids

async def get_id(params: dict,
                session: aiohttp.ClientSession,
                limiter: AsyncLimiter):
    """pipe response into parser"""
    response = await fetch(CLAN_URL, params=params, session=session, limiter=limiter)
    logger.debug("Parsing page %d", params.get('page_no'))
    return parse_id_response(response)

async def get_all_ids(app_id: str, total_pages: int = 1, search: str = None) -> list[str]:
    """Retrieve all clan IDs"""
    limiter = AsyncLimiter(max_rate=3, time_period=1)
    tasks = []
    async with aiohttp.ClientSession() as session:
        for page_no in range(1, total_pages+1, 1):
            params = {
                'application_id': app_id,
                'page_no': page_no,
                "fields": "clan_id"
            }
            if search:
                params['search'] = search
            task = get_id(params=params, session=session, limiter=limiter)
            tasks.append(task)
        logger.debug("Created all fetch tasks for ID's")
        parsed_responses = await asyncio.gather( *tasks)
        parsed_responses = list(filter(None, parsed_responses))
    return parsed_responses

def determine_no_pagers(response: dict) -> int:
    """Calculate amount of total pages"""
    logger.debug("Parsing response: %s", response)
    if len(response) == 0:
        logger.error("Empty response")
        return 0
    if response.get('status') != 'ok':
        logger.error("query failed: %s", response.get('error'))
        return 0
    count = response.get('meta').get('count')
    total = response.get('meta').get('total')
    # pagination, get other pages
    total_pages = -1 * (-1*total // count)

    logger.debug("Found %d pages", total_pages)
    return total_pages

async def start(app_id: str, search: str = None) -> int:
    """First request to determine amount of pages"""
    params = {
            'application_id': app_id,
            'page_no': 1,
            "fields": "clan_id"
        }
    if search:
        params['search'] = search
    limiter = AsyncLimiter(max_rate=4, time_period=1)
    try:
        async with aiohttp.ClientSession() as session:
            response =  await fetch(CLAN_URL, params, session, limiter) # get the ball rolling
            return determine_no_pagers(response)
    except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,
            aiohttp.ClientConnectorError ) as se:
        logger.error("Error fetching member Data. msg: %s", se.message)
        return 0

def get_arguments() -> argparse.Namespace:
    ''' Parse arguments from CLI or if none supplied get them from Environmental variables'''
    parser = argparse.ArgumentParser(
        prog="Wot_clan_retriever",
        description="Query WOT server for all clans. Unless search is specified")
    parser.add_argument('--log-level',
                        choices=['critical', 'warning', 'error', 'info', 'debug'],
                        help="Verbosity of logging",
                        default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument("--application-id",
                        dest="id",
                        type=str,
                        help=" id of your Wargaming application",
                        default=os.environ.get("APPLICATION_ID"))
    parser.add_argument("--output-file",
                        dest="file",
                        type=str,
                        help="File clan data will be stored in",
                        required=True)
    parser.add_argument("--search",
                        type=str,
                        help="If supplied look for clan names with this string in the name.\
                            Else return all clans"
                        )
    args = parser.parse_args()

    logger.setLevel(args.log_level.upper())

    logger.debug(args)
    return args

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

def main() -> None:
    """main"""
    args = get_arguments()
    loop = asyncio.get_event_loop()

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop)))
    try:
        logger.info("Starting App")

        total_pages = loop.run_until_complete(start(args.id, args.search))

        grouped_clan_ids = loop.run_until_complete(
                                    get_all_ids(
                                        args.id,
                                        total_pages=total_pages,
                                        search=args.search)
                                    )
        logger.info("Got all clan ids")
        # with open("clan_ids.txt", "a", encoding="utf-8") as file:
        #     for line in grouped_clan_ids:
        #         file.write(line +'\n')
        # grouped_clan_ids = []
        # with open("clan_ids.txt", "r",encoding="utf-8") as file:
        #     grouped_clan_ids = file.readlines()

        clans = loop.run_until_complete(get_all_desciptions(args.id, grouped_clan_ids))

        store_file(clans, args.file)
    finally:
        loop.close()
        logger.info("Successfully shutdown get Clans script.")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e.code)
