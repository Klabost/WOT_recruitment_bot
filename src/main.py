"""BOT that queries wargames clans. and if members apear to have left 
   a clan then their username will be posted in a discord channel"""

import signal
import logging
import os
import sys
import argparse

import asyncio
import aiohttp
from aiolimiter import AsyncLimiter

from discord_logging.handler import DiscordHandler
from sane_argument_parser import sane_argument_parser

logger = logging.getLogger(__name__)

console_handler = logging.StreamHandler(sys.stdout) # sys.stderr
console_foramt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s",
                                   datefmt='%Y/%m/%d %H:%M:%S')
console_handler.setFormatter(console_foramt)
logger.addHandler(console_handler)

async def test():
    """testing purposes only"""
    await asyncio.sleep(1000)

async def publish(args: argparse.Namespace) -> None:
    """Will query Wargames"""
    async def fetch(url, session, limiter):
        async with limiter:
            async with session.get(url) as response:
                return await response.text()


    limiter = AsyncLimiter(max_rate=args.rate_limit, time_period=1)
    url = 'http://python.org'
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session, limiter) for _ in range(10)]
        data = await asyncio.gather(*tasks)
    logger.info(*data)

async def consume(args: argparse.Namespace, recruit_logger: logging.Logger):
    """Will push to Discord"""
    recruit_logger = logging.getLogger("recruit")
    discord_handler = DiscordHandler("WOT recruitement BOT", webhook_url=args.discord_recruit_url)
    discord_handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt='%Y/%m/%d %H:%M:%S'))
    recruit_logger.addHandler(discord_handler)
    recruit_logger.setLevel(logging.INFO)

async def shutdown(sig, loop) -> None:
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
    parser = sane_argument_parser.SaneArgumentParser(
        prog="Wot_recruitement_bot",
        description="Query WOT server for members leaving clans and \
                     post it in specified Deiscord channels.")
    parser.add_argument('--log-level',
                        choices=['critical', 'warning', 'error', 'info', 'debug'],
                        help="Verbosity of logging",
                        default=os.environ.get("LOG_LEVEL", "INFO"))

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
    parser.add_argument("--clan-language",
                        choices=['nl','en'],
                        help="Language that the clan speaks, if not in this list extend it",
                        default=os.environ.get("CLAN_LANGUAGE", "nl"))
    parser.add_argument("--application-id",
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
        logger.addHandler(discord_handler)
        logger.debug("Attached discord logger")
    logger.debug(args)

    return args

def main() -> None:
    """main"""
    # args = get_arguments()
    # queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop)))

    try:
        logger.info("Starting App")
        loop.create_task(test())  # get data from wargames
        # loop.create_task(consume(queue)) # publish changes in data to discord
        loop.run_forever()
    finally:
        loop.close()
        logging.info("Successfully shutdown the Mayhem service.")

if __name__ == "__main__":
    main()
