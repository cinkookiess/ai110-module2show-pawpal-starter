"""Shared display formatting for PawPal+ (Challenge 4).

Both the terminal demo (`main.py`) and the Streamlit app (`app.py`) present the
same tasks, so the emoji/status vocabulary lives here in one place instead of
being duplicated (and drifting) between them. This module is UI-agnostic: it
returns plain strings with emojis, no ANSI colors and no Streamlit calls, so
each front end can style them however it likes (colorama in the terminal,
markdown/`st.*` in Streamlit).
"""

# One emoji per task category, so a task's type reads at a glance.
CATEGORY_EMOJI = {
    "walk": "🚶",
    "feed": "🍽️",
    "medication": "💊",
    "enrichment": "🧩",
    "grooming": "✂️",
}

# One emoji per completion status: green check when done, hourglass when pending.
STATUS_EMOJI = {
    "complete": "✅",
    "pending": "⏳",
}

# One emoji per priority level, so urgency is visible without color.
PRIORITY_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🔵",
}


def emoji_for(category):
    """Emoji for a task category, falling back to the paw print for unknowns."""
    return CATEGORY_EMOJI.get(category, "🐾")


def task_label(task):
    """Task name prefixed with its category emoji, e.g. '💊 Insulin'."""
    return f"{emoji_for(task.category)} {task.name}"


def status_label(status):
    """Status text prefixed with its icon, e.g. '✅ complete'."""
    return f"{STATUS_EMOJI.get(status, '•')} {status}"


def priority_label(priority):
    """Priority text prefixed with its icon, e.g. '🔴 high'."""
    return f"{PRIORITY_EMOJI.get(priority, '⚪')} {priority}"
