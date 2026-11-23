import pytest
from app.permissions import has_admin_access

def test_admin_access():
    # Fails with AttributeError
    assert has_admin_access('secret_tok') is True