"""Tests for PawPal+ core behaviors."""

from datetime import date, time, timedelta

from pawpal_system import Owner, Pet, Task, Scheduler


def test_mark_complete_changes_status():
    """Task Completion: mark_complete() flips the task's status to complete."""
    task = Task("Morning walk", "walk", 30)

    assert task.status == "pending"      # starts out not done
    task.mark_complete()
    assert task.status == "complete"     # mark_complete() changed it


def test_adding_task_increases_pet_task_count():
    """Task Addition: add_task() grows that pet's task count by one."""
    owner = Owner("Sam", 120, time(8, 0))
    pet = Pet("Biscuit", "Dog", owner)

    before = len(pet.tasks)              # no tasks yet
    pet.add_task(Task("Feed", "feed", 15))
    after = len(pet.tasks)

    assert after == before + 1


def test_resolve_conflicts_leaves_no_overlaps():
    """Conflict resolution: no two kept tasks may overlap, even when one task
    conflicts with several others at once.

    Regression for a greedy bug where a high-priority task evicted only the
    first task it clashed with, leaving it overlapping a second survivor. Here
    B (08:20-08:50) overlaps BOTH A (08:00-08:30) and C (08:40-09:10), while A
    and C don't overlap each other. Only B (highest priority) should remain.
    """
    owner = Owner("Sam", 300, time(8, 0),
                  priority_weights={"walk": 5, "feed": 5, "medication": 10})
    pet = Pet("Biscuit", "Dog", owner)
    a = Task("A", "walk", 30, pet=pet, priority="low", preferred_time=time(8, 0))
    c = Task("C", "feed", 30, pet=pet, priority="low", preferred_time=time(8, 40))
    b = Task("B", "medication", 30, pet=pet, priority="high",
             preferred_time=time(8, 20))

    kept = Scheduler(owner, [a, c, b]).resolve_conflicts()

    # The highest-priority task wins its whole overlapping group...
    assert kept == [b]
    # ...and nothing left in `kept` still conflicts with anything else.
    residual = [(x, y) for i, x in enumerate(kept)
                for y in kept[i + 1:] if x.conflicts_with(y)]
    assert residual == []


# --------------------------------------------------------------------------
# Sorting correctness
# --------------------------------------------------------------------------

def test_sort_by_time_returns_chronological_order():
    """Sorting Correctness: sort_by_time() returns tasks earliest-first,
    regardless of the order they were passed in."""
    noon = Task("Lunch feed", "feed", 15, preferred_time=time(12, 0))
    morning = Task("Morning walk", "walk", 30, preferred_time=time(8, 0))
    evening = Task("Evening walk", "walk", 30, preferred_time=time(18, 30))

    ordered = Scheduler.sort_by_time([noon, evening, morning])

    assert ordered == [morning, noon, evening]
    # Confirm the underlying times really are ascending.
    times = [t.preferred_time for t in ordered]
    assert times == sorted(times)


def test_sort_by_time_places_flexible_tasks_last():
    """Sorting Correctness (edge case): tasks with no preferred_time sort to
    the end via time.max instead of crashing on a None comparison."""
    fixed = Task("Vet visit", "grooming", 60, preferred_time=time(9, 0))
    flexible = Task("Play", "enrichment", 20)  # no preferred_time

    ordered = Scheduler.sort_by_time([flexible, fixed])

    assert ordered == [fixed, flexible]


# --------------------------------------------------------------------------
# Recurrence logic
# --------------------------------------------------------------------------

def test_daily_task_completion_spawns_next_day_occurrence():
    """Recurrence Logic: completing a daily task creates a fresh pending task
    due the following day, attached to the same pet."""
    owner = Owner("Sam", 120, time(8, 0))
    pet = Pet("Biscuit", "Dog", owner)
    task = Task("Morning walk", "walk", 30, pet=pet, recurrence="daily",
                due_date=date(2026, 7, 7))

    task.mark_complete()
    nxt = task.next_occurrence

    assert nxt is not None                       # a next occurrence was spawned
    assert nxt.status == "pending"               # and it's not yet done
    assert nxt.due_date == date(2026, 7, 8)      # rolled forward exactly one day
    assert nxt.pet is pet                         # same pet
    assert nxt in pet.tasks                       # and registered on that pet
    assert nxt is not task                         # a distinct object, not itself


def test_weekly_task_completion_rolls_forward_seven_days():
    """Recurrence Logic: a weekly task's next occurrence is due +7 days."""
    task = Task("Weekly grooming", "grooming", 45, recurrence="weekly",
                due_date=date(2026, 7, 7))

    task.mark_complete()

    assert task.next_occurrence.due_date == date(2026, 7, 7) + timedelta(days=7)


def test_one_time_task_does_not_recur():
    """Recurrence Logic (edge case): a one_time task spawns no next occurrence."""
    task = Task("Nail trim", "grooming", 20, recurrence="one_time")

    task.mark_complete()

    assert task.next_occurrence is None


def test_marking_complete_twice_does_not_pile_up_occurrences():
    """Recurrence Logic (edge case): re-marking an already-complete task must
    not spawn a second copy (spawn only fires on the pending->complete edge)."""
    pet = Pet("Biscuit", "Dog")
    task = Task("Feed", "feed", 15, pet=pet, recurrence="daily")

    task.mark_complete()
    first = task.next_occurrence
    task.mark_complete()  # already complete — should be a no-op for spawning

    assert task.next_occurrence is first          # unchanged
    # The pet gained exactly one new task (the original + one spawned copy).
    assert len(pet.tasks) == 2


# --------------------------------------------------------------------------
# Conflict detection
# --------------------------------------------------------------------------

def test_find_conflicts_flags_duplicate_times():
    """Conflict Detection: two tasks at the exact same time are flagged as a
    single conflicting pair."""
    owner = Owner("Sam", 300, time(8, 0))
    pet = Pet("Biscuit", "Dog", owner)
    a = Task("Walk", "walk", 30, pet=pet, preferred_time=time(9, 0))
    b = Task("Feed", "feed", 30, pet=pet, preferred_time=time(9, 0))

    conflicts = Scheduler(owner, [a, b]).find_conflicts()

    assert len(conflicts) == 1
    assert set(conflicts[0]) == {a, b}


def test_check_conflicts_reports_duplicate_times_as_warning():
    """Conflict Detection: check_conflicts() surfaces overlaps as a non-empty
    warning string (and stays empty when nothing clashes)."""
    owner = Owner("Sam", 300, time(8, 0))
    pet = Pet("Biscuit", "Dog", owner)
    a = Task("Walk", "walk", 30, pet=pet, preferred_time=time(9, 0))
    b = Task("Feed", "feed", 30, pet=pet, preferred_time=time(9, 0))
    scheduler = Scheduler(owner, [a, b])

    warning = scheduler.check_conflicts()
    assert warning.startswith("WARNING")
    assert "1 time conflict" in warning

    # No conflict once the times no longer overlap.
    b.preferred_time = time(10, 0)
    assert scheduler.check_conflicts() == ""


def test_back_to_back_tasks_do_not_conflict():
    """Conflict Detection (edge case): tasks whose ranges only touch at the
    boundary (08:00-08:30 and 08:30-09:00) must NOT be flagged."""
    a = Task("Walk", "walk", 30, preferred_time=time(8, 0))
    b = Task("Feed", "feed", 30, preferred_time=time(8, 30))

    assert a.conflicts_with(b) is False


def test_flexible_task_never_conflicts():
    """Conflict Detection (edge case): a task with no preferred_time isn't
    pinned to a moment, so it can't clash."""
    fixed = Task("Walk", "walk", 30, preferred_time=time(8, 0))
    flexible = Task("Play", "enrichment", 30)  # no preferred_time

    assert fixed.conflicts_with(flexible) is False


# --------------------------------------------------------------------------
# Time-budget filtering & empty inputs
# --------------------------------------------------------------------------

def test_time_critical_task_kept_even_over_budget():
    """Budget (edge case): an is_time_critical task is never dropped for lack
    of time, even when the budget is already exhausted."""
    owner = Owner("Sam", 30, time(8, 0))
    pet = Pet("Biscuit", "Dog", owner)
    filler = Task("Long walk", "walk", 30, pet=pet, preferred_time=time(8, 0))
    med = Task("Insulin", "medication", 10, pet=pet, is_time_critical=True,
               preferred_time=time(12, 0))

    fitting = Scheduler(owner, [filler, med]).filter_by_available_time([filler, med])

    assert med in fitting  # kept despite pushing past the 30-min budget


def test_generate_plan_with_no_tasks_does_not_crash():
    """Empty input (edge case): planning an owner/pet with no tasks yields an
    empty schedule rather than an error."""
    owner = Owner("Sam", 120, time(8, 0))
    Pet("Biscuit", "Dog", owner)
    scheduler = Scheduler(owner, [])

    scheduler.generate_plan()

    assert scheduler.scheduled == []
    assert scheduler.excluded == []
    assert scheduler.total_time_used == 0
    assert "nothing scheduled" in str(scheduler)
