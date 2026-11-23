import pytest
from app.query import build_user_query

def test_user_query():
    # Test triggering the validation failure
    build_user_query("john'doe", "member")
