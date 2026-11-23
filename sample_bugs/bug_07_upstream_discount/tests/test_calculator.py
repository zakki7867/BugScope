import pytest
from app.calculator import compute_final_bill

def test_bill_calculation():
    # Fails with KeyError: 'discount'
    assert compute_final_bill({'item': 'Book', 'price': 50.0}) == 50.0