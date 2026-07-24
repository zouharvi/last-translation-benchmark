import asyncio

import httpx
import pytest
from last_translation_benchmark.public_dashboard_source import (
    PublicDashboardSourceError,
    fetch_public_dashboard_source,
)


def test_fetch_public_dashboard_source_returns_valid_payload():
    payload = {
        "rows": [],
        "total_submissions": 1388,
        "total_authors": 165,
        "languages": [["English", 100]],
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))

    async def fetch():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_dashboard_source(
                "https://example.test/api/public-dashboard", client
            )

    assert asyncio.run(fetch()) == payload


def test_fetch_public_dashboard_source_rejects_invalid_payload():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"rows": []})
    )

    async def fetch():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_dashboard_source(
                "https://example.test/api/public-dashboard", client
            )

    with pytest.raises(PublicDashboardSourceError, match="total_submissions"):
        asyncio.run(fetch())
