import pytest
from app.scheduler import schedule_task

def test_schedule():
    # Fails with TypeError
    assert schedule_task(1000) == 1120