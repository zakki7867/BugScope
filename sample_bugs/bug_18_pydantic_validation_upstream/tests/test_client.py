import pytest
from app.client import fetch_and_format

def test_fetch_and_format():
    raw = {"id": 101, "timestamp": "2026-01-01T00:00:00Z"}
    res = fetch_and_format(raw)
    assert "User 101" in res
