"""Rolling goal window: Minute Grid only counts goals from the last WINDOW_YEARS years."""

from datetime import date

WINDOW_YEARS = 10


def window_start(today):
    """Same calendar day WINDOW_YEARS years ago; 29 February falls back to 28 February."""
    try:
        return today.replace(year=today.year - WINDOW_YEARS)
    except ValueError:
        return date(today.year - WINDOW_YEARS, 2, 28)


def in_window(day, start):
    """`day` and `start` are ISO strings (YYYY-MM-DD); the start day is included."""
    return day >= start
