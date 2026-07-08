# PawPal+ Project Reflection

## 1. System Design

**Three Core Actions**

- Schedule medicine intake
- Time availability of the owner
- Produce daily and weekly plan 
- Add a pet

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

### Response 

- This UML design consists of foru classes that are to store Pets, the tasks, the Owner information, and the Schedule of the owner to create a schedule that the owner will be satisfied.


INITAL IDEAS: 
Objects:

- Pet
  - type of pet
- Pet Care Tasks (for now)
  - walking
  - feeding
  - medications
  - enrichment 
  - grooming
- Owner 
 - time avilable
 - prefered time
 - task they want to prioritize 
 - prefered durations 
- Schedule Maker

CLAUDE ASSITED IDEAS FOR CLASSES:

## `Owner`
 
Represents the pet owner and their scheduling constraints/preferences.
 
**Attributes**
| Name | Type | Notes |
|---|---|---|
| `name` | `str` | |
| `available_minutes` | `int` | Total time budget for the day |
| `preferred_start_time` | `time` | When the day's plan should begin |
| `priority_weights` | `dict[str, int]` | Which task categories matter most |
 
**Methods**
| Signature | Returns | Notes |
|---|---|---|
| `get_priority_weight(category)` | `int` | Lookup helper used by `Scheduler` |
 
---
 
## `Pet`
 
Represents the pet being cared for.
 
**Attributes**
| Name | Type | Notes |
|---|---|---|
| `name` | `str` | |
| `species` | `str` | e.g. "Dog", "Cat" |
| `breed` | `str` | Optional |
| `age` | `int` | Optional |
| `owner` | `Owner` | Reference back to owner |
 
**Methods**
| Signature | Returns | Notes |
|---|---|---|
| `__str__()` | `str` | e.g. `"Biscuit (Golden Retriever)"` for display |
 
---
 
## `Task`
 
Represents a single pet care task, including medication tasks (flattened — no subclass).
 
**Attributes**
| Name | Type | Notes |
|---|---|---|
| `name` | `str` | |
| `category` | `str` | `"walk"`, `"feed"`, `"medication"`, `"enrichment"`, `"grooming"` |
| `duration_minutes` | `int` | |
| `priority` | `str` | `"low"`, `"medium"`, `"high"` |
| `recurrence` | `str` | `"daily"`, `"weekly"`, `"one_time"` |
| `preferred_time` | `time` | Optional |
| `is_time_critical` | `bool` | Default `False`; `True` for medication |
| `dosage` | `str` | Optional — only used when `category == "medication"` |
| `times_per_day` | `int` | Default `1` — only used for medication |
| `dose_times` | `list[time]` | Default `[]` — only used for medication |
 
**Methods**
| Signature | Returns | Notes |
|---|---|---|
| `__repr__()` | `str` | For debugging/tests |
| `conflicts_with(other: Task)` | `bool` | Checks overlapping `preferred_time` |
| `expand_doses()` | `list[dict]` | If medication with `times_per_day > 1`, returns one entry per dose time; otherwise returns a single entry |
 
---
 
## `Scheduler`
 
Takes tasks + owner constraints, builds and stores a plan, and can explain/display it. Combines what would otherwise be separate `Plan`/`ScheduledTask` classes into one.
 
**Attributes**
| Name | Type | Notes |
|---|---|---|
| `owner` | `Owner` | |
| `pet` | `Pet` | |
| `tasks` | `list[Task]` | All candidate tasks |
| `scheduled` | `list[dict]` | Generated result — each dict has `task`, `start_time`, `end_time` |
| `excluded` | `list[Task]` | Tasks that didn't fit in available time |
| `total_time_used` | `int` | Sum of scheduled durations |
 
**Methods**
| Signature | Returns | Notes |
|---|---|---|
| `generate_plan(period="daily")` | `None` | Main entry point — populates `scheduled`, `excluded`, `total_time_used` |
| `sort_by_priority()` | `list[Task]` | Uses `owner.priority_weights` |
| `filter_by_available_time()` | `list[Task]` | Drops tasks once `owner.available_minutes` is exhausted |
| `resolve_conflicts()` | `list[Task]` | Handles overlapping `preferred_time` values |
| `explain()` | `str` | Human-readable reasoning: why tasks were included/excluded/ordered |
| `__str__()` | `str` | Full formatted plan for display (e.g. the CLI sample output in the README) |
 
---
 

**b. Design changes**

- Did your design change during implementation?

Claude AI was able to capture some inconsistensies between the Class design and the skeleton. 

- If yes, describe at least one change and why you made it.

It updated the `pawpal_system.py` by changing the ordering of how dasks should be ordered. It should resolve conflicts first and then check if the preffered time can work for the Owner. 

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

### Response

**Tradeoff: greedy, priority-first scheduling instead of searching for the globally optimal plan.**

When tasks conflict in time, or the owner's daily time budget runs out, the scheduler decides *one task at a time in priority order*. `resolve_conflicts()` sorts tasks by weight (owner's category priority, then the task's own low/medium/high) and keeps a task only if it doesn't overlap something already kept — so the highest-priority task of any overlapping group wins and the rest are dropped. `filter_by_available_time()` then walks that same priority order and keeps tasks until the budget is spent. Neither step searches every possible combination of tasks to find the set that fits the *most* tasks or the *most* total value into the day.

This means the plan is not guaranteed to be the fullest possible use of the owner's time. For example, dropping one 60-minute high-priority task could have made room for three 20-minute lower-priority tasks that together the owner might have preferred — the greedy approach won't consider that, because it commits to the high-priority task first.

**Why this is reasonable here.** A pet owner needs a plan that is fast to produce, predictable, and easy to *explain* ("your dog's insulin was scheduled first because medication is your top priority; grooming was dropped because it overlapped breakfast"). The greedy rule guarantees the most important care — medication, feeding — never loses out to a bundle of low-priority tasks, which is exactly the safety property that matters for a living animal. It also keeps the logic simple enough to reason about and test. And because a household only has a handful of tasks per day, the cases where an optimal packing would beat the greedy one are rare and low-stakes. The one real cost we caught and fixed was correctness, not optimality: the original greedy loop could leave two overlapping tasks in the plan, so we rewrote `resolve_conflicts()` to process highest-priority first (a kept task is never evicted, so no overlaps survive) and added a regression test.

(Note: an *earlier, simpler* version of this tradeoff — checking only exact start-time matches — was rejected in favor of true duration-overlap detection in `Task.conflicts_with`, so back-to-back and partially overlapping tasks are handled correctly.)

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

### Response

The suite lives in `tests/test_pawpal.py` (15 tests, all passing under
`python -m pytest`). It covers the core behaviors of the scheduler:

- **Task basics** — `mark_complete()` flips a task's status to complete, and
  `add_task()` grows a pet's task list.
- **Sorting correctness** — `sort_by_time()` returns tasks in chronological
  order, and flexible ("anytime") tasks with no preferred time sort to the end
  instead of crashing on a `None` comparison.
- **Recurrence logic** — completing a *daily* task spawns a pending copy due the
  next day; a *weekly* task rolls forward 7 days; a *one-time* task never
  recurs; and marking an already-complete task again does **not** pile up
  duplicate occurrences.
- **Conflict detection** — two tasks at the same/overlapping time are flagged as
  a single pair (`find_conflicts`, `check_conflicts`), while back-to-back tasks
  that only touch at the boundary are *not* flagged, and flexible tasks never
  conflict.
- **Conflict resolution** — the highest-priority task wins its overlapping
  group, leaving no residual overlaps (this was a regression test for the greedy
  bug described in section 2).
- **Time-budget filtering** — an `is_time_critical` task (medication) is kept
  even when the owner's minutes are already exhausted.
- **Empty input** — planning an owner/pet with no tasks produces an empty
  schedule instead of raising.

These mattered because they are the behaviors a pet owner actually depends on:
that the plan is ordered correctly, that a recurring task reliably reappears the
next day, that medication is never silently dropped for lack of time, and that
time clashes are surfaced rather than hidden. They also lock in the two bugs we
found during design (duration-overlap detection and highest-priority-first
resolution) so they can't quietly regress.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

### Response 

I am somewhat confident that my schdulre works correctly as all 15 tests do pass, there might be something I missed as I am someone who never owned a pet before. 


More edge casses that I would test if I had more time is if there are specific medications a person wants to add (looks like more of a new feature), the midnight wrap, the gap-aware placemnt, multi-dose meds in the full plan, end-to-end priority ordering, and cross-pet conflicts.

### Response

**Confidence: 4 out of 5.** The happy paths and the highest-risk edge cases
(duplicate times, boundary-touching tasks, recurrence rollover across
month/year boundaries, over-budget medication, and empty input) are all covered
and green. I'm holding back the fifth point because a couple of behaviors aren't
pinned down by a test yet, so I'm trusting the code by reading rather than by
proof.

Edge cases I would test next, given more time:

- **Midnight wrap** — `_from_minutes` wraps times past 24:00 (e.g. a task
  starting at 23:50 for 30 minutes). I want a test that documents whether the
  wrapped end time is intended behavior or a latent bug.
- **Gap-aware placement** — that a flexible task is actually slotted into a free
  gap *between* two fixed tasks (via `_earliest_gap`), not just appended after
  them.
- **Multi-dose medication in the plan** — that a `times_per_day=3` med both
  counts as 3× its duration against the budget and produces three separate slots
  in the generated schedule.
- **Priority ordering end-to-end** — that `generate_plan` (not just
  `sort_by_priority` in isolation) places a higher-weight category ahead of a
  lower one when the budget forces a choice.
- **Cross-pet conflicts in the full plan** — verifying that a clash between two
  *different* pets' tasks is resolved the same way a same-pet clash is.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

### Response 

**a.** The part I'm most satisfied with is the conflict handling, because it's
where the real problem-solving happened. Most of the other features are a clean
single pass — sort, filter, expand. Conflict handling had an actual bug: the
first version kept a high-priority task but only removed the *first* task it
clashed with, so a second overlapping task could still sneak into the plan. The
fix was to handle the highest-priority task first, so once a task is kept it's
never removed — which means no overlaps can survive. That was a non-obvious
insight, and I backed it with a regression test
(`test_resolve_conflicts_leaves_no_overlaps`) so it can't come back. I also like
that the overlap check gets the small details right: `conflicts_with` compares
full time ranges (start up to start + duration), not just matching start times,
so two tasks that simply touch — like 08:00–08:30 and 08:30–09:00 — are
correctly *not* treated as a conflict, while tasks that actually overlap are.
Best of all, it pays off in the app: instead of just saying "conflict," the UI
names both tasks, shows which one is kept and which is dropped, and tells the
owner how to fix it. "You can't be in two places at once" is the core problem
for a scheduler, and this solves it safely — important care like medication
never gets dropped in favor of something minor like grooming.

**b.** If I had another iteration I would improve the scheduler gneerator where they can implement it into their calander device, like Apple Calander, Google Calander, etc so they don't have to manually put it if they truly want to use the generated schedule.