from datetime import time

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
if st.button("Generate schedule"):
    all_tasks = [task for pet in owner.pets for task in pet.tasks]
    if not all_tasks:
        st.warning("No tasks to schedule yet.")
    else:
        scheduler = Scheduler(owner, all_tasks)

        # Warn about time clashes (same pet or across pets) before resolving
        # them, so the owner knows a task will be dropped and why. check_conflicts
        # returns a ready-to-show message ("" when there's nothing to warn about).
        warning = scheduler.check_conflicts()
        if warning:
            st.warning(warning + "\n\nThe lower-priority task in each pair "
                       "will be dropped.")

        scheduler.generate_plan(period="daily")
        st.text(str(scheduler))       # the timeline, grouped by pet
        st.text(scheduler.explain())  # the reasoning (included / excluded)
