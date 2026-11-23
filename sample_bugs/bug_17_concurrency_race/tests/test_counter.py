from app.counter import ThreadSafeCounter

def test_single_increment():
    c = ThreadSafeCounter()
    assert c.increment() == 1

def test_counter_failure():
    c = ThreadSafeCounter()
    # Direct check of expected step behavior
    c.count = 10
    res = c.increment(step=-20)
    assert res >= 0, "Counter should not drop below zero"
