"""
main.py -- CLI demo for PawPal+

Demonstrates:
  1. Basic schedule generation
  2. Sorting by time
  3. Filtering by pet / completion status
  4. Recurring task renewal with timedelta
  5. Conflict detection

Run with:  python main.py
"""

from pawpal_system import (
    Owner, Pet, Task, Scheduler,
    Priority, TimeOfDay, Frequency,
)


def divider(title: str = "") -> None:
    width = 55
    if title:
        print(f"\n--- {title} {'-' * max(0, width - len(title) - 5)}")
    else:
        print("-" * width)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
owner = Owner(
    name="Jordan",
    available_minutes_per_day=180,
    preferred_schedule=TimeOfDay.MORNING,
)

mochi = Pet(name="Mochi", species="dog", breed="Shiba Inu", age_years=3.0)
luna  = Pet(name="Luna",  species="cat", breed="Tabby",     age_years=5.5)
owner.add_pet(mochi)
owner.add_pet(luna)

# Tasks added out of priority order intentionally to show sorting
mochi.add_task(Task(
    title="Enrichment puzzle",
    duration_minutes=20,
    priority=Priority.LOW,
    category="enrichment",
    preferred_time=TimeOfDay.AFTERNOON,
    recurring=True,
    frequency=Frequency.DAILY,
))
mochi.add_task(Task(
    title="Flea medication",
    duration_minutes=5,
    priority=Priority.HIGH,
    category="meds",
    preferred_time=TimeOfDay.MORNING,
    recurring=True,
    frequency=Frequency.DAILY,
    notes="Apply between shoulder blades",
))
mochi.add_task(Task(
    title="Morning walk",
    duration_minutes=30,
    priority=Priority.HIGH,
    category="walk",
    preferred_time=TimeOfDay.MORNING,
    recurring=True,
    frequency=Frequency.DAILY,
))

luna.add_task(Task(
    title="Wet food feeding",
    duration_minutes=5,
    priority=Priority.HIGH,
    category="feeding",
    preferred_time=TimeOfDay.MORNING,
    recurring=True,
    frequency=Frequency.DAILY,
))
luna.add_task(Task(
    title="Brush coat",
    duration_minutes=15,
    priority=Priority.MEDIUM,
    category="grooming",
    preferred_time=TimeOfDay.EVENING,
    recurring=False,
    frequency=Frequency.ONCE,
))

divider("Owner & Pets")
print(owner)
for pet in owner.pets:
    print(f"  - {pet}  |  {len(pet.tasks)} task(s), {pet.total_care_minutes()} min total")


# ---------------------------------------------------------------------------
# 1. Generate schedule
# ---------------------------------------------------------------------------
scheduler = Scheduler(owner)
scheduler.generate_schedule()

divider("Today's Schedule (priority order)")
print(f"{'TIME':<14} {'PET':<8} {'TASK':<22} {'PRIORITY':<10} REASON")
divider()
for st in scheduler.schedule:
    time_range = f"{st.start_time_str()}-{st.end_time_str()}"
    print(f"{time_range:<14} {st.pet.name:<8} {st.task.title:<22} "
          f"{st.task.priority.value:<10} {st.reason}")


# ---------------------------------------------------------------------------
# 2. Sorting by time
# ---------------------------------------------------------------------------
divider("Sorted by Start Time (earliest first)")
for st in scheduler.sort_by_time():
    print(f"  {st.start_time_str()}  {st.pet.name}: {st.task.title}")


# ---------------------------------------------------------------------------
# 3. Filtering tasks
# ---------------------------------------------------------------------------
divider("Filter: Mochi's tasks only")
for pet, task in scheduler.filter_tasks(pet_name="Mochi"):
    print(f"  [{task.priority.value}] {task.title} ({task.duration_minutes} min)")

divider("Filter: incomplete tasks")
for pet, task in scheduler.filter_tasks(completed=False):
    print(f"  {pet.name}: {task.title}")


# ---------------------------------------------------------------------------
# 4. Recurring task renewal
# ---------------------------------------------------------------------------
divider("Recurring Task Renewal")

# Mark Mochi's morning walk as done
walk = next(t for t in mochi.tasks if t.title == "Morning walk")
walk.mark_complete()
print(f"  Marked complete: {walk.title}  (completed={walk.completed})")

# Generate next occurrences
next_tasks = scheduler.renew_recurring_tasks()
for t in next_tasks:
    print(f"  Next occurrence created: '{t.title}' due {t.due_date} "
          f"(freq={t.frequency.value}, completed={t.completed})")

divider("Filter: completed tasks (after marking walk done)")
for pet, task in scheduler.filter_tasks(completed=True):
    print(f"  {pet.name}: {task.title}")


# ---------------------------------------------------------------------------
# 5. Conflict detection
# ---------------------------------------------------------------------------
divider("Conflict Detection Demo")

# Force two tasks into the same time slot to trigger a conflict
conflict_task = Task(
    title="Emergency vet call",
    duration_minutes=20,
    priority=Priority.HIGH,
    preferred_time=TimeOfDay.MORNING,
)
# Place it at 07:00 — same as the first scheduled task
scheduler.add_fixed_task(mochi, conflict_task, start_minute=7 * 60)

conflicts = scheduler.detect_conflicts()
if conflicts:
    print(f"  [!] {len(conflicts)} conflict(s) found:")
    for a, b in conflicts:
        print(f"      '{a.task.title}' ({a.start_time_str()}-{a.end_time_str()}) "
              f"overlaps '{b.task.title}' ({b.start_time_str()}-{b.end_time_str()})")
else:
    print("  No conflicts detected.")
