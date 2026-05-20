from server.routers import _filter_reviewer_submissions

ROWS = [
    {
        "id": 1,
        "points": -1,
        "source_lang": "English",
        "target_lang": "Czech",
        "username": "alice",
    },
    {
        "id": 2,
        "points": 1,
        "source_lang": "German",
        "target_lang": "English",
        "username": "bob",
    },
    {
        "id": 3,
        "points": 0,
        "source_lang": "English",
        "target_lang": "French",
        "username": "bob",
    },
]


def test_status_filter_pending():
    rows = _filter_reviewer_submissions(ROWS, "pending", "", "", "")
    assert [r["id"] for r in rows] == [1]


def test_status_filter_scored():
    rows = _filter_reviewer_submissions(ROWS, "scored", "", "", "")
    assert [r["id"] for r in rows] == [2, 3]


def test_combined_filters():
    rows = _filter_reviewer_submissions(ROWS, "all", "English", "French", "bob")
    assert [r["id"] for r in rows] == [3]
