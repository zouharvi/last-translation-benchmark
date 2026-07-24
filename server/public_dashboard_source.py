import os
from typing import Any

import httpx

PUBLIC_DASHBOARD_SOURCE_ENV = "PUBLIC_DASHBOARD_SOURCE_URL"

_HTTP_CLIENT: httpx.AsyncClient | None = None


class PublicDashboardSourceError(RuntimeError):
    pass


def get_public_dashboard_source_url() -> str | None:
    source_url = os.getenv(PUBLIC_DASHBOARD_SOURCE_ENV, "").strip()
    return source_url or None


def _validate_dashboard(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PublicDashboardSourceError("Live dashboard returned an invalid response")

    required_types = {
        "rows": list,
        "total_submissions": int,
        "total_authors": int,
        "languages": list,
    }
    for field, expected_type in required_types.items():
        if not isinstance(payload.get(field), expected_type):
            raise PublicDashboardSourceError(
                f"Live dashboard response is missing a valid {field} field"
            )

    return payload


async def fetch_public_dashboard_source(
    source_url: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    global _HTTP_CLIENT

    if client is None:
        if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
            _HTTP_CLIENT = httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": "last-translation-benchmark/0.0.1"},
            )
        client = _HTTP_CLIENT

    try:
        response = await client.get(source_url)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PublicDashboardSourceError(
            "Live public dashboard data is unavailable"
        ) from exc

    return _validate_dashboard(payload)


async def close_public_dashboard_source_client() -> None:
    global _HTTP_CLIENT

    if _HTTP_CLIENT is not None and not _HTTP_CLIENT.is_closed:
        await _HTTP_CLIENT.aclose()
    _HTTP_CLIENT = None
