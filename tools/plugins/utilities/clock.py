"""Local date and time utility."""
from datetime import datetime


def current_time() -> str:
    now = datetime.now().astimezone()
    return now.strftime("It is %I:%M %p on %A, %B %d, %Y (%Z).")
