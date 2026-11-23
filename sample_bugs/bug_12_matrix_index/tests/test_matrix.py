import pytest
from app.matrix import transpose

def test_non_square_matrix():
    m = [[1, 2, 3], [4, 5, 6]]
    assert transpose(m) == [[1, 4], [2, 5], [3, 6]]