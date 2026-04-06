"""
Automated tests for PawPal+ core logic.

Run with:  python -m pytest
"""

import pytest
from pawpal_system import (
    Owner, Pet, Task, Scheduler,
    Priority, TimeOfDay, ScheduledTask,
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
