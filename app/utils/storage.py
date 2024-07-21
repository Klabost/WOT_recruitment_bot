"""functions used to read and write to csv file"""
import logging
import csv

from typing import List
from pydantic import ValidationError
from models import Clan
from utils.const import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

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
                    if not row.get('is_clan_disbanded') or row.get('is_clan_disbanded').isspace():
                        row['is_clan_disbanded'] = False
                    clan = Clan(**row)
                    clans.append(clan)
                    logger.debug("Clan object content: %s", clan)
                except ValidationError as ve:
                    logger.error("Parsing Error. Line: %s, Error: %s", row, ve)
            return clans
    except FileNotFoundError as fnfe:
        logger.error("Data-file error: %s", fnfe.args[1])
        return []

def store_file(clans: List[Clan], filename: str) -> None:
    """Write current dataframe to csv file"""
    if len(clans) == 0:
        logger.error("Cannot store empty list")
        return
    try:
        with open(filename, "w", encoding="utf-8") as csvfile:
            headers = ["name", "clan_id", "tag", "is_clan_disbanded",
                       "old_name","members_count", "description"]
            writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter=',')
            writer.writeheader()
            logger.debug("Writeing file, headers found: %s", headers)
            for clan in clans:
                clan_dict = clan.model_dump()
                filtered_dict = dict((k, clan_dict[k]) for k in headers if k in clan_dict)
                logger.debug("Clan object to dict Content: %s", filtered_dict)
                writer.writerow(filtered_dict)
        logger.info("Saved Current clan list to %s", filename)
    except PermissionError as pe:
        logger.error("Cannot Store current clan info: %s", pe.args[1])
