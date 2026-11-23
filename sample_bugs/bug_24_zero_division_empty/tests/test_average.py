from average import mean


def test_mean():
    assert mean([2, 4]) == 3


def test_empty_mean():
    assert mean([]) == 0.0
