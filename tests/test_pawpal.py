"""Tests for PawPal+ core behaviors."""

from datetime import time

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
