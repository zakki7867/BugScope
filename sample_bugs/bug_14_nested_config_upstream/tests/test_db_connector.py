import pytest
from app.db_connector import connect_db

def test_db_connect():
    # Fails with KeyError
    assert 'Connecting' in connect_db()