from app.queue import fetch_next_task

def schedule_task(current_time):
    task = fetch_next_task()
    # Crashes with TypeError: unsupported operand type(s) for +: 'int' and 'str'
    return current_time + task['duration']