from money import format_price


def test_two_decimals():
    assert format_price(3) == "3.00"


def test_uses_dot():
    assert format_price(12.5) == "12.50"
