import importlib.util
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).parents[2] / "scripts" / "update_affiliation_locations.py"
)
SPEC = importlib.util.spec_from_file_location("update_affiliation_locations", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
UPDATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATER)


def test_combined_affiliation_searches_full_value_then_each_part():
    assert UPDATER.search_queries("PSL University, INRIA Paris") == [
        "PSL University, INRIA Paris",
        "PSL University",
        "INRIA Paris",
    ]


def test_exact_match_accepts_a_unique_ror_acronym():
    records = [
        {
            "names": [
                {"value": "PSL", "types": ["acronym"]},
                {
                    "value": "Paris Sciences et Lettres University",
                    "types": ["ror_display"],
                },
            ],
            "locations": [
                {
                    "geonames_details": {
                        "name": "Paris",
                        "country_name": "France",
                        "lat": 48.8566,
                        "lng": 2.3522,
                    }
                }
            ],
            "domains": ["psl.eu"],
        }
    ]

    match = UPDATER.exact_match("PSL", records)

    assert match is not None
    assert match["name"] == "Paris Sciences et Lettres University"
    assert match["city"] == "Paris"
