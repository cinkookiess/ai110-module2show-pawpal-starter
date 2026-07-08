"""Tests for PawPal+ core behaviors."""

from datetime import time

from pawpal_system import Owner, Pet, Task


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
