"""PawPal+ — pet care scheduling system.

An Owner has one or more Pets; each Task belongs to a Pet. A single Scheduler
plans all of an owner's tasks against one shared daily time budget, resolving
time conflicts and dropping lower-priority tasks that don't fit.
"""

from __future__ import annotations

from datetime import time


def _to_minutes(t):
    """Convert a datetime.time into minutes since midnight, so times can be
    compared and added with plain arithmetic (time itself doesn't support it)."""
    return t.hour * 60 + t.minute


def _from_minutes(total):
    """Inverse of _to_minutes: turn minutes-since-midnight back into a time.
    Wraps at 24h so end-of-day arithmetic never raises."""
    total %= 24 * 60
    return time(total // 60, total % 60)


class Owner:
    """Represents the pet owner and their scheduling constraints/preferences."""

    def __init__(self, name, available_minutes, preferred_start_time,
                 priority_weights=None):
        self.name = name
        self.available_minutes = available_minutes    # total time budget for the day
        self.preferred_start_time = preferred_start_time
        # Which task categories matter most. Default to {} — but build it inside
        # __init__ so every Owner gets its own dict, not one shared across all.
        self.priority_weights = priority_weights if priority_weights is not None else {}
        self.pets = []  # every Pet this owner cares for

    def add_pet(self, pet):
        """Register a pet with this owner (and set the pet's back-reference).

        Idempotent — adding the same pet twice is a no-op, so the owner never
        ends up with duplicates.
        """
        if pet not in self.pets:
            self.pets.append(pet)
            pet.owner = self
        return pet

    def remove_pet(self, pet):
        """Remove a pet from this owner. Safe to call if it isn't there."""
        if pet in self.pets:
            self.pets.remove(pet)
            pet.owner = None
        return pet

    def get_priority_weight(self, category):
        """Lookup helper used by Scheduler.

        Returns the weight the owner assigns to `category`, or 0 if they never
        set one (so an unlisted category just means "no special priority"
        instead of crashing).
        """
        return self.priority_weights.get(category, 0)


class Pet:
    """Represents the pet being cared for."""

    def __init__(self, name, species, owner=None, breed="", age=None):
        self.name = name
        self.species = species
        self.owner = owner            # reference back to the Owner (may be set later)
        self.breed = breed            # optional
        self.age = age                # optional
        self.tasks = []               # this pet's care tasks
        # Keep the owner's pet list in sync when an owner is given up front.
        if owner is not None:
            owner.add_pet(self)

    def add_task(self, task):
        """Attach a task to this pet (and set the task's back-reference).

        Idempotent, so adding the same task twice won't inflate the count.
        """
        if task not in self.tasks:
            self.tasks.append(task)
            task.pet = self
        return task

    def remove_task(self, task):
        """Remove a task from this pet. Safe to call if it isn't there."""
        if task in self.tasks:
            self.tasks.remove(task)
            task.pet = None
        return task

    def __str__(self):
        # "Biscuit (Golden Retriever)" when a breed is known, otherwise fall
        # back to the species so it never reads "Biscuit ()".
        descriptor = self.breed if self.breed else self.species
        return f"{self.name} ({descriptor})"


class Task:
    """A single pet care task, including medication tasks (flattened, no subclass)."""

    def __init__(self, name, category, duration_minutes, pet=None, priority="medium",
                 recurrence="one_time", preferred_time=None, is_time_critical=False,
                 dosage="", times_per_day=1, dose_times=None):
        self.name = name
        self.pet = pet                        # which Pet this task is for
        self.category = category              # walk, feed, medication, enrichment, grooming
        self.duration_minutes = duration_minutes
        self.priority = priority              # "low", "medium", "high"
        self.recurrence = recurrence          # "daily", "weekly", "one_time"
        self.preferred_time = preferred_time  # optional
        self.is_time_critical = is_time_critical  # True for medication

        # Medication-only fields (used when category == "medication")
        self.dosage = dosage
        self.times_per_day = times_per_day
        # Own list per Task, not one shared across all (same reason as Owner above).
        self.dose_times = dose_times if dose_times is not None else []

        self.status = "pending"   # "pending" until mark_complete() is called
        # Keep the pet's task list in sync when a pet is given up front.
        if pet is not None:
            pet.add_task(self)

    def mark_complete(self):
        """Mark this task done. Returns the new status for convenience."""
        self.status = "complete"
        return self.status

    def __repr__(self):
        # Developer-facing view: enough to identify the task in test output.
        return (f"Task(name={self.name!r}, category={self.category!r}, "
                f"duration_minutes={self.duration_minutes})")

    def conflicts_with(self, other):
        """True if this task's time range overlaps other's.

        Compares [preferred_time, preferred_time + duration_minutes) against the
        same range on `other` — not just equal start times — so back-to-back
        tasks that actually collide are detected.
        """
        # A task with no fixed time isn't placed yet, so it can't clash.
        if self.preferred_time is None or other.preferred_time is None:
            return False

        start_self = _to_minutes(self.preferred_time)
        end_self = start_self + self.duration_minutes
        start_other = _to_minutes(other.preferred_time)
        end_other = start_other + other.duration_minutes

        # Ranges overlap when each one starts before the other ends.
        return start_self < end_other and start_other < end_self

    def expand_doses(self):
        """If medication with times_per_day > 1, returns one entry per dose time;
        otherwise returns a single entry."""
        is_multi_dose_med = (
            self.category == "medication"
            and self.times_per_day > 1
            and self.dose_times
        )
        if is_multi_dose_med:
            return [
                {"name": self.name, "time": dose_time, "dosage": self.dosage,
                 "duration_minutes": self.duration_minutes}
                for dose_time in self.dose_times
            ]
        # Everything else — non-medication, or a once-a-day dose — is one entry.
        return [{"name": self.name, "time": self.preferred_time,
                 "dosage": self.dosage, "duration_minutes": self.duration_minutes}]


class ScheduledSlot:
    """One placed task on the plan timeline. Replaces the loose dict so the
    slot's shape is clear and weekly plans have a `day` to key on."""

    def __init__(self, task, start_time, end_time, day="daily"):
        self.task = task              # the Task being placed
        self.start_time = start_time
        self.end_time = end_time
        self.day = day                # "daily" or a weekday name for weekly plans


class Scheduler:
    """Takes an owner's tasks (across all their pets) and one shared time
    budget, builds a single plan, and can explain/display it.

    Because there is one owner doing the work, tasks for different pets compete
    for the same minutes and can conflict in time with each other.
    """

    def __init__(self, owner, tasks):
        # Inputs from the caller
        self.owner = owner
        self.tasks = tasks

        # Results, filled in by generate_plan()
        self.scheduled = []       # list of ScheduledSlot
        self.excluded = []        # tasks that didn't fit in available time
        self.total_time_used = 0  # sum of scheduled durations

    def generate_plan(self, period="daily"):
        """Main entry point — populates scheduled, excluded, total_time_used.

        Pipeline order (deliberate):
          1. resolve_conflicts()        — drop/shift overlaps first, so the time
                                          budget is never spent on tasks that
                                          later get removed for conflicting.
          2. sort_by_priority()         — order what remains by owner weights.
          3. filter_by_available_time() — spend the budget on the sorted list.
        """
        # Reset any results from a previous run so re-planning is idempotent.
        self.scheduled = []
        self.total_time_used = 0

        kept = self.resolve_conflicts(self.tasks)
        ordered = self.sort_by_priority(kept)
        fitting = self.filter_by_available_time(ordered)

        # Place the survivors on the clock. Tasks with a preferred_time land
        # there; flexible ones fall in sequentially after whatever came before.
        clock = _to_minutes(self.owner.preferred_start_time)
        for task in fitting:
            for dose in task.expand_doses():
                start = _to_minutes(dose["time"]) if dose["time"] else clock
                end = start + dose["duration_minutes"]
                self.scheduled.append(
                    ScheduledSlot(task, _from_minutes(start), _from_minutes(end),
                                  day=period)
                )
                self.total_time_used += dose["duration_minutes"]
                clock = max(clock, end)  # next flexible task starts after this

        # Whatever never made it onto the plan is excluded (conflict or no time).
        placed = {id(slot.task) for slot in self.scheduled}
        self.excluded = [t for t in self.tasks if id(t) not in placed]

    def sort_by_priority(self, tasks=None):
        """Order tasks by owner.priority_weights, highest weight first.

        sorted() is stable, so tasks of equal weight keep their original order.
        """
        tasks = self.tasks if tasks is None else tasks
        return sorted(
            tasks,
            key=lambda t: self.owner.get_priority_weight(t.category),
            reverse=True,
        )

    def filter_by_available_time(self, tasks=None):
        """Keep tasks until owner.available_minutes is exhausted.

        Two rules before dropping:
          - Expand medications into per-dose entries first (expand_doses), so a
            times_per_day=3 med counts as 3x duration, not 1x.
          - Never drop an is_time_critical task for lack of time; exclude a
            non-critical task instead.
        """
        tasks = self.tasks if tasks is None else tasks
        budget = self.owner.available_minutes
        used = 0
        fitting = []
        for task in tasks:
            cost = sum(d["duration_minutes"] for d in task.expand_doses())
            if task.is_time_critical or used + cost <= budget:
                fitting.append(task)   # time-critical is kept even over budget
                used += cost
            # else: no room — leave it out (generate_plan records it as excluded)
        return fitting

    def resolve_conflicts(self, tasks=None):
        """Drop overlapping tasks, keeping the higher-priority one of each pair.

        See Task.conflicts_with for what "overlap" means (time ranges, not just
        equal start times).
        """
        tasks = self.tasks if tasks is None else tasks
        kept = []
        for task in tasks:
            clash = next((k for k in kept if task.conflicts_with(k)), None)
            if clash is None:
                kept.append(task)
            elif self._weight(task) > self._weight(clash):
                kept.remove(clash)     # new task wins; evict the one it beat
                kept.append(task)
            # else: existing task wins, so skip the new one
        return kept

    def _weight(self, task):
        """Shorthand for the owner's priority weight of a task's category."""
        return self.owner.get_priority_weight(task.category)

    @staticmethod
    def _pet_name(task):
        """Display name of a task's pet, or '?' if it isn't attached to one."""
        return task.pet.name if task.pet is not None else "?"

    def explain(self):
        """Human-readable reasoning: why tasks were included/excluded/ordered."""
        lines = ["Schedule reasoning:"]
        lines.append(f"  Budget: {self.owner.available_minutes} min "
                     f"(used {self.total_time_used}).")
        if self.scheduled:
            lines.append("  Included (in priority order):")
            for slot in self.scheduled:
                lines.append(f"    - [{self._pet_name(slot.task)}] {slot.task.name} "
                             f"at {slot.start_time:%H:%M} "
                             f"[weight {self._weight(slot.task)}]")
        if self.excluded:
            lines.append("  Excluded (conflicted or out of time):")
            for task in self.excluded:
                lines.append(f"    - [{self._pet_name(task)}] {task.name}")
        return "\n".join(lines)

    def __str__(self):
        """Full formatted plan for display, grouped by pet."""
        if not self.scheduled:
            return "Today's Schedule: (nothing scheduled)"

        header = (f"Today's Schedule - {len(self.scheduled)} item(s), "
                  f"{self.total_time_used} min:")

        # Group slots by pet, then show each pet's items in time order.
        by_pet = {}
        for slot in self.scheduled:
            by_pet.setdefault(slot.task.pet, []).append(slot)

        lines = [header]
        for pet, slots in by_pet.items():
            lines.append(f"  {pet if pet is not None else 'Unassigned'}:")
            for slot in sorted(slots, key=lambda s: s.start_time):
                lines.append(f"    {slot.start_time:%H:%M}-{slot.end_time:%H:%M}  "
                             f"{slot.task.name}")
        return "\n".join(lines)
