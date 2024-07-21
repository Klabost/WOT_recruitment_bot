"""Uses fast_langdetect to detect the language i the clan discription"""
import logging
import sys
import string
import argparse
import os

from fast_langdetect import detect, detect_multilingual

from utils.const import LOGGER_NAME
from utils.storage import store_file, read_file
from models import Clan 

logger = logging.getLogger(LOGGER_NAME)

console_handler = logging.StreamHandler(sys.stdout) 
console_foramt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s",
                                   datefmt='%Y/%m/%d %H:%M:%S')
console_handler.setFormatter(console_foramt)
logger.addHandler(console_handler)

def threshold_range(arg):
    """ Type function for argparse - a float within some predefined bounds """
    try:
        f = float(arg)
    except ValueError:    
        raise argparse.ArgumentTypeError("Must be a floating point number")
    if f < 0 or f > 1:
        raise argparse.ArgumentTypeError("Argument must be between 0 and 1")
    return f

def get_arguments() -> argparse.Namespace:
    ''' Parse arguments from CLI or if none supplied get them from Environmental variables'''
    parser = argparse.ArgumentParser(
        prog="Wot_language_detector",
        description="Query WOT server for all clans and then try \
            to detect langauge in their description. Unless search is specified")
    parser.add_argument('--log-level',
                        choices=['critical', 'warning', 'error', 'info', 'debug'],
                        help="Verbosity of logging",
                        default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument("--input-file",
                        "-i",
                        dest="infile",
                        type=str,
                        help="File containing clan data",
                        default="clan_data.csv")
    parser.add_argument("--output-file",
                        "-o",
                        dest="outfile",
                        type=str,
                        help="File clan data will be stored in",
                        default="dutch_clans.csv")
    parser.add_argument("--language",
                        type=str,
                        choices=['en','nl'],
                        default='nl',
                        help="Determine if the decsription is this language")
    parser.add_argument("--threshold",
                        type=threshold_range,
                        default=0.2,
                        help="The average score has to be higher then this to be considered valid")
    args = parser.parse_args()

    logger.setLevel(args.log_level.upper())

    logger.debug(args)
    return args

def main():
    """main"""
    args = get_arguments()
    threshold = args.threshold
    clans = read_file(args.infile)
    dutch_clans = []
    for clan in clans:
        lines = clan.description.splitlines()
        total_score = 0
        no_lines = 1
        for line in lines:
            if len(line) == 0 or line.isspace():
                continue
            line = ''.join(filter(lambda x: x in string.printable, line))
            no_lines += 1
            try:
                scores = detect_multilingual(line, low_memory=False)
                for score in scores:
                    if score.get('lang') == args.language:
                        total_score += score.get('score')
            except ValueError as ve:
                logger.error("Error parsing description: %s, Error:%s", clan.description, ve.args)
        gem_score = total_score/no_lines
        if gem_score > threshold:
            logger.info("Potential %s Clan: %s, average score: %f",
                        args.language, clan.name, gem_score)
            dutch_clans.append(clan)

    store_file(dutch_clans, args.outfile)

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e.code)