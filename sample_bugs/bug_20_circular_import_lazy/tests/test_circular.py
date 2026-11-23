import pytest

def test_circular_import_trigger():
    import app.service_a
    assert app.service_a.compute_a(5) == 11
