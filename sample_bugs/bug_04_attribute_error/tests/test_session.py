import pytest
from app.session import validate_session

def test_valid_token():
    assert validate_session({'token': 'SESS_123'}) is True

def test_none_token():
    # This test fails
    assert validate_session({'token': None}) is False