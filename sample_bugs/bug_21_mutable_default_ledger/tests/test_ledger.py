from ledger import add_transaction, balance


def test_balance_sums():
    assert balance([1, 2]) == 3


def test_histories_are_independent():
    add_transaction(100)
    second = add_transaction(50)
    assert balance(second) == 50
