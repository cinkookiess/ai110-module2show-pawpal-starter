"""PawPal+ demo entry point.

Builds an owner with two pets, gives each pet its own tasks, runs a single
scheduler over the whole household (one shared time budget), and prints
"Today's Schedule" to the terminal.

Challenge 4 — Professional UI and Output Formatting:
This demo dresses up its terminal output with three formatting layers, all
implemented in the small "presentation helpers" section below:
  - Emojis per task category (💊 medication, 🚶 walk, …) so a task's type
    reads at a glance.
  - Color-coded status/priority via `colorama` (green = complete,
    yellow = pending; red/yellow/cyan for high/medium/low priority), which
    also makes ANSI colors work on Windows terminals.
  - Structured tables via `tabulate`, so every list of tasks lines up in
    clean, aligned columns instead of ragged text.
See the README's "🎨 Output formatting (Challenge 4)" section for the full
write-up.
"""

import sys
from datetime import time

from colorama import Fore, Style
from colorama import init as colorama_init
from tabulate import tabulate

from formatting import CATEGORY_EMOJI, task_label
from pawpal_system import Owner, Pet, Task, Scheduler

# Windows terminals often default to a legacy codepage (cp1252) that can't
# encode emoji, so force UTF-8 first — before colorama wraps the stream — or
# the paw prints crash the demo with a UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# Make ANSI color codes work on Windows too, and auto-reset the color after
# every print so a colored cell never "bleeds" into the text that follows.
colorama_init(autoreset=True)


# --- Presentation helpers (Challenge 4: emojis, colors, tables) -------------
# The emoji vocabulary (CATEGORY_EMOJI, emoji_for, task_label) is shared with
# the Streamlit app via formatting.py; the colorama-based color helpers below
# are terminal-only, so they stay here.

# Color + icon per status: green check when done, amber hourglass when pending.
STATUS_STYLE = {
    "complete": (Fore.GREEN, "✅"),
    "pending": (Fore.YELLOW, "⏳"),
}

# Color per priority level (high stands out in red, low recedes in cyan).
PRIORITY_COLOR = {
    "high": Fore.RED,
    "medium": Fore.YELLOW,
    "low": Fore.CYAN,
}


def when(task):
    """Preferred time as HH:MM, or a dim 'anytime' for flexible tasks."""
    if task.preferred_time is None:
        return f"{Style.DIM}anytime{Style.RESET_ALL}"
    return f"{task.preferred_time:%H:%M}"


def colored_status(status):
    """Status text with its color + icon, e.g. a green '✅ complete'."""
    color, icon = STATUS_STYLE.get(status, (Fore.WHITE, "•"))
    return f"{color}{icon} {status}{Style.RESET_ALL}"


def colored_priority(priority):
    """Priority text tinted by level (high=red, medium=yellow, low=cyan)."""
    color = PRIORITY_COLOR.get(priority, Fore.WHITE)
    return f"{color}{priority}{Style.RESET_ALL}"


def pet_name(task):
    """Task's pet name, or '?' when it isn't attached to a pet."""
    return task.pet.name if task.pet is not None else "?"


def section(title):
    """Print a bold, cyan section header so the demo's parts stand apart."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{title}{Style.RESET_ALL}")


def task_table(tasks):
    """Render a list of tasks as an aligned table (tabulate).

    Columns: Time · Pet · Task (with emoji) · Category · Duration · Status,
    with the status cell color-coded. tabulate ignores the embedded ANSI
    color codes when measuring column widths, so colored cells still line up.
    """
    rows = [
        [
            when(t),
            pet_name(t),
            task_label(t),
            t.category,
            f"{t.duration_minutes} min",
            colored_status(t.status),
        ]
        for t in tasks
    ]
    headers = ["Time", "Pet", "Task", "Category", "Duration", "Status"]
    return tabulate(rows, headers=headers, tablefmt="rounded_grid")


def main():
    # One owner and their shared daily time budget.
    owner = Owner(
        name="Sam",
        available_minutes=120,
        preferred_start_time=time(8, 0),
        priority_weights={
            "medication": 10, "feed": 8, "walk": 5,
            "grooming": 4, "enrichment": 2,
        },
    )

    # Two pets. Passing the owner auto-registers them, so owner.pets holds both.
    biscuit = Pet("Biscuit", "Dog", owner, breed="Golden Retriever")
    miso = Pet("Miso", "Cat", owner, breed="Tabby")

    print(f"{Fore.MAGENTA}{Style.BRIGHT}🐾 PawPal+ — Daily Care Planner{Style.RESET_ALL}")
    print(f"{owner.name} cares for {len(owner.pets)} pets: "
          f"{', '.join(str(p) for p in owner.pets)}")

    # Tasks, each attached to a pet via pet=... Deliberately added OUT of time
    # order (evening walk first, morning feed last) so sort_by_time has real
    # work to do below.
    tasks = [
        Task("Evening walk", "walk", 30, pet=biscuit, preferred_time=time(18, 0)),
        Task("Brush coat", "grooming", 10, pet=miso, preferred_time=time(9, 30)),
        Task("Insulin", "medication", 5, pet=biscuit, is_time_critical=True,
             dosage="2 units", times_per_day=2, dose_times=[time(8, 0), time(20, 0)]),
        Task("Feed", "feed", 10, pet=miso, preferred_time=time(9, 0)),
        Task("Breakfast", "feed", 15, pet=biscuit, preferred_time=time(8, 30)),
        # Cross-pet clash: Miso's litter cleanup (08:35) overlaps Biscuit's
        # 08:30-08:45 breakfast — the one owner can't do both at once.
        Task("Litter cleanup", "grooming", 15, pet=miso, preferred_time=time(8, 35)),
    ]

    # Mark a couple done so the status filter has something to separate.
    tasks[1].mark_complete()   # Brush coat
    tasks[3].mark_complete()   # Feed (Miso)

    # --- Tasks as entered (note they're NOT in time order) ---
    section("Tasks as entered:")
    print(task_table(tasks))

    # --- sort_by_time: same tasks, now earliest-first ---
    section("Sorted by time (sort_by_time):")
    print(task_table(Scheduler.sort_by_time(tasks)))

    # --- filter_tasks: by status, then by pet name ---
    section("Pending only (filter_tasks status='pending'):")
    print(task_table(Scheduler.filter_tasks(tasks, status="pending")))

    section("Complete only (filter_tasks status='complete'):")
    print(task_table(Scheduler.filter_tasks(tasks, status="complete")))

    section("Biscuit's tasks (filter_tasks pet_name='Biscuit'):")
    print(task_table(Scheduler.filter_tasks(tasks, pet_name="Biscuit")))

    # --- Recurrence: completing a daily/weekly task rolls the due date forward ---
    # (These live on biscuit but aren't in the `tasks` list above, so they don't
    # affect the schedule below.)
    section("Recurrence (mark_complete spawns the next occurrence):")
    daily_walk = Task("Daily walk", "walk", 20, pet=biscuit, recurrence="daily",
                      preferred_time=time(7, 0))
    weekly_bath = Task("Weekly bath", "grooming", 40, pet=biscuit, recurrence="weekly")
    recur_rows = []
    for t in (daily_walk, weekly_bath):
        t.mark_complete()
        nxt = t.next_occurrence
        recur_rows.append([
            task_label(t), t.recurrence, str(t.due_date),
            str(nxt.due_date), colored_status(nxt.status),
        ])
    print(tabulate(
        recur_rows,
        headers=["Task", "Repeats", "Was due", "Next due", "Next status"],
        tablefmt="rounded_grid",
    ))

    # --- The full plan, as before ---
    # One scheduler for the whole household — pets share the same time budget.
    scheduler = Scheduler(owner, tasks)

    # Detect time clashes before planning (same pet or across pets). The plan
    # below resolves them by dropping the lower-priority task of each pair.
    # check_conflicts returns a ready-to-print message (or "" when all clear).
    section("Conflict check (check_conflicts):")
    warning = scheduler.check_conflicts()
    if warning:
        # Tint the whole warning amber so a clash is impossible to miss.
        print(f"{Fore.YELLOW}⚠️  {warning}{Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}✅ No time conflicts.{Style.RESET_ALL}")

    scheduler.generate_plan(period="daily")

    # --- Today's plan as a color-coded, emoji-labeled table -----------------
    section(f"Today's Schedule — {len(scheduler.scheduled)} item(s), "
            f"{scheduler.total_time_used}/{owner.available_minutes} min:")
    if scheduler.scheduled:
        plan_rows = [
            [
                f"{slot.start_time:%H:%M}–{slot.end_time:%H:%M}",
                pet_name(slot.task),
                task_label(slot.task),
                slot.task.category,
                f"{slot.task.duration_minutes} min",
                colored_priority(slot.task.priority),
            ]
            for slot in sorted(scheduler.scheduled, key=lambda s: s.start_time)
        ]
        print(tabulate(
            plan_rows,
            headers=["Time", "Pet", "Task", "Category", "Duration", "Priority"],
            tablefmt="rounded_grid",
        ))
    else:
        print("  (nothing scheduled)")

    # Anything left out (a conflict loss or no time budget left).
    if scheduler.excluded:
        dropped = ", ".join(f"{task_label(t)} ({pet_name(t)})"
                            for t in scheduler.excluded)
        print(f"{Fore.YELLOW}⚠️  Left out (conflict or not enough time): "
              f"{dropped}{Style.RESET_ALL}")

    # Full reasoning stays as plain text — it's a paragraph, not a table.
    section("Why this plan?")
    print(scheduler.explain())

    # A small legend so the colors/emojis are self-explanatory.
    section("Legend:")
    print("  Status:   " + colored_status("complete") + "   " + colored_status("pending"))
    print("  Priority: " + colored_priority("high") + " · "
          + colored_priority("medium") + " · " + colored_priority("low"))
    print("  Category: " + "  ".join(f"{e} {c}" for c, e in CATEGORY_EMOJI.items()))


if __name__ == "__main__":
    main()
