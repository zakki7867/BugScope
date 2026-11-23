import pytest
from app.rounding import split_cents

def test_split_half():
    # Ambiguous whether 2.5 cents rounds to 2.0 or 3.0
    assert split_cents(5.0, 2) == 2.50