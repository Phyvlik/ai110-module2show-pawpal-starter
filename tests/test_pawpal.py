"""
Automated tests for PawPal+ core logic.

Run with:  python -m pytest
"""

import pytest
from datetime import date, timedelta
from pawpal_system import (
    Owner, Pet, Task, Scheduler,
    Priority, TimeOfDay, Frequency, ScheduledTask,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_task():
    """A basic high-priority task."""
    return Task(title="Morning walk", duration_minutes=30, priority=Priority.HIGH)


@pytest.fixture
def sample_pet():
    """A dog with no tasks."""
    return Pet(name="Mochi", species="dog")


@pytest.fixture
def owner_with_pets():
    """An owner with two pets and several tasks."""
    owner = Owner(name="Jordan", available_minutes_per_day=180)
    dog = Pet(name="Mochi", species="dog")
    cat = Pet(name="Luna", species="cat")

    dog.add_task(Task("Morning walk",   30, Priority.HIGH,   preferred_time=TimeOfDay.MORNING, recurring=True))
    dog.add_task(Task("Flea meds",       5, Priority.HIGH,   preferred_time=TimeOfDay.MORNING))
    dog.add_task(Task("Puzzle toy",     20, Priority.LOW,    preferred_time=TimeOfDay.AFTERNOON))
    cat.add_task(Task("Wet food",        5, Priority.HIGH,   preferred_time=TimeOfDay.MORNING, recurring=True))
    cat.add_task(Task("Brush coat",     15, Priority.MEDIUM, preferred_time=TimeOfDay.EVENING))

    owner.add_pet(dog)
    owner.add_pet(cat)
    return owner


# ---------------------------------------------------------------------------
# Task tests
# ---------------------------------------------------------------------------

class TestTask:
    def test_mark_complete_changes_status(self, sample_task):
        """mark_complete() should set completed to True."""
        assert sample_task.completed is False
        sample_task.mark_complete()
        assert sample_task.completed is True

    def test_mark_complete_is_idempotent(self, sample_task):
        """Calling mark_complete() twice should not raise and stays True."""
        sample_task.mark_complete()
        sample_task.mark_complete()
        assert sample_task.completed is True

    def test_is_high_priority_true(self, sample_task):
        assert sample_task.is_high_priority() is True

    def test_is_high_priority_false(self):
        task = Task(title="Grooming", duration_minutes=15, priority=Priority.LOW)
        assert task.is_high_priority() is False

    def test_default_completed_is_false(self, sample_task):
        assert sample_task.completed is False


# ---------------------------------------------------------------------------
# Pet tests
# ---------------------------------------------------------------------------

class TestPet:
    def test_add_task_increases_count(self, sample_pet, sample_task):
        """Adding a task should increase the pet's task count by 1."""
        before = len(sample_pet.tasks)
        sample_pet.add_task(sample_task)
        assert len(sample_pet.tasks) == before + 1

    def test_add_multiple_tasks(self, sample_pet):
        """Adding three tasks should result in three tasks."""
        for i in range(3):
            sample_pet.add_task(Task(title=f"Task {i}", duration_minutes=10))
        assert len(sample_pet.tasks) == 3

    def test_remove_task_decreases_count(self, sample_pet, sample_task):
        sample_pet.add_task(sample_task)
        result = sample_pet.remove_task("Morning walk")
        assert result is True
        assert len(sample_pet.tasks) == 0

    def test_remove_nonexistent_task_returns_false(self, sample_pet):
        assert sample_pet.remove_task("Does not exist") is False

    def test_total_care_minutes(self, sample_pet):
        sample_pet.add_task(Task("Walk",    30, Priority.HIGH))
        sample_pet.add_task(Task("Feeding",  5, Priority.MEDIUM))
        assert sample_pet.total_care_minutes() == 35

    def test_get_tasks_by_priority_order(self, sample_pet):
        sample_pet.add_task(Task("Low task",  10, Priority.LOW))
        sample_pet.add_task(Task("High task", 10, Priority.HIGH))
        sample_pet.add_task(Task("Med task",  10, Priority.MEDIUM))
        sorted_tasks = sample_pet.get_tasks_by_priority()
        assert sorted_tasks[0].priority == Priority.HIGH
        assert sorted_tasks[1].priority == Priority.MEDIUM
        assert sorted_tasks[2].priority == Priority.LOW


# ---------------------------------------------------------------------------
# Owner tests
# ---------------------------------------------------------------------------

class TestOwner:
    def test_add_pet_increases_count(self, sample_pet):
        owner = Owner("Jordan")
        owner.add_pet(sample_pet)
        assert len(owner.pets) == 1

    def test_get_pet_returns_correct_pet(self, sample_pet):
        owner = Owner("Jordan")
        owner.add_pet(sample_pet)
        found = owner.get_pet("Mochi")
        assert found is sample_pet

    def test_get_pet_case_insensitive(self, sample_pet):
        owner = Owner("Jordan")
        owner.add_pet(sample_pet)
        assert owner.get_pet("mochi") is sample_pet

    def test_get_pet_missing_returns_none(self):
        owner = Owner("Jordan")
        assert owner.get_pet("Ghost") is None

    def test_has_enough_time_true(self, owner_with_pets):
        """75 min of tasks vs 180 min available — should be True."""
        assert owner_with_pets.has_enough_time() is True

    def test_has_enough_time_false(self, sample_pet):
        owner = Owner("Jordan", available_minutes_per_day=10)
        sample_pet.add_task(Task("Long task", 60, Priority.HIGH))
        owner.add_pet(sample_pet)
        assert owner.has_enough_time() is False

    def test_all_tasks_aggregates_all_pets(self, owner_with_pets):
        pairs = owner_with_pets.all_tasks()
        assert len(pairs) == 5


# ---------------------------------------------------------------------------
# Scheduler tests
# ---------------------------------------------------------------------------

class TestScheduler:
    def test_generate_schedule_returns_list(self, owner_with_pets):
        scheduler = Scheduler(owner_with_pets)
        result = scheduler.generate_schedule()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_high_priority_tasks_scheduled_first(self, owner_with_pets):
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        high_slots = [
            st for st in scheduler.schedule if st.task.priority == Priority.HIGH
        ]
        low_slots = [
            st for st in scheduler.schedule if st.task.priority == Priority.LOW
        ]
        if high_slots and low_slots:
            assert min(s.start_minute for s in high_slots) < max(s.start_minute for s in low_slots)

    def test_no_conflicts_in_normal_schedule(self, owner_with_pets):
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        assert scheduler.detect_conflicts() == []

    def test_schedule_respects_time_budget(self, sample_pet):
        """Tasks that exceed available time should be skipped."""
        owner = Owner("Jordan", available_minutes_per_day=10)
        sample_pet.add_task(Task("Short task", 5,  Priority.HIGH))
        sample_pet.add_task(Task("Long task",  60, Priority.LOW))
        owner.add_pet(sample_pet)

        scheduler = Scheduler(owner)
        scheduler.generate_schedule()

        total_scheduled = sum(st.task.duration_minutes for st in scheduler.schedule)
        assert total_scheduled <= 10

    def test_explain_plan_returns_string(self, owner_with_pets):
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        explanation = scheduler.explain_plan()
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_scheduled_tasks_have_valid_times(self, owner_with_pets):
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        for st in scheduler.schedule:
            assert st.start_minute >= Scheduler.DEFAULT_START_MINUTE
            assert st.end_minute <= Scheduler.DEFAULT_END_MINUTE

    def test_empty_pet_produces_no_schedule(self):
        """A pet with no tasks should result in an empty schedule."""
        owner = Owner("Jordan", available_minutes_per_day=120)
        owner.add_pet(Pet(name="Ghost", species="cat"))
        scheduler = Scheduler(owner)
        result = scheduler.generate_schedule()
        assert result == []

    def test_owner_with_no_pets_produces_no_schedule(self):
        """An owner with no pets should produce an empty schedule."""
        owner = Owner("Jordan", available_minutes_per_day=120)
        scheduler = Scheduler(owner)
        result = scheduler.generate_schedule()
        assert result == []


# ---------------------------------------------------------------------------
# Sorting tests
# ---------------------------------------------------------------------------

class TestSorting:
    def test_sort_by_time_returns_chronological_order(self, owner_with_pets):
        """sort_by_time() must return slots ordered earliest start first."""
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        sorted_slots = scheduler.sort_by_time()
        start_times = [st.start_minute for st in sorted_slots]
        assert start_times == sorted(start_times)

    def test_sort_by_time_is_stable_for_single_task(self, sample_pet, sample_task):
        """A schedule with one task should sort to a list of one item."""
        owner = Owner("Jordan", available_minutes_per_day=120)
        sample_pet.add_task(sample_task)
        owner.add_pet(sample_pet)
        scheduler = Scheduler(owner)
        scheduler.generate_schedule()
        assert len(scheduler.sort_by_time()) == 1

    def test_high_priority_before_low_in_generated_order(self, owner_with_pets):
        """High-priority tasks must be placed before low-priority ones."""
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        priorities = [st.task.priority for st in scheduler.schedule]
        high_indices = [i for i, p in enumerate(priorities) if p == Priority.HIGH]
        low_indices  = [i for i, p in enumerate(priorities) if p == Priority.LOW]
        if high_indices and low_indices:
            assert max(high_indices) < min(low_indices)


# ---------------------------------------------------------------------------
# Recurrence tests
# ---------------------------------------------------------------------------

class TestRecurrence:
    def test_daily_next_occurrence_is_tomorrow(self):
        """create_next_occurrence() for a daily task should be due tomorrow."""
        today = date.today()
        task = Task(
            title="Walk",
            duration_minutes=20,
            recurring=True,
            frequency=Frequency.DAILY,
            due_date=today,
        )
        next_task = task.create_next_occurrence()
        assert next_task.due_date == today + timedelta(days=1)

    def test_weekly_next_occurrence_is_next_week(self):
        """create_next_occurrence() for a weekly task should be due in 7 days."""
        today = date.today()
        task = Task(
            title="Bath",
            duration_minutes=30,
            recurring=True,
            frequency=Frequency.WEEKLY,
            due_date=today,
        )
        next_task = task.create_next_occurrence()
        assert next_task.due_date == today + timedelta(days=7)

    def test_next_occurrence_starts_incomplete(self):
        """The renewed task must not carry over the completed flag."""
        task = Task(title="Meds", duration_minutes=5, recurring=True, frequency=Frequency.DAILY)
        task.mark_complete()
        next_task = task.create_next_occurrence()
        assert next_task.completed is False

    def test_next_occurrence_preserves_task_attributes(self):
        """Title, duration, priority, and category must be copied to the new occurrence."""
        task = Task(
            title="Flea meds",
            duration_minutes=5,
            priority=Priority.HIGH,
            category="meds",
            recurring=True,
            frequency=Frequency.DAILY,
        )
        next_task = task.create_next_occurrence()
        assert next_task.title == task.title
        assert next_task.duration_minutes == task.duration_minutes
        assert next_task.priority == task.priority
        assert next_task.category == task.category

    def test_non_recurring_task_raises_on_renewal(self):
        """create_next_occurrence() must raise ValueError for non-recurring tasks."""
        task = Task(title="One-off groom", duration_minutes=15, recurring=False)
        with pytest.raises(ValueError):
            task.create_next_occurrence()

    def test_renew_recurring_tasks_returns_correct_count(self, owner_with_pets):
        """renew_recurring_tasks() should return one item per completed recurring task."""
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()

        # Mark all recurring tasks in the schedule complete
        recurring_slots = [st for st in scheduler.schedule if st.task.recurring]
        for st in recurring_slots:
            st.task.mark_complete()

        renewed = scheduler.renew_recurring_tasks()
        assert len(renewed) == len(recurring_slots)

    def test_renew_returns_empty_when_nothing_completed(self, owner_with_pets):
        """renew_recurring_tasks() should return [] if no tasks are completed."""
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        assert scheduler.renew_recurring_tasks() == []

    def test_due_date_defaults_to_today_when_none(self):
        """When due_date is None, create_next_occurrence() bases the date on today."""
        today = date.today()
        task = Task(title="Walk", duration_minutes=20, recurring=True, frequency=Frequency.DAILY)
        next_task = task.create_next_occurrence()
        assert next_task.due_date == today + timedelta(days=1)


# ---------------------------------------------------------------------------
# Conflict detection tests
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_normal_schedule_has_no_conflicts(self, owner_with_pets):
        """Sequentially placed tasks must never overlap."""
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        assert scheduler.detect_conflicts() == []

    def test_identical_start_times_detected_as_conflict(self, owner_with_pets):
        """Two tasks starting at the same minute must be flagged."""
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        pet = owner_with_pets.pets[0]
        extra = Task("Emergency vet", duration_minutes=10, priority=Priority.HIGH)
        scheduler.add_fixed_task(pet, extra, start_minute=Scheduler.DEFAULT_START_MINUTE)
        assert len(scheduler.detect_conflicts()) >= 1

    def test_overlapping_tasks_detected(self, sample_pet):
        """Tasks whose windows overlap (not just same start) must be detected."""
        owner = Owner("Jordan", available_minutes_per_day=120)
        t1 = Task("Task A", duration_minutes=30)
        t2 = Task("Task B", duration_minutes=30)
        owner.add_pet(sample_pet)
        scheduler = Scheduler(owner)
        # Manually place two overlapping slots
        scheduler.add_fixed_task(sample_pet, t1, start_minute=480)   # 08:00–08:30
        scheduler.add_fixed_task(sample_pet, t2, start_minute=500)   # 08:20–08:50
        conflicts = scheduler.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0] == (scheduler.schedule[0], scheduler.schedule[1])

    def test_adjacent_tasks_not_flagged_as_conflict(self, sample_pet):
        """Tasks that touch (end == next start) must NOT be flagged."""
        owner = Owner("Jordan", available_minutes_per_day=120)
        t1 = Task("Task A", duration_minutes=30)
        t2 = Task("Task B", duration_minutes=30)
        owner.add_pet(sample_pet)
        scheduler = Scheduler(owner)
        scheduler.add_fixed_task(sample_pet, t1, start_minute=480)   # 08:00–08:30
        scheduler.add_fixed_task(sample_pet, t2, start_minute=510)   # 08:30–09:00
        assert scheduler.detect_conflicts() == []


# ---------------------------------------------------------------------------
# Filtering tests
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_filter_by_pet_name(self, owner_with_pets):
        """filter_tasks(pet_name=) should only return that pet's tasks."""
        scheduler = Scheduler(owner_with_pets)
        results = scheduler.filter_tasks(pet_name="Mochi")
        assert all(pet.name == "Mochi" for pet, _ in results)

    def test_filter_by_pet_name_case_insensitive(self, owner_with_pets):
        """Pet name filter should be case-insensitive."""
        scheduler = Scheduler(owner_with_pets)
        lower = scheduler.filter_tasks(pet_name="mochi")
        upper = scheduler.filter_tasks(pet_name="MOCHI")
        assert len(lower) == len(upper)

    def test_filter_completed_false(self, owner_with_pets):
        """filter_tasks(completed=False) should exclude completed tasks."""
        scheduler = Scheduler(owner_with_pets)
        scheduler.generate_schedule()
        # Mark one task complete
        owner_with_pets.pets[0].tasks[0].mark_complete()
        incomplete = scheduler.filter_tasks(completed=False)
        assert all(not t.completed for _, t in incomplete)

    def test_filter_completed_true(self, owner_with_pets):
        """filter_tasks(completed=True) should return only completed tasks."""
        scheduler = Scheduler(owner_with_pets)
        owner_with_pets.pets[0].tasks[0].mark_complete()
        done = scheduler.filter_tasks(completed=True)
        assert len(done) == 1
        assert done[0][1].completed is True

    def test_filter_no_match_returns_empty(self, owner_with_pets):
        """Filtering by a non-existent pet name should return an empty list."""
        scheduler = Scheduler(owner_with_pets)
        assert scheduler.filter_tasks(pet_name="NoSuchPet") == []

    def test_filter_combined_pet_and_status(self, owner_with_pets):
        """Combining pet_name and completed filters should intersect both."""
        scheduler = Scheduler(owner_with_pets)
        # Mark Luna's first task complete
        luna = owner_with_pets.get_pet("Luna")
        luna.tasks[0].mark_complete()
        results = scheduler.filter_tasks(pet_name="Luna", completed=True)
        assert len(results) == 1
        assert results[0][0].name == "Luna"
