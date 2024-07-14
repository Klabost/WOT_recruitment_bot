import asyncio
import aiohttp
import signal
from aiolimiter import AsyncLimiter
 
import logging
import os
import sys
from discord_logging.handler import DiscordHandler

import argparse
from saneArgumentParser import saneArgumentParser

logger = logging.getLogger(__name__)

console_handler = logging.StreamHandler(sys.stdout) # sys.stderr
console_handler.setFormatter( logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(message)s", datefmt='%Y/%m/%d %H:%M:%S') )
logger.addHandler(console_handler)

async def test(args):

    await asyncio.sleep(1000)

async def publish(args: argparse.Namespace) -> None:
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
    recruit_logger = logging.getLogger("recruit")
    discord_handler = DiscordHandler("WOT recruitement BOT", webhook_url=args.discord_recruit_url)
    discord_handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt='%Y/%m/%d %H:%M:%S'))
    recruit_logger.addHandler(discord_handler) 
    recruit_logger.setLevel(logging.INFO)

async def shutdown(signal, loop) -> None:
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not
             asyncio.current_task()]

    [task.cancel() for task in tasks]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info(f"Flushing metrics")
    loop.stop()
    
def get_arguments() -> argparse.Namespace:
    parser = saneArgumentParser.SaneArgumentParser(prog="Wot_recruitement_bot", description="Query WOT server for members leaving clans and post it in specified Deiscord channels.")
    
    parser.add_argument('--log-level', choices=['critical', 'warning', 'error', 'info', 'debug'], help="Verbosity of logging", default="info")

    parser.add_argument('--rate-limit', type=int, help="Rate limit in Requests per Second of the Wargames API.", default=os.environ.get("WOT_RATE_LIMIT", 10))
    parser.add_argument('--discord-logging-url', type=str, help="Discord channel to send logging data to", default=os.environ.get("DISCORD_LOGGING_WEBHOOK"))
    parser.add_argument('--discord-recruit-url', type=str, help="Discord channel to send recruit information to", default=os.environ.get("DISCORD_RECRUITMENT_WEBHOOK"))
        
    args = parser.parse_args()
    
    logger.setLevel(args.log_level.upper()) # parse_args will throw an exception if there is an invalid log_level value
    # if args.discord_logging_url:
    #     discord_handler = DiscordHandler("WOT recruitement BOT", webhook_url=args.discord_logging_url)
    #     discord_handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt='%Y/%m/%d %H:%M:%S'))
    #     logger.addHandler(discord_handler) 
    #     logger.debug("Attached discord logger")        
    logger.debug(args)

    return args

       
def main() -> None:    

    args = get_arguments()
    
    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop)))
        
    try:
        logger.info("Starting App")
        loop.create_task(publish(args))  # get data from wargames
        # loop.create_task(consume(queue)) # publish changes in data to discord
        loop.run_forever()
    finally:
        loop.close()
        logging.info("Successfully shutdown the Mayhem service.")
        
if __name__ == "__main__":
    main()