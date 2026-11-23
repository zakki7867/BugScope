import pytest
from app.user import format_user_profile

def test_valid_user():
    assert format_user_profile({'name': 'Alice', 'email': 'alice@example.com'}) == 'Alice <alice@example.com>'

def test_missing_email():
    # This test fails
    assert format_user_profile({'name': 'Bob'}) == 'Bob <N/A>'