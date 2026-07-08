from datetime import time

import pandas as pd
import streamlit as st

from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

# --- Owner: created once, then kept alive in the session "vault" ---
# Building it inside the `not in` guard means it survives every rerun instead
# of being rebuilt (and wiped) each time the user touches a widget.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(
        name="Jordan",
        available_minutes=120,
        preferred_start_time=time(8, 0),
        priority_weights={
            "medication": 10, "feed": 8, "walk": 5,
            "grooming": 4, "enrichment": 2,
        },
    )
owner = st.session_state.owner

st.subheader("Owner")
# Sync the editable fields back onto the persisted Owner each run.
owner.name = st.text_input("Owner name", value=owner.name)
owner.available_minutes = st.number_input(
    "Available minutes today", min_value=0, max_value=1440, value=owner.available_minutes
)
owner.preferred_start_time = st.time_input(
    "Preferred start time", value=owner.preferred_start_time
)

st.divider()

# --- Add a Pet: Pet(...) calls owner.add_pet() for us ---
st.subheader("Pets")
with st.form("add_pet_form", clear_on_submit=True):
    pet_name = st.text_input("Pet name", value="Mochi")
    species_choice = st.selectbox("Species", ["dog", "cat", "other"])
    # Always shown (forms can't reveal fields mid-edit); only used when "other".
    other_species = st.text_input("If 'other', type the species", value="")
    breed = st.text_input("Breed (optional)", value="")
    if st.form_submit_button("Add pet"):
        if species_choice == "other":
            species = other_species.strip() or "other"  # fall back if left blank
        else:
            species = species_choice
        if pet_name.strip():
            Pet(pet_name.strip(), species, owner, breed=breed.strip())  # auto-registers
            st.success(f"Added {pet_name}.")
        else:
            st.warning("Please enter a pet name.")

if owner.pets:
    st.write(f"{owner.name} has {len(owner.pets)} pet(s):")
    # Iterate a copy so removing during the loop can't disturb it.
    for pet in list(owner.pets):
        row, action = st.columns([4, 1])
        row.write(f"{pet} · {len(pet.tasks)} task(s)")
        # id(pet) gives each button a stable, unique key.
        if action.button("Remove", key=f"rm_pet_{id(pet)}"):
            owner.remove_pet(pet)
            st.rerun()  # redraw immediately so the pet disappears from the list
else:
    st.info("No pets yet. Add one above.")

st.divider()

# --- Add a Task: Task(..., pet=...) attaches it to the chosen pet ---
st.subheader("Tasks")
if not owner.pets:
    st.info("Add a pet first, then you can give it tasks.")
else:
    with st.form("add_task_form", clear_on_submit=True):
        pet_label = st.selectbox("For which pet?", [str(p) for p in owner.pets])
        task_title = st.text_input("Task title", value="Morning walk")
        col1, col2, col3 = st.columns(3)
        with col1:
            category = st.selectbox(
                "Category", ["walk", "feed", "medication", "enrichment", "grooming"]
            )
        with col2:
            duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
        with col3:
            priority = st.selectbox("Priority", ["low", "medium", "high"], index=1)
        recurrence = st.selectbox("Repeats", ["one_time", "daily", "weekly"])
        use_time = st.checkbox("Set a preferred time")
        preferred_time = st.time_input("Preferred time", value=time(9, 0)) if use_time else None

        if st.form_submit_button("Add task"):
            # Match the chosen label back to the actual Pet object.
            target_pet = owner.pets[[str(p) for p in owner.pets].index(pet_label)]
            Task(
                task_title, category, int(duration), pet=target_pet,
                priority=priority, recurrence=recurrence, preferred_time=preferred_time,
                is_time_critical=(category == "medication"),
            )
            st.success(f"Added '{task_title}' for {target_pet}.")

    # Render one task row: time/name/status plus "Done" and "Remove" buttons.
    # Done marks the task complete (and, for a daily/weekly task, spawns the
    # next occurrence); it's disabled once complete so it can't spawn twice.
    def render_task_row(pet, task):
        row, done, action = st.columns([5, 1, 1])
        # Show the preferred time (or "anytime") so the ordering is visible.
        when = f"{task.preferred_time:%H:%M}" if task.preferred_time else "anytime"
        # Note the recurrence + due date for repeating tasks.
        repeat = "" if task.recurrence == "one_time" else f" · {task.recurrence} (due {task.due_date:%b %d})"
        row.write(f"{when} · {task.name} "
                  f"({task.category}, {task.duration_minutes} min) "
                  f"— {task.status}{repeat}")
        if done.button("Done", key=f"done_task_{id(task)}",
                       disabled=task.status == "complete"):
            task.mark_complete()  # spawns next_occurrence if recurring
            st.rerun()
        if action.button("Remove", key=f"rm_task_{id(task)}"):
            pet.remove_task(task)
            st.rerun()

    # Show each pet's tasks in clock order (Scheduler.sort_by_time), with the
    # pending ones first and completed ones grouped under a "Completed" caption
    # (split via Scheduler.filter_tasks) so finished tasks stay on record but
    # move out of the way.
    for pet in owner.pets:
        if pet.tasks:
            st.write(f"**{pet}**")
            ordered = Scheduler.sort_by_time(list(pet.tasks))
            pending = Scheduler.filter_tasks(ordered, status="pending")
            completed = Scheduler.filter_tasks(ordered, status="complete")
            for task in pending:
                render_task_row(pet, task)
            if completed:
                st.caption("Completed")
                for task in completed:
                    render_task_row(pet, task)

st.divider()

# --- Build Schedule: hand all the pets' tasks to one Scheduler ---
st.subheader("Build Schedule")
# Heads-up: the plan currently includes every task, even ones marked "Done".
st.caption("Note: the schedule includes all tasks, including completed ones. "
           "Marking a task Done does not yet remove it from the generated plan.")
def _pet_name(task):
    """Pet name for display, or a dash when a task isn't attached to a pet."""
    return task.pet.name if task.pet is not None else "—"


def _conflict_outcome(task_a, task_b, kept_ids):
    """Plain-language result of a clash, so the owner knows what PawPal+ will do.

    resolve_conflicts() keeps the higher-priority task of each overlapping group,
    so we look up which of the pair survived and phrase it as an action.
    """
    a_kept, b_kept = id(task_a) in kept_ids, id(task_b) in kept_ids
    if a_kept and not b_kept:
        return f"Keeping “{task_a.name}”, dropping “{task_b.name}”"
    if b_kept and not a_kept:
        return f"Keeping “{task_b.name}”, dropping “{task_a.name}”"
    # Neither survived: a third, higher-priority task overlapped both.
    return "Both give way to a higher-priority task"


if st.button("Generate schedule"):
    all_tasks = [task for pet in owner.pets for task in pet.tasks]
    if not all_tasks:
        st.warning("No tasks to schedule yet.")
    else:
        scheduler = Scheduler(owner, all_tasks)

        # --- Conflict warning ---------------------------------------------
        # Surface time clashes (same pet or across pets) BEFORE the plan, in
        # plain language, so the owner sees exactly which task is dropped and
        # why — and can fix it by changing a preferred time. find_conflicts()
        # lists the overlapping pairs; resolve_conflicts() tells us which task
        # wins each clash.
        conflicts = scheduler.find_conflicts()
        if conflicts:
            kept_ids = {id(t) for t in scheduler.resolve_conflicts()}
            st.warning(
                f"⏰ **{len(conflicts)} time conflict(s) found.** "
                "You can only be in one place at a time, so PawPal+ keeps the "
                "higher-priority task in each clash and drops the other."
            )
            conflict_rows = [
                {
                    "Task A": f"{a.name} · {_pet_name(a)} ({a.preferred_time:%H:%M})",
                    "Task B": f"{b.name} · {_pet_name(b)} ({b.preferred_time:%H:%M})",
                    "What PawPal+ does": _conflict_outcome(a, b, kept_ids),
                }
                for a, b in conflicts
            ]
            st.dataframe(pd.DataFrame(conflict_rows), hide_index=True,
                         use_container_width=True)
            st.caption("💡 Want to keep both? Give one of them a different "
                       "preferred time above, then regenerate.")
        else:
            st.success("✅ No time conflicts — every task has room on the timeline.")

        # --- Build and show the plan --------------------------------------
        scheduler.generate_plan(period="daily")

        col1, col2, col3 = st.columns(3)
        col1.metric("Tasks scheduled", len(scheduler.scheduled))
        col2.metric("Time used", f"{scheduler.total_time_used} min")
        col3.metric("Daily budget", f"{owner.available_minutes} min")

        if scheduler.scheduled:
            # Timeline as a clean table, in clock order, keyed on the time slot.
            plan_rows = [
                {
                    "Time": f"{slot.start_time:%H:%M}–{slot.end_time:%H:%M}",
                    "Pet": _pet_name(slot.task),
                    "Task": slot.task.name,
                    "Category": slot.task.category,
                    "Duration": f"{slot.task.duration_minutes} min",
                    "Priority": slot.task.priority,
                }
                for slot in sorted(scheduler.scheduled, key=lambda s: s.start_time)
            ]
            st.subheader("Today's plan")
            st.table(pd.DataFrame(plan_rows).set_index("Time"))
        else:
            st.info("Nothing could be scheduled with the current settings.")

        # Anything left out (a conflict loss or no time budget left).
        if scheduler.excluded:
            dropped = ", ".join(f"{t.name} ({_pet_name(t)})" for t in scheduler.excluded)
            st.warning(f"Left out of today's plan (conflict or not enough time): {dropped}")

        # Full reasoning stays available but tucked away so it doesn't clutter.
        with st.expander("Why this plan? (included / excluded reasoning)"):
            st.text(scheduler.explain())
