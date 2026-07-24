import json
from functools import lru_cache
from pathlib import Path
from typing import Any

AFFILIATION_LOCATIONS_PATH = Path(__file__).with_name("affiliation_locations.json")
OTHER_AFFILIATION_NAME = "Other affiliations"
OTHER_AFFILIATION_LOCATION = {
    "lat": 45.0,
    "lng": -12.0,
    "city": "Location unavailable",
    "country": "Other",
    "precision": "country",
}


@lru_cache(maxsize=1)
def load_affiliation_locations() -> dict[str, Any]:
    with AFFILIATION_LOCATIONS_PATH.open(encoding="utf-8") as locations_file:
        return json.load(locations_file)


def build_affiliation_map(
    dashboard: dict[str, Any],
    location_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = location_config or load_affiliation_locations()
    aliases = config.get("aliases", {})
    logo_domains = config.get("logo_domains", {})
    locations = config.get("locations", {})

    search_terms_by_name: dict[str, list[str]] = {}
    for alias, canonical in aliases.items():
        search_terms_by_name.setdefault(canonical, []).append(alias)

    affiliations: dict[str, dict[str, Any]] = {}
    omitted: list[dict[str, Any]] = []

    for row in dashboard.get("rows", []):
        original_name = str(row.get("affiliation", "")).strip()
        accepted = int(row.get("accepted_submissions", 0))
        canonical_name = aliases.get(original_name, original_name)
        location = locations.get(canonical_name)

        if not canonical_name or location is None:
            canonical_name = OTHER_AFFILIATION_NAME
            location = OTHER_AFFILIATION_LOCATION

        affiliation = affiliations.setdefault(
            canonical_name,
            {
                "name": canonical_name,
                "search_terms": search_terms_by_name.get(canonical_name, []),
                "logo_domain": logo_domains.get(canonical_name, ""),
                **location,
                "accepted": 0,
                "authors": [],
            },
        )
        affiliation["accepted"] += accepted
        if (
            canonical_name == OTHER_AFFILIATION_NAME
            and original_name
            and original_name not in affiliation["search_terms"]
        ):
            affiliation["search_terms"].append(original_name)
        affiliation["authors"].append(
            {"name": row.get("name", ""), "accepted": accepted}
        )

    places_by_coordinate: dict[tuple[float, float], dict[str, Any]] = {}
    for affiliation in affiliations.values():
        affiliation["authors"].sort(
            key=lambda author: (-author["accepted"], author["name"])
        )
        coordinate = (affiliation["lat"], affiliation["lng"])
        place = places_by_coordinate.setdefault(
            coordinate,
            {
                "lat": affiliation["lat"],
                "lng": affiliation["lng"],
                "city": affiliation.get("city", ""),
                "country": affiliation.get("country", ""),
                "precision": affiliation.get("precision", "city"),
                "accepted": 0,
                "affiliations": [],
            },
        )
        place["accepted"] += affiliation["accepted"]
        place["affiliations"].append(
            {
                "name": affiliation["name"],
                "search_terms": affiliation["search_terms"],
                "logo_domain": affiliation["logo_domain"],
                "accepted": affiliation["accepted"],
                "authors": affiliation["authors"],
            }
        )

    places = list(places_by_coordinate.values())
    for place in places:
        place["affiliations"].sort(
            key=lambda affiliation: (
                -affiliation["accepted"],
                affiliation["name"],
            )
        )
    places.sort(key=lambda place: (-place["accepted"], place["city"], place["country"]))

    mapped_authors = sum(
        len(affiliation["authors"]) for affiliation in affiliations.values()
    )
    return {
        "places": places,
        "mapped_authors": mapped_authors,
        "mapped_accepted": sum(place["accepted"] for place in places),
        "omitted": omitted,
    }
