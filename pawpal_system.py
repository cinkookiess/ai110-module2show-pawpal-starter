"""PawPal+ — pet care scheduling system.

Skeleton generated from diagrams/uml.mmd. Classes, attributes, and method
stubs only; implementation is left for later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time


@dataclass
class Owner:
    """Represents the pet owner and their scheduling constraints/preferences."""

    name: str
    available_minutes: int
    preferred_start_time: time
    priority_weights: dict[str, int] = field(default_factory=dict)

    def get_priority_weight(self, category: str) -> int:
        """Lookup helper used by Scheduler."""
        raise NotImplementedError


@dataclass
class Pet:
    """Represents the pet being cared for."""

    name: str
    species: str
    owner: Owner
    breed: str = ""
    age: int | None = None

    def __str__(self) -> str:
        raise NotImplementedError


@dataclass
class Task:
    """A single pet care task, including medication tasks (flattened, no subclass)."""

    name: str
    category: str  # "walk", "feed", "medication", "enrichment", "grooming"
    duration_minutes: int
    priority: str = "medium"  # "low", "medium", "high"
    recurrence: str = "one_time"  # "daily", "weekly", "one_time"
    preferred_time: time | None = None
    is_time_critical: bool = False  # True for medication

    # Medication-only fields (used when category == "medication")
    dosage: str = ""
    times_per_day: int = 1
    dose_times: list[time] = field(default_factory=list)

    def __repr__(self) -> str:
        raise NotImplementedError

    def conflicts_with(self, other: Task) -> bool:
        """Checks overlapping preferred_time."""
        raise NotImplementedError

    def expand_doses(self) -> list[dict]:
        """If medication with times_per_day > 1, returns one entry per dose time;
        otherwise returns a single entry."""
        raise NotImplementedError


class Scheduler:
    """Takes tasks + owner constraints, builds and stores a plan, and can
    explain/display it."""

    def __init__(self, owner: Owner, pet: Pet, tasks: list[Task]) -> None:
        self.owner: Owner = owner
        self.pet: Pet = pet
        self.tasks: list[Task] = tasks
        self.scheduled: list[dict] = []  # each dict: task, start_time, end_time
        self.excluded: list[Task] = []  # tasks that didn't fit in available time
        self.total_time_used: int = 0  # sum of scheduled durations

    def generate_plan(self, period: str = "daily") -> None:
        """Main entry point — populates scheduled, excluded, total_time_used."""
        raise NotImplementedError

    def sort_by_priority(self) -> list[Task]:
        """Uses owner.priority_weights."""
        raise NotImplementedError

    def filter_by_available_time(self) -> list[Task]:
        """Drops tasks once owner.available_minutes is exhausted."""
        raise NotImplementedError

    def resolve_conflicts(self) -> list[Task]:
        """Handles overlapping preferred_time values."""
        raise NotImplementedError

    def explain(self) -> str:
        """Human-readable reasoning: why tasks were included/excluded/ordered."""
        raise NotImplementedError

    def __str__(self) -> str:
        """Full formatted plan for display."""
        raise NotImplementedError
