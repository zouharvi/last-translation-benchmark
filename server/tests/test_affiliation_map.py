from last_translation_benchmark.affiliation_map import (
    build_affiliation_map,
    load_affiliation_locations,
)


def test_build_affiliation_map_canonicalizes_and_groups_rows():
    dashboard = {
        "rows": [
            {"name": "Ada", "affiliation": "UIC", "accepted_submissions": 3},
            {
                "name": "Grace",
                "affiliation": "University of Illinois Chicago",
                "accepted_submissions": 2,
            },
            {
                "name": "Unknown",
                "affiliation": "Unmapped Lab",
                "accepted_submissions": 1,
            },
        ]
    }
    locations = {
        "aliases": {"UIC": "University of Illinois Chicago"},
        "logo_domains": {"University of Illinois Chicago": "uic.edu"},
        "locations": {
            "University of Illinois Chicago": {
                "lat": 41.8708,
                "lng": -87.6505,
                "city": "Chicago",
                "country": "United States",
            }
        },
    }

    result = build_affiliation_map(dashboard, locations)

    assert len(result["places"]) == 2
    affiliation = next(
        affiliation
        for place in result["places"]
        for affiliation in place["affiliations"]
        if affiliation["name"] == "University of Illinois Chicago"
    )
    assert affiliation["name"] == "University of Illinois Chicago"
    assert affiliation["search_terms"] == ["UIC"]
    assert affiliation["accepted"] == 5
    assert affiliation["authors"] == [
        {"name": "Ada", "accepted": 3},
        {"name": "Grace", "accepted": 2},
    ]
    assert result["mapped_authors"] == 3
    assert result["mapped_accepted"] == 6
    assert result["omitted"] == []


def test_latest_live_affiliations_are_in_location_registry():
    dashboard = {
        "rows": [
            {
                "name": "Author One",
                "affiliation": "University of Luxembourg",
                "accepted_submissions": 9,
            },
            {
                "name": "Author Two",
                "affiliation": "Research Center for Linguistics at NOVA University Lisbon",
                "accepted_submissions": 3,
            },
            {
                "name": "Author Three",
                "affiliation": "Centro de Investigaciones Históricas, Antropológicas y Culturales (CIHAC -AIP)",
                "accepted_submissions": 1,
            },
            {
                "name": "Author Four",
                "affiliation": "DFKI GmbH and BSC-CNS",
                "accepted_submissions": 1,
            },
        ]
    }

    result = build_affiliation_map(dashboard, load_affiliation_locations())

    assert len(result["places"]) == 4
    assert result["mapped_authors"] == 4
    assert result["mapped_accepted"] == 14
    assert result["omitted"] == []


def test_unmapped_affiliations_are_grouped_under_other():
    dashboard = {
        "rows": [
            {
                "name": "Ada",
                "affiliation": "Unknown Lab",
                "accepted_submissions": 3,
            },
            {
                "name": "Grace",
                "affiliation": "Another Unknown Group",
                "accepted_submissions": 2,
            },
        ]
    }

    result = build_affiliation_map(
        dashboard,
        {"aliases": {}, "logo_domains": {}, "locations": {}},
    )

    affiliation = result["places"][0]["affiliations"][0]
    assert affiliation["name"] == "Other affiliations"
    assert affiliation["accepted"] == 5
    assert affiliation["search_terms"] == [
        "Unknown Lab",
        "Another Unknown Group",
    ]
    assert result["places"][0]["country"] == "Other"
    assert result["mapped_authors"] == 2
    assert result["mapped_accepted"] == 5
    assert result["omitted"] == []
