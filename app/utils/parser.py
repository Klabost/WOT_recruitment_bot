"""Contain functions for parsing responses"""
import logging
import asyncio

from typing import List
from pydantic import ValidationError

from clan_data import Clan
from utils.const import LOGGER_NAME, CLAN_URL
from utils.enums import Reason
logger = logging.getLogger(LOGGER_NAME)

async def parse_response(request_queue: asyncio.Queue,
                        response_queue: asyncio.Queue,
                        recruit_queue: asyncio.Queue,
                        clans: List[Clan],
                        lock: asyncio.Lock):
    """Parse data retrieved from Wargames API"""
    while True:
        response, params = await response_queue.get()
        logger.debug("Parsing response: %s", response)

        if len(response) == 0:
            if params.get('search'):
                logger.error("Empty response for search: %s",params.get('search'))
            elif params.get('clan_id'):
                logger.error("Empty response for clan_id: %s",params.get('clan_id'))
            response_queue.task_done()
            continue
        if response.get('status') != 'ok':
            logger.error("query failed: %s", response.get('error'))
            response_queue.task_done()
            continue
        if not response.get('meta') or response.get('meta').get('count') == 0:
            if params.get('search'):
                logger.error("No result for search: %s",params.get('search'))
            elif params.get('clan_id'):
                logger.error("No result for clan_id: %s",params.get('clan_id'))
            response_queue.task_done()
            continue
        if response.get('meta').get('total'):
            count = response.get('meta').get('count')
            total = response.get('meta').get('total')
            if count > total and params.get('page_no') == 1:
                # pagination, get other pages
                total_pages = -1 * (-1*total // count)
                for page_no in range(2, total_pages, 1):
                    params['page_no'] = page_no
                    await request_queue.put((CLAN_URL, params))
                logger.debug("Found %d pages. added missing pages in queue", total_pages)
            await parse_clan_ids(response.get('data'), clans, params.get('search'), lock)
            response_queue.task_done()
        else:
            await parse_members(response.get('data'), recruit_queue, clans, lock)
            response_queue.task_done()

async def parse_clan_ids(data: List[dict],
                         clans: List[Clan],
                         requested_clan_name: str,
                         lock: asyncio.Lock):
    """ parses IDs data """
    for entry in data:
        try:
            new_clan = Clan(**entry)
            async with lock:
                for clan in clans:
                    if clan.name == requested_clan_name:
                        clan.update_values(new_clan)
                        logger.info("Found clan_id: %s for clan name: %s",
                                    new_clan.clan_id, new_clan.name)
                        break
                    if clan == new_clan:
                        clan.update_values(new_clan)
                        logger.info("Found clan_id: %s for clan name: %s",
                                    new_clan.clan_id, new_clan.name)
                        break
                else:
                    clans.append(new_clan)
                    logger.info("Found new clan with clan_id: %s and clan name: %s",
                        new_clan.clan_id, new_clan.name)
        except ValidationError as ve:
            logger.error("Error parsing data: %s with error %s",
                        entry, ve.args)
        except TypeError as te:
            logger.error("Error while parsing member data. Error: %s", te.args)

async def parse_members(data: List[dict],
                        recruit_queue: asyncio.Queue,
                        clans: List[Clan],
                        lock: asyncio.Lock):
    """ parses member data"""
    for clan_id, entry in data.items():
        try:
            tmpclan = Clan(**entry)
            async with lock:
                clan = None
                for x in clans:
                    if x.clan_id == int(clan_id):
                        clan = x
                        break
                if not clan:
                    logger.error("Retrieved clan data which was not requested: ID %s", clan_id)
                if clan.members is not None and clan.members != tmpclan.members:
                    for member in clan.members:
                        if member not in tmpclan.members:
                            logger.info("Found member %s that left the clan: %s",
                                        member.account_name, clan.name)
                            await recruit_queue.put((Reason.LEFT, member, clan))
                if not clan.is_clan_disbanded and tmpclan.is_clan_disbanded:
                    logger.info("Clan %s disbanded, All members are potential recruits", clan.name)
                    for member in tmpclan.members:
                        await recruit_queue.put((Reason.DISBANDED, member, clan.copy()))
                clan.update_values(tmpclan)
                logger.debug("Updated values of Clan %s with ID %d", clan.name, clan.clan_id)
        except ValidationError as ve:
            logger.error("Error parsing data: %s with error %s",
                        entry, ve.args)
        except TypeError as te:
            logger.error("Error while parsing member data. Error: %s", te.args)
