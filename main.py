"""
main.py — CLI demo for PawPal+

Run with:  python main.py
"""

from pawpal_system import Owner, Pet, Task, Scheduler, Priority, TimeOfDay


def print_divider(title: str = "") -> None:
    width = 50
    if title:
        print(f"\n--- {title} {'-' * (width - len(title) - 5)}")
    else:
        print("-" * width)


def main() -> None:
    # ------------------------------------------------------------------ #
    # 1. Create owner
    # ------------------------------------------------------------------ #
    owner = Owner(
        name="Jordan",
        available_minutes_per_day=180,
        preferred_schedule=TimeOfDay.MORNING,
    )

    # ------------------------------------------------------------------ #
    # 2. Create pets
    # ------------------------------------------------------------------ #
    mochi = Pet(name="Mochi", species="dog", breed="Shiba Inu", age_years=3.0)
    luna  = Pet(name="Luna",  species="cat", breed="Tabby",     age_years=5.5)

    owner.add_pet(mochi)
    owner.add_pet(luna)

    # ------------------------------------------------------------------ #
    # 3. Add tasks
    # ------------------------------------------------------------------ #
    mochi.add_task(Task(
        title="Morning walk",
        duration_minutes=30,
        priority=Priority.HIGH,
        category="walk",
        preferred_time=TimeOfDay.MORNING,
        recurring=True,
    ))
    mochi.add_task(Task(
        title="Flea medication",
        duration_minutes=5,
        priority=Priority.HIGH,
        category="meds",
        preferred_time=TimeOfDay.MORNING,
        recurring=True,
        notes="Apply between shoulder blades",
    ))
    mochi.add_task(Task(
        title="Enrichment puzzle",
        duration_minutes=20,
        priority=Priority.LOW,
        category="enrichment",
        preferred_time=TimeOfDay.AFTERNOON,
    ))

    luna.add_task(Task(
        title="Wet food feeding",
        duration_minutes=5,
        priority=Priority.HIGH,
        category="feeding",
        preferred_time=TimeOfDay.MORNING,
        recurring=True,
    ))
    luna.add_task(Task(
        title="Brush coat",
        duration_minutes=15,
        priority=Priority.MEDIUM,
        category="grooming",
        preferred_time=TimeOfDay.EVENING,
    ))

    # ------------------------------------------------------------------ #
    # 4. Show owner + pet summary
    # ------------------------------------------------------------------ #
    print_divider("Owner & Pets")
    print(owner)
    for pet in owner.pets:
        print(f"  - {pet}  |  {len(pet.tasks)} task(s), "
              f"{pet.total_care_minutes()} min total")

    # ------------------------------------------------------------------ #
    # 5. Generate and display schedule
    # ------------------------------------------------------------------ #
    scheduler = Scheduler(owner)
    scheduler.generate_schedule()

    print_divider("Today's Schedule")
    print(f"{'TIME':<14} {'PET':<8} {'TASK':<22} {'PRIORITY':<10} REASON")
    print_divider()
    for st in scheduler.schedule:
        time_range = f"{st.start_time_str()}-{st.end_time_str()}"
        print(
            f"{time_range:<14} "
            f"{st.pet.name:<8} "
            f"{st.task.title:<22} "
            f"{st.task.priority.value:<10} "
            f"{st.reason}"
        )

    # ------------------------------------------------------------------ #
    # 6. Time budget check
    # ------------------------------------------------------------------ #
    print_divider("Time Budget")
    total_req  = owner.total_required_minutes()
    total_avail = owner.available_minutes_per_day
    scheduled  = sum(st.task.duration_minutes for st in scheduler.schedule)
    skipped    = total_req - scheduled

    print(f"  Required : {total_req} min")
    print(f"  Available: {total_avail} min")
    print(f"  Scheduled: {scheduled} min")
    if skipped:
        print(f"  Skipped  : {skipped} min worth of tasks (not enough time)")
    else:
        print("  All tasks fit within today's budget.")

    # ------------------------------------------------------------------ #
    # 7. Conflict check
    # ------------------------------------------------------------------ #
    conflicts = scheduler.detect_conflicts()
    if conflicts:
        print_divider("Conflicts Detected")
        for a, b in conflicts:
            print(f"  [!]{a.task.title} overlaps with {b.task.title}")
    else:
        print_divider()
        print("  No scheduling conflicts.")


if __name__ == "__main__":
    main()
