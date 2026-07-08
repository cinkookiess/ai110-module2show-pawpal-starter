"""PawPal+ — pet care scheduling system.

An Owner has one or more Pets; each Task belongs to a Pet. A single Scheduler
plans all of an owner's tasks against one shared daily time budget, resolving
time conflicts and dropping lower-priority tasks that don't fit.
"""

from __future__ import annotations

from datetime import date, time, timedelta


# Rank for a task's own low/medium/high priority. Used as a tiebreaker after
# the owner's per-category weight, so two tasks in the same category order by
# how urgent the owner marked each one.
_PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}


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
        """Create an owner and their daily scheduling constraints.

        Args:
            name: The owner's display name.
            available_minutes: Total time budget (minutes) for the day's plan.
            preferred_start_time: datetime.time the day's plan should begin at.
            priority_weights: Optional {category: weight} mapping of which task
                categories matter most. Defaults to an empty dict (every
                category weight 0), built per-instance so owners never share one.
        """
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
        """Create a pet, optionally registering it with an owner up front.

        Args:
            name: The pet's name.
            species: e.g. "dog", "cat".
            owner: Optional Owner to attach to; when given, the pet is added to
                that owner's pet list automatically.
            breed: Optional breed string (shown by __str__ when present).
            age: Optional age.
        """
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
                 dosage="", times_per_day=1, dose_times=None, due_date=None):
        """Create a pet care task (medication fields apply only when
        category == "medication").

        Args:
            name: Task title, e.g. "Morning walk".
            category: One of "walk", "feed", "medication", "enrichment",
                "grooming".
            duration_minutes: How long the task takes.
            pet: Optional Pet this task is for; when given, the task is added to
                that pet's task list automatically.
            priority: "low", "medium", or "high" (tiebreaker within a category).
            recurrence: "one_time", "daily", or "weekly".
            preferred_time: Optional datetime.time to start at; None means
                flexible (the scheduler slots it into a gap).
            is_time_critical: When True the task is never dropped for lack of
                time (used for medication).
            dosage: Medication dose description (medication only).
            times_per_day: Number of doses per day (medication only).
            dose_times: List of datetime.time dose times (medication only);
                copied per-instance so tasks never share one list.
            due_date: Calendar date the task is due; defaults to today.
        """
        self.name = name
        self.pet = pet                        # which Pet this task is for
        self.category = category              # walk, feed, medication, enrichment, grooming
        self.duration_minutes = duration_minutes
        self.priority = priority              # "low", "medium", "high"
        self.recurrence = recurrence          # "daily", "weekly", "one_time"
        self.preferred_time = preferred_time  # optional
        self.is_time_critical = is_time_critical  # True for medication
        # Calendar day this task is due. Defaults to today when not given (built
        # here, not as a default arg, so it's evaluated per-Task, not once at
        # import). mark_complete() advances it for the next occurrence.
        self.due_date = due_date if due_date is not None else date.today()

        # Medication-only fields (used when category == "medication")
        self.dosage = dosage
        self.times_per_day = times_per_day
        # Own list per Task, not one shared across all (same reason as Owner above).
        self.dose_times = dose_times if dose_times is not None else []

        self.status = "pending"   # "pending" until mark_complete() is called
        # Set by mark_complete() on a recurring task: the fresh copy created
        # for the next occurrence. Stays None for one-time tasks.
        self.next_occurrence = None
        # Keep the pet's task list in sync when a pet is given up front.
        if pet is not None:
            pet.add_task(self)

    def mark_complete(self):
        """Mark this task done, spawning the next occurrence if it recurs.

        If the task recurs ("daily" or "weekly"), completing it also spawns a
        fresh pending copy for the next occurrence — attached to the same pet
        and reachable via self.next_occurrence. The spawn only happens on the
        transition from pending to complete, so marking an already-complete
        task again won't pile up duplicates.

        Returns:
            str: The new status, always "complete".
        """
        was_pending = self.status != "complete"
        self.status = "complete"
        if was_pending and self.recurrence in ("daily", "weekly"):
            self.next_occurrence = self._spawn_next_occurrence()
        return self.status

    def _spawn_next_occurrence(self):
        """Create a fresh pending copy of this task for its next occurrence,
        carrying over every defining field with the due date rolled forward.

        The new due date is this task's due date plus one interval: +1 day for
        "daily", +7 days for "weekly". timedelta handles month/year rollovers
        correctly (e.g. Jan 31 + 1 day -> Feb 1), so it's safe near boundaries.

        Mutable fields (dose_times) are copied so the new task doesn't share
        state with this one. Passing the same pet auto-registers the copy on
        that pet's task list, so it shows up as an upcoming task right away.

        Returns:
            Task: A new pending Task identical to this one but with due_date
                rolled forward by the recurrence interval.
        """
        step = timedelta(days=7) if self.recurrence == "weekly" else timedelta(days=1)
        next_due = self.due_date + step
        return Task(
            self.name, self.category, self.duration_minutes, pet=self.pet,
            priority=self.priority, recurrence=self.recurrence,
            preferred_time=self.preferred_time,
            is_time_critical=self.is_time_critical,
            dosage=self.dosage, times_per_day=self.times_per_day,
            dose_times=list(self.dose_times), due_date=next_due,
        )

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
        """Create one placed slot on the plan timeline.

        Args:
            task: The Task being placed.
            start_time: datetime.time the slot starts.
            end_time: datetime.time the slot ends.
            day: "daily" or a weekday name (for weekly plans) to key on.
        """
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
        """Create a scheduler for one owner and a set of candidate tasks.

        Args:
            owner: The Owner whose constraints (budget, start time, priority
                weights) drive planning.
            tasks: List of candidate Tasks (typically all tasks across all the
                owner's pets).

        The result attributes (scheduled, excluded, total_time_used) start empty
        and are populated by generate_plan().
        """
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

        # Expand into placeable (task, dose) entries. Fixed entries have a
        # concrete time; flexible ones (no preferred_time) get slotted around
        # them below.
        entries = [(task, dose) for task in fitting for dose in task.expand_doses()]
        fixed = sorted(
            (e for e in entries if e[1]["time"] is not None),
            key=lambda e: _to_minutes(e[1]["time"]),
        )
        flexible = [e for e in entries if e[1]["time"] is None]

        # Place fixed entries at their requested time and record the intervals
        # they occupy, so flexible tasks can be fit into the gaps around them.
        occupied = []
        for task, dose in fixed:
            start = _to_minutes(dose["time"])
            self._place(task, start, dose["duration_minutes"], period, occupied)

        # Slot each flexible entry into the earliest free gap at or after the
        # owner's preferred start — filling holes between fixed tasks instead
        # of always piling up at the end of the day.
        day_start = _to_minutes(self.owner.preferred_start_time)
        for task, dose in flexible:
            start = self._earliest_gap(day_start, dose["duration_minutes"], occupied)
            self._place(task, start, dose["duration_minutes"], period, occupied)

        # Whatever never made it onto the plan is excluded (conflict or no time).
        placed = {id(slot.task) for slot in self.scheduled}
        self.excluded = [t for t in self.tasks if id(t) not in placed]

    def sort_by_priority(self, tasks=None):
        """Order tasks by owner category weight first, then the task's own
        low/medium/high priority, highest first.

        sorted() is stable, so tasks that tie on both keep their original order.
        """
        tasks = self.tasks if tasks is None else tasks
        return sorted(tasks, key=self._weight, reverse=True)

    @staticmethod
    def sort_by_time(tasks):
        """Order tasks chronologically by their preferred_time (earliest first).

        A staticmethod because it depends only on the tasks passed in, not on
        any owner/scheduler state — call it as Scheduler.sort_by_time(tasks)
        without building a Scheduler.

        preferred_time is a datetime.time, which already compares
        chronologically, so the lambda just hands each task's time to sorted().
        Tasks with no preferred_time (flexible) sort to the end via time.max,
        rather than crashing on a None comparison.

        Claude Note: if preferred_time were instead an "HH:MM" *string*, the very same
        lambda would still work — zero-padded "HH:MM" sorts lexicographically in
        the same order as chronologically ("08:30" < "15:00").

        Args:
            tasks: The tasks to order.

        Returns:
            list[Task]: A new list sorted by preferred_time ascending, with
                flexible (no preferred_time) tasks placed last.
        """
        return sorted(tasks, key=lambda t: t.preferred_time or time.max)

    @staticmethod
    def filter_tasks(tasks, status=None, pet_name=None):
        """Return the subset of `tasks` matching the given filters.

        Args:
            tasks: The tasks to filter.
            status: If given, keep only tasks whose .status equals this
                ("pending" or "complete").
            pet_name: If given, keep only tasks whose pet has this name
                (case-insensitive; a task with no pet never matches).

        Returns:
            list[Task]: The tasks matching every supplied filter. Filters left
                as None are ignored, so the two can be combined (ANDed) or used
                on their own; passing neither returns all tasks.

        Like sort_by_time this is a staticmethod — call it as
        Scheduler.filter_tasks(tasks, status="complete").
        """
        result = []
        for task in tasks:
            if status is not None and task.status != status:
                continue
            if pet_name is not None:
                name = task.pet.name if task.pet is not None else ""
                if name.lower() != pet_name.lower():
                    continue
            result.append(task)
        return result

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

    def find_conflicts(self, tasks=None):
        """Detect every pair of tasks whose times overlap — whether they belong
        to the same pet or different ones (one owner can't be two places at
        once, so cross-pet clashes matter too).

        Uses Task.conflicts_with (overlapping [start, start + duration) ranges,
        not just equal start times). Unlike resolve_conflicts, this only
        *reports* clashes — it drops nothing — so callers can warn the owner.
        Only tasks with a fixed preferred_time can clash here: a task with no
        set time isn't pinned to a moment, so conflicts_with treats it as
        unplaced. (generate_plan's gap-filling then keeps flexible tasks from
        overlapping once they're actually placed.)

        Args:
            tasks: The tasks to check; defaults to self.tasks.

        Returns:
            list[tuple[Task, Task]]: Every (task_a, task_b) pair whose times
                overlap. Each pair is reported once.
        """
        tasks = self.tasks if tasks is None else tasks
        conflicts = []
        # Compare each task only with those after it, so each pair is checked
        # once (and no task is compared against itself).
        for i, task_a in enumerate(tasks):
            for task_b in tasks[i + 1:]:
                if task_a.conflicts_with(task_b):
                    conflicts.append((task_a, task_b))
        return conflicts

    def describe_conflicts(self, tasks=None):
        """Human-readable version of find_conflicts: one line per clashing pair,
        naming each task's pet and time.

        Args:
            tasks: The tasks to check; defaults to self.tasks.

        Returns:
            list[str]: One description per clashing pair, or [] when nothing
                overlaps.
        """
        lines = []
        for task_a, task_b in self.find_conflicts(tasks):
            lines.append(
                f"[{self._pet_name(task_a)}] {task_a.name} "
                f"({task_a.preferred_time:%H:%M}) overlaps "
                f"[{self._pet_name(task_b)}] {task_b.name} "
                f"({task_b.preferred_time:%H:%M})"
            )
        return lines

    def check_conflicts(self, tasks=None):
        """Lightweight conflict check that always returns a warning *message*
        (a string) instead of raising — safe to drop straight into a UI label,
        a log line, or a print without any try/except at the call site.

        The message is plain ASCII (no emoji) so it prints safely to any
        console — a warning that itself crashed on encoding would defeat the
        point. UIs like Streamlit add their own warning icon.

        Args:
            tasks: The tasks to check; defaults to self.tasks.

        Returns:
            str: One of —
              - "" (empty, falsy) when nothing overlaps, so callers can do
                `if scheduler.check_conflicts(): ...`;
              - a "WARNING: N time conflict(s) detected:" summary with one
                indented line per clashing pair, when there are conflicts;
              - a single "WARNING: Could not check ..." line if detection itself
                errors, so a display helper can never crash the app.
        """
        try:
            lines = self.describe_conflicts(tasks)
        except Exception as exc:  # never let conflict-checking take down the caller
            return f"WARNING: Could not check for conflicts: {exc}"
        if not lines:
            return ""
        header = f"WARNING: {len(lines)} time conflict(s) detected:"
        return "\n".join([header] + [f"  - {line}" for line in lines])

    def resolve_conflicts(self, tasks=None):
        """Keep the highest-priority task of each overlapping group, dropping
        the rest. See Task.conflicts_with for what "overlap" means (time ranges,
        not just equal start times).

        Processing highest-priority first (via _weight) means a task, once kept,
        is never evicted — so a task is added only when it clashes with nothing
        already kept, and no overlaps can survive. Ties keep the first task seen
        (sorted() is stable), matching the original input order within a weight.

        Args:
            tasks: The tasks to resolve; defaults to self.tasks.

        Returns:
            list[Task]: The kept tasks, in descending priority order, with no
                two overlapping in time.
        """
        tasks = self.tasks if tasks is None else tasks
        kept = []
        for task in sorted(tasks, key=self._weight, reverse=True):
            if not any(task.conflicts_with(k) for k in kept):
                kept.append(task)
        return kept

    def _weight(self, task):
        """Priority key for a task: the owner's category weight first, then the
        task's own low/medium/high priority as a tiebreaker.

        Args:
            task: The task to score.

        Returns:
            tuple[int, int]: (owner category weight, priority rank), so `>` and
                sorted() compare category weight first and fall back to priority
                only when categories tie.
        """
        return (self.owner.get_priority_weight(task.category),
                _PRIORITY_RANK.get(task.priority, 1))

    def _place(self, task, start, duration, period, occupied):
        """Record one slot on the plan and mark the time as occupied.

        Appends a ScheduledSlot, adds the duration to the running total, and
        marks [start, end) occupied so later (flexible) placements avoid it.

        Args:
            task: The Task being placed.
            start: Start time in minutes since midnight.
            duration: Length of the task in minutes.
            period: "daily" or a weekday name, stored on the slot.
            occupied: List of (start, end) intervals already taken; appended to
                in place.
        """
        end = start + duration
        self.scheduled.append(
            ScheduledSlot(task, _from_minutes(start), _from_minutes(end), day=period)
        )
        self.total_time_used += duration
        occupied.append((start, end))

    @staticmethod
    def _earliest_gap(earliest, duration, occupied):
        """Earliest start time at or after `earliest` where a `duration`-long
        task fits without overlapping any interval in `occupied`.

        Walks the busy intervals in time order: a task fits in front of the
        next busy block if there's room, otherwise we try again after it.

        Args:
            earliest: Earliest allowed start, in minutes since midnight.
            duration: Length of the task to place, in minutes.
            occupied: List of (start, end) busy intervals, in minutes.

        Returns:
            int: The earliest start (minutes since midnight) at or after
                `earliest` where the task fits without overlapping a busy block.
        """
        start = earliest
        for busy_start, busy_end in sorted(occupied):
            if busy_end <= start:
                continue                     # busy block is already behind us
            if start + duration <= busy_start:
                return start                 # fits in the gap before this block
            start = busy_end                 # otherwise start after it and retry
        return start

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
                weight = self.owner.get_priority_weight(slot.task.category)
                lines.append(f"    - [{self._pet_name(slot.task)}] {slot.task.name} "
                             f"at {slot.start_time:%H:%M} "
                             f"[weight {weight}, {slot.task.priority}]")
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
