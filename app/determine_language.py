"""Uses fast_langdetect to detect the language i the clan discription"""
import logging
import sys
import string
import argparse
import os
from collections import Counter

from fast_langdetect import detect, detect_multilingual, detect_language
from utils.const import LOGGER_NAME
from utils.storage import store_file, read_file

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
    except ValueError as exc:    
        raise argparse.ArgumentTypeError("Must be a floating point number") from exc
    if f < 0 or f > 1:
        raise argparse.ArgumentTypeError("Argument must be between 0 and 1")
    return f

def get_arguments() -> argparse.Namespace:
    ''' Parse arguments from CLI or if none supplied get them from Environmental variables'''
    parser = argparse.ArgumentParser(
        prog="Wot_language_detector",
        description="Read file containg Clan data and then try \
            to detect the langauge in their description.")
    parser.add_argument('--log-level',
                        choices=['critical', 'warning', 'error', 'info', 'debug'],
                        help="Verbosity of logging",
                        default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument("--input-file",
                        "-i",
                        type=str,
                        help="File containing clan data",
                        required=True)
    parser.add_argument("--output-file",
                        "-o",
                        type=str,
                        help="File clan data will be stored in",
                        required=True)
    parser.add_argument("--language",
                        type=str,
                        choices=['af', 'als', 'am', 'an', 'ar', 'arz', 'as', 'ast', 'av', 'az', 'azb', 'ba', 'bar', 'bcl', 'be', 'bg', 'bh', 'bn', 'bo', 'bpy', 'br', 'bs', 'bxr', 'ca', 'cbk', 'ce', 'ceb', 'ckb', 'co', 'cs', 'cv', 'cy', 'da', 'de', 'diq', 'dsb', 'dty', 'dv', 'el', 'eml', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'fi', 'fr', 'frr', 'fy', 'ga', 'gd', 'gl', 'gn', 'gom', 'gu', 'gv', 'he', 'hi', 'hif', 'hr', 'hsb', 'ht', 'hu', 'hy', 'ia', 'id', 'ie', 'ilo', 'io', 'is', 'it', 'ja', 'jbo', 'jv', 'ka', 'kk', 'km', 'kn', 'ko', 'krc', 'ku', 'kv', 'kw', 'ky', 'la', 'lb', 'lez', 'li', 'lmo', 'lo', 'lrc', 'lt', 'lv', 'mai', 'mg', 'mhr', 'min', 'mk', 'ml', 'mn', 'mr', 'mrj', 'ms', 'mt', 'mwl', 'my', 'myv', 'mzn', 'nah', 'nap', 'nds', 'ne', 'new', 'nl', 'nn', 'no', 'oc', 'or', 'os', 'pa', 'pam', 'pfl', 'pl', 'pms', 'pnb', 'ps', 'pt', 'qu', 'rm', 'ro', 'ru', 'rue', 'sa', 'sah', 'sc', 'scn', 'sco', 'sd', 'sh', 'si', 'sk', 'sl', 'so', 'sq', 'sr', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'tyv', 'ug', 'uk', 'ur', 'uz', 'vec', 'vep', 'vi', 'vls', 'vo', 'wa', 'war', 'wuu', 'xal', 'xmf', 'yi', 'yo', 'yue', 'zh'],
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

def main2():
    """main2"""
    args = get_arguments()
    clans = read_file(args.input_file)
    dutch_clans = []
    for clan in clans.values():
        lines = clan.description.splitlines()
        languages = []
        for line in lines:
            if len(line) == 0 or line.isspace():
                continue
            line = ''.join(filter(lambda x: x in string.printable, line))
            try:
                language = detect_language(line, low_memory=False)
                languages.append(language)
            except ValueError as ve:
                logger.error("Error parsing description: %s, Error:%s", clan.description, ve.args)
        if len(languages) > 0:
            counter = Counter(languages)
            if counter.most_common(1)[0][0] == args.language.upper():
                logger.info("Potential %s Clan: %s",
                            args.language, clan.name)
                dutch_clans.append(clan)
    store_file(dutch_clans, args.outfile)

if __name__ == "__main__":
    try:
        main2()
    except SystemExit as e:
        print(e.code)
