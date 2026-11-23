from datetime import datetime, timezone

def get_elapsed_seconds(start_time):
    now_utc = datetime.now(timezone.utc)
    # Crashes if start_time is naive datetime
    diff = now_utc - start_time
    return diff.total_seconds()