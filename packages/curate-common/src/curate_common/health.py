"""Pre-flight health checks for local emulator dependencies."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

if TYPE_CHECKING:
    from curate_common.config import Settings

logger = logging.getLogger(__name__)


async def check_emulators(settings: Settings) -> bool:
    """Verify local emulators are reachable. Return False if any are down."""
    failures: list[str] = []
    async with httpx.AsyncClient(timeout=3) as client:
        cosmos_url = settings.cosmos.endpoint
        if not cosmos_url:
            failures.append(
                "AZURE_COSMOS_ENDPOINT is not set — add it to .env (see .env.example)"
            )
        elif not cosmos_url.startswith("https://"):
            try:
                await client.get(f"{cosmos_url.rstrip('/')}/")
            except httpx.ConnectError:
                parsed = urlparse(cosmos_url)
                failures.append(f"Cosmos DB emulator is not running at {parsed.netloc}")

        storage_url = settings.storage.account_url
        if not storage_url:
            failures.append(
                "AZURE_STORAGE_ACCOUNT_URL is not set — add it to .env "
                "(see .env.example)"
            )
        elif not storage_url.startswith("https://"):
            try:
                parsed = urlparse(storage_url)
                await client.get(f"{parsed.scheme}://{parsed.netloc}/")
            except httpx.ConnectError:
                parsed = urlparse(storage_url)
                failures.append(
                    f"Azurite storage emulator is not running at {parsed.netloc}"
                )

    if failures:
        for failure in failures:
            logger.error(failure)
        logger.error("Start the emulators with: docker compose up -d")
        return False
    return True
