def is_cache_valid(last_updated_ts, ttl_seconds):
    # Bug: calling .seconds on integer timestamp
    expiry = last_updated_ts + ttl_seconds
    return expiry > 1000