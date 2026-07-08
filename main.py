"""PawPal+ demo entry point.

Builds an owner with two pets, gives each pet its own tasks, runs a single
scheduler over the whole household (one shared time budget), and prints
"Today's Schedule" to the terminal.
"""

from datetime import time

from pawpal_system import Owner, Pet, Task, Scheduler


def _row(task):
    """One-line view of a task for the demo prints: time, pet, name, status."""
    when = f"{task.preferred_time:%H:%M}" if task.preferred_time else "anytime"
    pet_name = task.pet.name if task.pet is not None else "?"
    return f"{when}  [{pet_name}] {task.name} - {task.status}"


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
    print("\nTasks as entered:")
    for t in tasks:
        print(f"  {_row(t)}")

    # --- sort_by_time: same tasks, now earliest-first ---
    print("\nSorted by time (sort_by_time):")
    for t in Scheduler.sort_by_time(tasks):
        print(f"  {_row(t)}")

    # --- filter_tasks: by status, then by pet name ---
    print("\nPending only (filter_tasks status='pending'):")
    for t in Scheduler.filter_tasks(tasks, status="pending"):
        print(f"  {_row(t)}")

    print("\nComplete only (filter_tasks status='complete'):")
    for t in Scheduler.filter_tasks(tasks, status="complete"):
        print(f"  {_row(t)}")

    print("\nBiscuit's tasks (filter_tasks pet_name='Biscuit'):")
    for t in Scheduler.filter_tasks(tasks, pet_name="Biscuit"):
        print(f"  {_row(t)}")

    # --- Recurrence: completing a daily/weekly task rolls the due date forward ---
    # (These live on biscuit but aren't in the `tasks` list above, so they don't
    # affect the schedule below.)
    print("\nRecurrence (mark_complete spawns the next occurrence):")
    daily_walk = Task("Daily walk", "walk", 20, pet=biscuit, recurrence="daily",
                      preferred_time=time(7, 0))
    weekly_bath = Task("Weekly bath", "grooming", 40, pet=biscuit, recurrence="weekly")
    for t in (daily_walk, weekly_bath):
        t.mark_complete()
        nxt = t.next_occurrence
        print(f"  {t.name} ({t.recurrence}): due {t.due_date} -> "
              f"next due {nxt.due_date} [{nxt.status}]")

    # --- The full plan, as before ---
    # One scheduler for the whole household — pets share the same time budget.
    scheduler = Scheduler(owner, tasks)

    # Detect time clashes before planning (same pet or across pets). The plan
    # below resolves them by dropping the lower-priority task of each pair.
    # check_conflicts returns a ready-to-print message (or "" when all clear).
    print("\nConflict check (check_conflicts):")
    print(scheduler.check_conflicts() or "  (no conflicts)")

    scheduler.generate_plan(period="daily")

    print()
    print(scheduler)
    print()
    print(scheduler.explain())


if __name__ == "__main__":
    main()
