# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## ✨ Features

PawPal+ implements the following scheduling algorithms (all in `pawpal_system.py`;
see [Smarter Scheduling](#-smarter-scheduling) below for the method-level details):

- **Priority-aware daily planning** — builds a day's plan by running a fixed
  pipeline: resolve conflicts → sort by priority → fit within the time budget →
  place tasks on a timeline (`Scheduler.generate_plan`).
- **Sorting by time** — orders tasks chronologically by preferred time, with
  flexible (no-time) tasks placed last (`Scheduler.sort_by_time`).
- **Sorting by priority** — ranks tasks by the owner's per-category weight
  first, then each task's own low/medium/high priority as a tiebreaker
  (`Scheduler.sort_by_priority`).
- **Conflict warnings** — detects tasks whose time ranges overlap (same pet or
  across pets) and reports each clashing pair without dropping anything, so the
  owner can be warned (`find_conflicts`, `describe_conflicts`, `check_conflicts`).
- **Conflict resolution** — when overlaps exist, keeps the higher-priority task
  of each overlapping group and drops the rest (`resolve_conflicts`).
- **Time-budget filtering** — keeps tasks until the owner's available minutes
  run out, while never dropping a time-critical task such as medication
  (`filter_by_available_time`).
- **Gap-aware placement** — slots flexible tasks into the earliest free gap
  around fixed-time tasks instead of piling them up at the end of the day
  (`_earliest_gap`, `_place`).
- **Daily & weekly recurrence** — completing a recurring task automatically
  spawns the next occurrence with its due date rolled forward (+1 day / +7 days)
  (`Task.mark_complete`, `Task._spawn_next_occurrence`).
- **Multi-dose medication** — expands a medication with several daily doses into
  one scheduled entry per dose time (`Task.expand_doses`).
- **Filtering by pet or status** — returns the subset of tasks matching a
  completion status, a pet name, or both (`Scheduler.filter_tasks`).
- **Plan explanation** — produces human-readable reasoning for why each task was
  included, excluded, or ordered the way it was (`Scheduler.explain`).

## 🧩 Classes

The system is built from four core classes (all in `pawpal_system.py`; see the
UML in [`diagrams/uml.mmd`](diagrams/uml.mmd) and the design notes in
[`reflection.md`](reflection.md)):

- **`Owner`** — the pet owner and their scheduling constraints: name, total
  `available_minutes` for the day, `preferred_start_time`, and per-category
  `priority_weights`. Holds the list of `pets` and knows how to add/remove them.
- **`Pet`** — a single animal being cared for: name, species, optional breed/age,
  a back-reference to its `owner`, and its own list of `tasks` (with
  add/remove methods).
- **`Task`** — one care task (walk, feed, medication, enrichment, grooming),
  including its duration, priority, recurrence, optional preferred time, and
  medication fields. Knows how to `mark_complete()` (spawning the next
  occurrence for recurring tasks), test `conflicts_with()` another task, and
  `expand_doses()` for multi-dose meds.
- **`Scheduler`** — the engine: takes an owner plus all their tasks (across every
  pet) and one shared time budget, then sorts, filters, detects/resolves
  conflicts, and builds an explained daily plan. A small `ScheduledSlot` helper
  represents each placed task on the timeline.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running the app and demo

```bash
# Launch the Streamlit app (the main deliverable):
streamlit run app.py

# Run the terminal demo (end-to-end walkthrough — output shown below):
python main.py

# Run the test suite:
python -m pytest
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

A full sample of the terminal demo's output (`python main.py`) is shown in the
[Sample CLI output](#sample-cli-output-python-mainpy) section below, under
**Demo Walkthrough**.

## 🧪 Testing PawPal+

Run the full test suite from the project root:

```bash
python -m pytest
```

The tests live in `tests/test_pawpal.py` and exercise the core scheduling
behaviors in `pawpal_system.py`. Coverage includes:

- **Task basics** — status flips to `complete`, and `add_task()` grows a pet's
  task list.
- **Sorting correctness** — `sort_by_time()` returns tasks in chronological
  order, with flexible (no-time) tasks placed last.
- **Recurrence logic** — completing a **daily** task spawns a pending copy due
  the next day, **weekly** rolls forward 7 days, `one_time` tasks never recur,
  and re-completing a task doesn't pile up duplicates.
- **Conflict detection** — duplicate/overlapping times are flagged (`find_conflicts`,
  `check_conflicts`), back-to-back tasks that only touch are *not* flagged, and
  flexible tasks never conflict.
- **Conflict resolution** — the highest-priority task wins its overlapping group,
  leaving no residual overlaps.
- **Time-budget filtering** — `is_time_critical` tasks are kept even over budget.
- **Edge cases** — planning an owner/pet with **no tasks** produces an empty
  schedule instead of crashing.

Sample test output (all passing):

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\cynth\Documents\Projects\ai110-module2show-pawpal-starter
plugins: anyio-4.14.1
collected 15 items

tests\test_pawpal.py ...............                                     [100%]

============================= 15 passed in 0.06s ==============================
```

### Confidence Level: ★★★★☆ (4 / 5)

All 15 tests pass and cover the happy paths plus the highest-risk edge cases
(duplicate times, boundary-touching tasks, recurrence rollover, empty input).
Knocking off one star because a few behaviors aren't pinned down yet 
the **midnight-wrap** arithmetic in `_from_minutes` (a task running past 24:00
wraps silently) and **gap-aware placement** of flexible tasks around fixed ones.


## 📐 Smarter Scheduling

Beyond building a basic plan, PawPal+ implements several "smarter" scheduling
behaviors. All scheduling logic lives in `pawpal_system.py`. The table below
maps each feature to the method that implements it; details follow.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Chronological sorting | `Scheduler.sort_by_time()` | Orders tasks by `preferred_time`, earliest first |
| Priority sorting | `Scheduler.sort_by_priority()`, `Scheduler._weight()` | Owner's category weight first, then task's own low/med/high |
| Filtering by pet / status | `Scheduler.filter_tasks()` | Filter by completion status, pet name, or both |
| Filtering by time budget | `Scheduler.filter_by_available_time()` | Drops tasks once `available_minutes` is spent (keeps time-critical) |
| Conflict detection | `Scheduler.find_conflicts()`, `describe_conflicts()`, `check_conflicts()` | Reports overlapping tasks (same or different pets) without dropping them |
| Conflict resolution | `Scheduler.resolve_conflicts()`, `Task.conflicts_with()` | Keeps the higher-priority task of each overlapping group |
| Gap-aware placement | `Scheduler._earliest_gap()`, `_place()` | Fits flexible tasks into free gaps around fixed ones |
| Recurring tasks | `Task.mark_complete()`, `Task._spawn_next_occurrence()` | Completing a daily/weekly task spawns the next occurrence |

### Sorting behavior

- **`Scheduler.sort_by_time(tasks)`** — a `@staticmethod` that returns tasks in
  chronological order by `preferred_time` (earliest first). Flexible tasks (no
  set time) sort to the end via `time.max` so a `None` never crashes the sort.
  Used by the UI to list each pet's tasks in clock order.
- **`Scheduler.sort_by_priority(tasks)`** (with **`_weight()`**) — orders tasks
  by the owner's per-category weight first, then the task's own
  low/medium/high priority as a tiebreaker (a `(weight, rank)` tuple).

### Filtering behavior

- **`Scheduler.filter_tasks(tasks, status=None, pet_name=None)`** — a
  `@staticmethod` that returns the subset matching either filter or both
  (ANDed). `status` matches `"pending"`/`"complete"`; `pet_name` matches a
  pet's name case-insensitively. Filters left as `None` are ignored.
- **`Scheduler.filter_by_available_time(tasks)`** — keeps tasks until the
  owner's `available_minutes` budget is exhausted, expanding multi-dose meds
  first and never dropping a `is_time_critical` task.

### Conflict detection logic

- **`Task.conflicts_with(other)`** — the core test: two tasks conflict when
  their `[start, start + duration)` time ranges overlap (not just equal start
  times), so back-to-back tasks that touch are *not* flagged.
- **`Scheduler.find_conflicts(tasks)`** — returns every overlapping
  `(task_a, task_b)` pair, for the same pet *or* across pets (one owner can't
  be two places at once). It only reports — it drops nothing.
- **`Scheduler.describe_conflicts()`** / **`check_conflicts()`** — human-readable
  output. `check_conflicts()` is a "lightweight" wrapper that always returns a
  plain-ASCII warning string (empty when there's no clash) and never raises, so
  it's safe to drop straight into the UI or a `print`.
- **`Scheduler.resolve_conflicts(tasks)`** — the *resolution* counterpart:
  processes tasks highest-priority first and keeps a task only if it clashes
  with nothing already kept, so no overlaps survive in the final plan.

### Recurring task logic

- **`Task.mark_complete()`** — marking a `"daily"` or `"weekly"` task complete
  automatically spawns a fresh **pending** copy for the next occurrence,
  attached to the same pet and reachable via `task.next_occurrence`. It only
  spawns on the pending→complete transition, so it never piles up duplicates.
- **`Task._spawn_next_occurrence()`** — builds that copy, rolling the `due_date`
  forward with `datetime.timedelta` (+1 day for daily, +7 for weekly), which
  correctly handles month/year boundaries (e.g. Jan 31 → Feb 1).

## 📸 Demo Walkthrough

### Main UI features

The Streamlit app (`app.py`) is organized top-to-bottom into four areas:

- **Owner** — edit the owner's name, total available minutes for the day, and
  preferred start time. These constraints drive every scheduling decision.
- **Pets** — add a pet (name, species, optional breed) or remove one. Each pet
  shows a live count of its tasks.
- **Tasks** — add a task for a chosen pet, setting its category, duration,
  priority, recurrence (one-time / daily / weekly), and an optional preferred
  time. Each task row has **Done** (marks it complete — and spawns the next
  occurrence for recurring tasks) and **Remove** buttons. Pending tasks are
  listed in clock order, with completed ones grouped separately underneath.
- **Build Schedule** — press **Generate schedule** to build and display the
  day's plan.

### Example workflow

1. **Set the owner's constraints** — e.g. 120 available minutes, starting at
   08:00.
2. **Add a pet** — type "Biscuit", pick "dog", submit. Biscuit now appears with
   "0 task(s)".
3. **Add tasks for the pet** — e.g. an "Insulin" medication and a "Morning walk",
   each with a duration, priority, and preferred time.
4. **View the task list** — tasks appear sorted by time; mark one **Done** to see
   it move to the completed group (a daily task also spawns tomorrow's copy).
5. **Generate the schedule** — press the button to see today's plan, any
   conflict warnings, and the reasoning behind what was included or dropped.

### Key Scheduler behaviors shown

- **Sorting by time** — the task list and the generated plan are ordered
  earliest-first; flexible ("anytime") tasks fall to the end.
- **Filtering** — completed vs. pending tasks are separated, and the schedule
  respects the owner's time budget.
- **Conflict warnings** — if two tasks overlap in time (for the same pet *or*
  across pets), the app shows an amber warning naming each clashing pair and
  states which task it will keep and which it will drop.
- **Conflict resolution** — the plan keeps the higher-priority task of each
  overlapping pair and lists the loser under "Excluded".
- **Priority ordering** — the reasoning view shows each task's category weight,
  so the owner can see *why* medication outranks grooming.
- **Recurrence** — marking a daily/weekly task Done rolls its due date forward
  (+1 day / +7 days) and creates the next pending occurrence.

### Sample CLI output (`python main.py`)

Running the terminal demo builds an owner (Sam) with two pets (Biscuit and Miso)
and a deliberate cross-pet time clash, then exercises sorting, filtering,
recurrence, conflict detection, and the full plan:

```text
Sam cares for 2 pets: Biscuit (Golden Retriever), Miso (Tabby)

Tasks as entered:
  18:00  [Biscuit] Evening walk - pending
  09:30  [Miso] Brush coat - complete
  anytime  [Biscuit] Insulin - pending
  09:00  [Miso] Feed - complete
  08:30  [Biscuit] Breakfast - pending
  08:35  [Miso] Litter cleanup - pending

Sorted by time (sort_by_time):
  08:30  [Biscuit] Breakfast - pending
  08:35  [Miso] Litter cleanup - pending
  09:00  [Miso] Feed - complete
  09:30  [Miso] Brush coat - complete
  18:00  [Biscuit] Evening walk - pending
  anytime  [Biscuit] Insulin - pending

Pending only (filter_tasks status='pending'):
  18:00  [Biscuit] Evening walk - pending
  anytime  [Biscuit] Insulin - pending
  08:30  [Biscuit] Breakfast - pending
  08:35  [Miso] Litter cleanup - pending

Complete only (filter_tasks status='complete'):
  09:30  [Miso] Brush coat - complete
  09:00  [Miso] Feed - complete

Biscuit's tasks (filter_tasks pet_name='Biscuit'):
  18:00  [Biscuit] Evening walk - pending
  anytime  [Biscuit] Insulin - pending
  08:30  [Biscuit] Breakfast - pending

Recurrence (mark_complete spawns the next occurrence):
  Daily walk (daily): due 2026-07-07 -> next due 2026-07-08 [pending]
  Weekly bath (weekly): due 2026-07-07 -> next due 2026-07-14 [pending]

Conflict check (check_conflicts):
WARNING: 1 time conflict(s) detected:
  - [Biscuit] Breakfast (08:30) overlaps [Miso] Litter cleanup (08:35)

Today's Schedule - 6 item(s), 75 min:
  Biscuit (Golden Retriever):
    08:00-08:05  Insulin
    08:30-08:45  Breakfast
    18:00-18:30  Evening walk
    20:00-20:05  Insulin
  Miso (Tabby):
    09:00-09:10  Feed
    09:30-09:40  Brush coat

Schedule reasoning:
  Budget: 120 min (used 75).
  Included (in priority order):
    - [Biscuit] Insulin at 08:00 [weight 10, medium]
    - [Biscuit] Breakfast at 08:30 [weight 8, medium]
    - [Miso] Feed at 09:00 [weight 8, medium]
    - [Miso] Brush coat at 09:30 [weight 4, medium]
    - [Biscuit] Evening walk at 18:00 [weight 5, medium]
    - [Biscuit] Insulin at 20:00 [weight 10, medium]
  Excluded (conflicted or out of time):
    - [Miso] Litter cleanup
```

> Note: the recurrence due dates above (2026-07-07 → 07-08 / 07-14) are relative
> to the day you run the demo, since new tasks default to today's date.
