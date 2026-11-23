import pytest
from app.pagination import get_page_items

def test_first_page():
    assert get_page_items([1, 2, 3], 1, 2) == [1, 2]

def test_out_of_bounds_page():
    # This test fails
    assert get_page_items([1, 2], 5, 2) == []