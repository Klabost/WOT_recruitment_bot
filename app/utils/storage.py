"""functions used to read and write to csv file"""
import logging
import csv

from typing import List
from pydantic import ValidationError
from clan_data import Clan
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
                    clan = Clan(**row)
                    clans.append(clan)
                    logger.debug("Clan object content: %s", clan)
                except ValidationError as ve:
                    logger.error("Data-file error, illegal value: %s", ve)
            return clans
    except FileNotFoundError as fnfe:
        logger.error("Data-file error: %s", fnfe.args[1])
        return []

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
