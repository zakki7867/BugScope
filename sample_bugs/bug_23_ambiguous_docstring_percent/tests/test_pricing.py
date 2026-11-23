from pricing import apply_discount


def test_whole_number_percent():
    assert apply_discount(200, 10) == 180


def test_twenty_percent_off():
    assert apply_discount(100, 0.2) == 80
