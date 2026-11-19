"""Shared rules for turning PitchAPI goal events into Minute Grid cells."""


def is_shootout(period):
    period = (period or "").casefold()
    return "shootout" in period or "penalt" in period


def is_extra_period(period):
    return "extra" in (period or "").casefold()


def goal_cell(event):
    """Return (cell, is_extra_time, includes_added_time) or None when the goal does not count.

    Own goals and shootout kicks never count. Penalties count.
    45+x fills cell 45 and 90+x fills cell 90; minutes past 90 outside the
    second half are extra time.
    """
    if event.get("is_own_goal") or is_shootout(event.get("period")):
        return None
    minute = event.get("minute")
    if not isinstance(minute, int) or minute < 1:
        return None
    added = event.get("minute_added") or 0
    period = (event.get("period") or "").casefold()
    if is_extra_period(period) or (minute > 90 and period != "secondhalf"):
        return minute, True, added > 0
    if period == "firsthalf" and minute > 45:
        return 45, False, True
    if minute > 90:
        return 90, False, True
    return minute, False, added > 0 and minute in (45, 90)
