import pytest
from app.cache import is_cache_valid

def test_cache_validation():
    assert is_cache_valid(1500, 300) is True