#!/usr/bin/env python3
"""Suggest static map locations for public-dashboard affiliations using ROR."""

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import httpx

DEFAULT_SOURCE = (
    "https://last-translation-benchmark.vilda.net/api/public-dashboard"
)
DEFAULT_LOCATIONS = Path(__file__).parents[1] / "server" / "affiliation_locations.json"
ROR_API_URL = "https://api.ror.org/v2/organizations"


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def search_queries(affiliation: str) -> list[str]:
    queries = [affiliation.strip()]
    queries.extend(
        part.strip()
        for part in re.split(r"[,;]", affiliation)
        if part.strip() and part.strip() != affiliation.strip()
    )
    return list(dict.fromkeys(queries))


def organization_details(record: dict[str, Any]) -> dict[str, Any] | None:
    names = record.get("names", [])
    display = next(
        (
            str(item.get("value", "")).strip()
            for preferred in ("ror_display", "label")
            for item in names
            if preferred in item.get("types", []) and item.get("value")
        ),
        "",
    )
    if not display:
        return None

    variants = [
        str(item.get("value", "")).strip()
        for item in names
        if item.get("value") and str(item.get("value", "")).strip() != display
    ]
    location = next(
        (
            item.get("geonames_details") or {}
            for item in record.get("locations", [])
            if isinstance((item.get("geonames_details") or {}).get("lat"), (int, float))
            and isinstance((item.get("geonames_details") or {}).get("lng"), (int, float))
        ),
        None,
    )
    if location is None:
        return None

    domains = [str(domain) for domain in record.get("domains", []) if domain]
    return {
        "name": display,
        "variants": variants,
        "lat": float(location["lat"]),
        "lng": float(location["lng"]),
        "city": str(location.get("name", "")),
        "country": str(location.get("country_name", "")),
        "domain": domains[0] if domains else "",
    }


def exact_match(query: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized_query = normalize_name(query)
    matches = []
    for record in records:
        details = organization_details(record)
        if details and normalized_query in {
            normalize_name(details["name"]),
            *(normalize_name(variant) for variant in details["variants"]),
        }:
            matches.append(details)
    return matches[0] if len(matches) == 1 else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find unlisted dashboard affiliations in ROR and update the static map registry."
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--locations", type=Path, default=DEFAULT_LOCATIONS)
    parser.add_argument("--write", action="store_true", help="Write unambiguous matches to the JSON file")
    parser.add_argument("--client-id", default=os.getenv("ROR_CLIENT_ID", ""))
    args = parser.parse_args()

    config = json.loads(args.locations.read_text(encoding="utf-8"))
    aliases = config.setdefault("aliases", {})
    locations = config.setdefault("locations", {})
    logo_domains = config.setdefault("logo_domains", {})
    covered = set(locations) | set(aliases)

    headers = {"User-Agent": "last-translation-benchmark-affiliation-updater/1.0"}
    if args.client_id:
        headers["Client-Id"] = args.client_id

    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
        dashboard_response = client.get(args.source)
        dashboard_response.raise_for_status()
        dashboard = dashboard_response.json()
        unknown = sorted(
            {
                str(row.get("affiliation", "")).strip()
                for row in dashboard.get("rows", [])
                if str(row.get("affiliation", "")).strip()
                and str(row.get("affiliation", "")).strip() not in covered
                and not str(row.get("name", "")).startswith("Anonymous (")
            }
        )

        added = 0
        unresolved = []
        for affiliation in unknown:
            match = None
            matched_query = ""
            for query in search_queries(affiliation):
                response = client.get(ROR_API_URL, params={"query": query})
                response.raise_for_status()
                match = exact_match(query, response.json().get("items", []))
                if match is not None:
                    matched_query = query
                    break
            if match is None:
                unresolved.append(affiliation)
                continue

            canonical = match["name"]
            locations.setdefault(
                canonical,
                {
                    "lat": match["lat"],
                    "lng": match["lng"],
                    "city": match["city"],
                    "country": match["country"],
                    "precision": "city",
                },
            )
            if affiliation != canonical:
                aliases[affiliation] = canonical
            if match["domain"]:
                logo_domains.setdefault(canonical, match["domain"])
            added += 1
            query_note = f" via {matched_query}" if matched_query != affiliation else ""
            print(
                f"MATCH  {affiliation} -> {canonical}"
                f" ({match['city']}, {match['country']}){query_note}"
            )

    for affiliation in unresolved:
        print(f"OTHER  {affiliation}")
    print(
        f"\n{added} unambiguous ROR matches; "
        f"{len(unresolved)} will remain under Other affiliations."
    )

    if args.write and added:
        args.locations.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Updated {args.locations}")
    elif added:
        print("Dry run only. Re-run with --write after reviewing these matches.")


if __name__ == "__main__":
    main()
