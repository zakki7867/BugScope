import pytest
from app.sanitizer import sanitize_username

def test_allowed_symbols():
    # Fails because _ and - are improperly stripped
    assert sanitize_username('user_name-1') == 'user_name-1'