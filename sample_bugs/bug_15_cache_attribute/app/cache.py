def is_cache_valid(last_updated_ts, ttl_seconds):
    # Bug: calling .seconds on integer timestamp
    expiry = last_updated_ts + ttl_seconds
    # Calling .seconds attribute on integer timestamp instead of timedelta
    return expiry.seconds > 1000
