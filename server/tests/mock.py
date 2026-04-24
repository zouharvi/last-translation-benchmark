"""
Mock test for 1+1=2
"""

import pytest


def test_mock():
    assert 1 + 1 == 2

    with pytest.raises(AssertionError):
        assert 1 + 1 == 3
