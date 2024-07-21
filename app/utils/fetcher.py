"""contains functions for fetching data from wargaming api"""
import logging
import random
import asyncio
import aiohttp

from aiolimiter import AsyncLimiter

from utils.const import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

async def fetch(url: str,
                params: dict,
                session: aiohttp.ClientSession,
                limiter: AsyncLimiter,
                max_retries=5) -> dict:
    """Performs webrequests"""
    for retry in range(max_retries):
        async with limiter:
            async with session.get(url, params=params) as response:
                if response.status == 429 or response.status == 504:
                    backoff_time = pow(2, retry + random.uniform(0,1))
                    await asyncio.sleep(backoff_time)
                else:
                    return await response.json()
    logger.error("Request to url: %s Max retries exceed", url)
    return {}

async def fetcher(request_queue: asyncio.Queue,
                  response_queue: asyncio.Queue,
                  limiter: AsyncLimiter):
    """manages web requests. Function is meant to have multiple copies running as tasks"""
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    try:
                        url, params = await request_queue.get()
                        response = await fetch(url, params, session, limiter)
                        await response_queue.put(response)
                    finally:
                        request_queue.task_done()
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,
                aiohttp.ClientConnectorError ) as se:
            logger.error("Error fetching member Data. msg: %s", se.message)
