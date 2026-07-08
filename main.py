"""PawPal+ demo entry point.

Builds an owner with two pets, gives each pet its own tasks, runs a single
scheduler over the whole household (one shared time budget), and prints
"Today's Schedule" to the terminal.
"""

from datetime import time

from pawpal_system import Owner, Pet, Task, Scheduler


def main():
    # One owner and their shared daily time budget.
    owner = Owner(
        name="Sam",
        available_minutes=120,
        preferred_start_time=time(8, 0),
        priority_weights={
            "medication": 10, "feed": 8, "walk": 5,
            "grooming": 4, "enrichment": 2,
        },
    )

    # Two pets. Passing the owner auto-registers them, so owner.pets holds both.
    biscuit = Pet("Biscuit", "Dog", owner, breed="Golden Retriever")
    miso = Pet("Miso", "Cat", owner, breed="Tabby")
    print(f"{owner.name} cares for {len(owner.pets)} pets: "
          f"{', '.join(str(p) for p in owner.pets)}")

    # Tasks, each attached to a pet via pet=... and set at different times.
    tasks = [
        Task("Insulin", "medication", 5, pet=biscuit, is_time_critical=True,
             dosage="2 units", times_per_day=2, dose_times=[time(8, 0), time(20, 0)]),
        Task("Breakfast", "feed", 15, pet=biscuit, preferred_time=time(8, 30)),
        Task("Evening walk", "walk", 30, pet=biscuit, preferred_time=time(18, 0)),
        Task("Feed", "feed", 10, pet=miso, preferred_time=time(9, 0)),
        Task("Brush coat", "grooming", 10, pet=miso, preferred_time=time(9, 30)),
    ]

    # One scheduler for the whole household — pets share the same time budget.
    scheduler = Scheduler(owner, tasks)
    scheduler.generate_plan(period="daily")

    print()
    print(scheduler)
    print()
    print(scheduler.explain())


if __name__ == "__main__":
    main()
