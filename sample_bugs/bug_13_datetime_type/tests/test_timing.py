import pytest
from datetime import datetime, timezone
from app.timing import get_elapsed_seconds

def test_naive_datetime():
    # Fails with TypeError
    naive_start = datetime(2026, 1, 1, 12, 0, 0)
    assert get_elapsed_seconds(naive_start) > 0