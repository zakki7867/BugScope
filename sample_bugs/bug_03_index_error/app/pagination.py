def get_page_items(items, page, page_size):
    start_idx = (page - 1) * page_size
    if not items:
        return []
    # Direct index access causes IndexError if start_idx exceeds len
    _ = items[start_idx]
    return items[start_idx : start_idx + page_size]