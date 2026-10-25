"""Daily clean-up of auth rows that can no longer matter.

Registered as a Reflex lifespan task (``app.register_lifespan_task``), so it
runs inside the backend process: once at start, then every 24 hours, until
the app shuts down. With several backend workers each runs it; the deletes
are idempotent. See ``service.purge_expired`` for what is deleted.
"""

import asyncio

import reflex as rx

from ..utils.logging import get_logger
from . import service, settings

log = get_logger(__name__)

INTERVAL_SECONDS = 24 * 60 * 60


def _purge() -> None:
    with rx.session() as db:
        service.purge_expired(db, settings.PURGE_AFTER)


async def purge_expired_daily() -> None:
    while True:
        try:
            await asyncio.to_thread(_purge)
        except Exception as error:
            # A failed run must not end the task: Reflex re-raises a lifespan
            # task's exception, and the next run may well succeed.
            log.error("auth.purge_failed", error=repr(error))
        await asyncio.sleep(INTERVAL_SECONDS)
