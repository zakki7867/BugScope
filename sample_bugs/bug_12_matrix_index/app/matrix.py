def transpose(matrix):
    rows = len(matrix)
    cols = len(matrix[0]) if rows > 0 else 0
    # Bug: nested loop swaps index boundary
    result = [[0] * rows for _ in range(cols)]
    for c in range(cols):
        for r in range(rows):
            result[c][r] = matrix[r][c]
    return result