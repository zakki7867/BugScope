import pytest
from app.pricing import calculate_discounted_price

def test_float_discount():
    assert calculate_discounted_price(100.0, 0.2) == 80.0

def test_string_discount():
    # This test fails
    assert calculate_discounted_price(100.0, '0.15') == 85.0