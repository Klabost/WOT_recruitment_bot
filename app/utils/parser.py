"""Contain functions for parsing responses"""
import logging
import asyncio

from pydantic import ValidationError

from models import Clan
from utils.const import LOGGER_NAME
from utils.enums import Reason
logger = logging.getLogger(LOGGER_NAME)

async def parse_response(response_queue: asyncio.Queue,
                        recruit_queue: asyncio.Queue,
                        clans: dict[Clan]):
    """Parse data retrieved from Wargames API"""
    while True:
        response = await response_queue.get()
        logger.debug("Parsing response: %s", response)

        if len(response) == 0:
            logger.error("Empty response")
            response_queue.task_done()
            continue
        if response.get('status') != 'ok':
            logger.error("query failed: %s", response.get('error'))
            response_queue.task_done()
            continue
        if not response.get('meta'):
            logger.error("Received an incorrect response. Missing mandatory fiel meta.\
                Response: %s", response)
            response_queue.task_done()
            continue
        if response.get('meta').get('count') == 0:
            logger.error("No results for query")
            response_queue.task_done()
            continue
        await parse_members(response.get('data'), recruit_queue, clans)
        response_queue.task_done()

async def parse_members(data: list[dict],
                        recruit_queue: asyncio.Queue,
                        clans: dict[Clan]):
    """ parses member data"""
    for clan_id, entry in data.items():
        try:
            tmpclan = Clan(**entry)
            clan = clans.get(clan_id)
            if not clan:
                logger.error("Retrieved clan data which was not requested: ID %s", clan_id)
                continue
            if clan.members != tmpclan.members:
                left_members = [x for x in clan.members if x not in tmpclan.members]
                for member in left_members:
                    logger.info("Found member %s that left the clan: %s",
                                member.account_name, clan.name)
                    await recruit_queue.put((Reason.LEFT, member, clan))
            if not clan.is_clan_disbanded and tmpclan.is_clan_disbanded:
                logger.info("Clan %s disbanded, All members are potential recruits", clan.name)
                for member in tmpclan.members:
                    await recruit_queue.put((Reason.DISBANDED, member, clan))

            clans[clan_id] = tmpclan
            logger.debug("Updated values of Clan %s with ID %d", clan.name, clan.clan_id)
        except ValidationError as ve:
            logger.error("Error parsing data: %s with error %s",
                        entry, ve.args)
        except TypeError as te:
            logger.error("Error while parsing member data. Error: %s", te.args)
