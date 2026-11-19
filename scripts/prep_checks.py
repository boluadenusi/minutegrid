"""Checks that the metadata-only preparation preserves goal records."""


def total_changes(previous, current):
    return [
        (pid, old, current.get(pid, 0))
        for pid, old in sorted(previous.items())
        if old > 0 and old != current.get(pid, 0)
    ]
