import asyncio
import json
import logging
from pathlib import Path

from qdrant_client import AsyncQdrantClient
from redis import asyncio as redis

from .config import get_settings
from .indexing import process_index_job
from .schemas import IndexJob


LOGGER = logging.getLogger("onboarding-ai-worker")


async def run() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    client = redis.from_url(settings.redis_url, decode_responses=True)
    qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    LOGGER.info("Indexing worker started")
    try:
        while True:
            item = await client.blpop(settings.redis_queue, timeout=5)
            if item:
                job_id = item[1]
                job_data = await client.get("onboarding:index:job:%s" % job_id)
                if not job_data:
                    LOGGER.warning("Indexing job metadata missing id=%s", job_id)
                    continue
                job = IndexJob.model_validate(json.loads(job_data))
                cleanup_job = True
                try:
                    result = await process_index_job(job, settings, client, qdrant)
                    if result == "locked":
                        await client.rpush(settings.redis_queue, job_id)
                        cleanup_job = False
                        await asyncio.sleep(1)
                        continue
                    LOGGER.info("Indexing job completed id=%s result=%s", job_id, result)
                except Exception:
                    LOGGER.exception("Indexing job failed id=%s", job_id)
                finally:
                    if cleanup_job:
                        await client.delete("onboarding:index:job:%s" % job_id)
                        Path(job.file_path).unlink(missing_ok=True)
    finally:
        await client.aclose()
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(run())
