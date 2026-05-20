from server.routers import _build_public_dashboard_rows


def test_build_public_dashboard_rows_sorts_and_merges_anonymous():
    users = [
        {"id": 1, "name": "Alice", "affiliation": "ETH Zurich", "credit_consent": True},
        {"id": 2, "name": "Bob", "affiliation": "EPFL", "credit_consent": False},
        {"id": 3, "name": "Charlie", "affiliation": "CMU", "credit_consent": True},
    ]
    submissions = [
        {"user_id": 1, "points": 1},
        {"user_id": 1, "points": 1},
        {"user_id": 1, "points": 0},
        {"user_id": 2, "points": 1},
        {"user_id": 3, "points": 1},
        {"user_id": 3, "points": 1},
        {"user_id": 3, "points": 1},
    ]

    rows = _build_public_dashboard_rows(users, submissions)

    assert rows == [
        {"name": "Charlie", "affiliation": "CMU", "accepted_submissions": 3},
        {"name": "Alice", "affiliation": "ETH Zurich", "accepted_submissions": 2},
        {"name": "Anonymous", "affiliation": "", "accepted_submissions": 1},
    ]


def test_build_public_dashboard_rows_excludes_users_without_confirmed_submissions():
    users = [{"id": 1, "name": "Alice", "affiliation": "ETH Zurich", "credit_consent": True}]
    submissions = [{"user_id": 1, "points": 0}]

    rows = _build_public_dashboard_rows(users, submissions)

    assert rows == []
