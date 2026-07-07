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
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

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

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
