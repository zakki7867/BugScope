import pytest
from app.tags import process_tags

def test_empty_tags():
    # Fails with ValueError
    assert process_tags([]) == ['general']