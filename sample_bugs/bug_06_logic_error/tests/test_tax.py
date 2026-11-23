import pytest
from app.tax import calculate_tax

def test_standard_tax():
    # 10% tax on 1000 should be 100, but logic produces 1000
    assert calculate_tax(1000.0, 10.0) == 100.0