"""
PawPal+ — Backend logic layer.

Classes:
    Task       — a single pet care activity (dataclass)
    Pet        — represents a pet and its associated tasks (dataclass)
    Owner      — represents the owner, their preferences, and their pets
    Scheduler  — builds and explains a daily care plan from tasks + constraints
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    ANYTIME = "anytime"


class Frequency(str, Enum):
    """How often a recurring task repeats."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single pet care activity."""

    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    category: str = "general"          # e.g. "walk", "feeding", "meds", "grooming"
    preferred_time: TimeOfDay = TimeOfDay.ANYTIME
    recurring: bool = False             # True → repeats on the given frequency
    frequency: Frequency = Frequency.DAILY  # only meaningful when recurring=True
    due_date: date | None = None        # date this task is due (None = today)
    notes: str = ""
    completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.completed = True

    def create_next_occurrence(self) -> "Task":
        """Return a fresh copy of this recurring task scheduled for its next due date.

        Uses timedelta to advance the due date by 1 day (daily) or 7 days (weekly).
        Raises ValueError if called on a non-recurring task.
        """
        if not self.recurring:
            raise ValueError(f"Task '{self.title}' is not recurring.")

        delta = timedelta(days=1 if self.frequency == Frequency.DAILY else 7)
        base = self.due_date if self.due_date else date.today()
        next_task = copy.copy(self)
        next_task.completed = False
        next_task.due_date = base + delta
        return next_task

    def is_high_priority(self) -> bool:
        """Return True if this task has high priority."""
        return self.priority == Priority.HIGH

    def __str__(self) -> str:
        status = "done" if self.completed else "    "
        return (
            f"[{status}][{self.priority.value.upper()}] {self.title} "
            f"({self.duration_minutes} min, {self.preferred_time.value})"
        )


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    """Represents a pet and the tasks associated with it."""

    name: str
    species: str                        # "dog", "cat", "rabbit", etc.
    breed: str = ""
    age_years: float = 0.0
    special_needs: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a care task to this pet."""
        self.tasks.append(task)

    def remove_task(self, title: str) -> bool:
        """Remove the first task matching *title*. Returns True if removed."""
        for i, t in enumerate(self.tasks):
            if t.title.lower() == title.lower():
                self.tasks.pop(i)
                return True
        return False

    def get_tasks_by_priority(self) -> list[Task]:
        """Return tasks sorted high → low priority."""
        order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        return sorted(self.tasks, key=lambda t: order[t.priority])

    def total_care_minutes(self) -> int:
        """Sum of all task durations in minutes."""
        return sum(t.duration_minutes for t in self.tasks)

    def __str__(self) -> str:
        return f"{self.name} ({self.species}, {self.age_years:.1f} yrs)"


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

class Owner:
    """Represents the pet owner, their preferences, and their pets."""

    def __init__(
        self,
        name: str,
        available_minutes_per_day: int = 120,
        preferred_schedule: TimeOfDay = TimeOfDay.MORNING,
    ) -> None:
        self.name = name
        self.available_minutes_per_day = available_minutes_per_day
        self.preferred_schedule = preferred_schedule
        self.pets: list[Pet] = []

    # ------------------------------------------------------------------
    # Pet management
    # ------------------------------------------------------------------

    def add_pet(self, pet: Pet) -> None:
        """Register a pet with this owner."""
        self.pets.append(pet)

    def remove_pet(self, name: str) -> bool:
        """Remove the first pet matching *name*. Returns True if removed."""
        for i, p in enumerate(self.pets):
            if p.name.lower() == name.lower():
                self.pets.pop(i)
                return True
        return False

    def get_pet(self, name: str) -> Optional[Pet]:
        """Return the pet with *name*, or None if not found."""
        for p in self.pets:
            if p.name.lower() == name.lower():
                return p
        return None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def all_tasks(self) -> list[tuple[Pet, Task]]:
        """Return every (pet, task) pair across all owned pets."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]

    def total_required_minutes(self) -> int:
        """Sum of all task durations across all pets."""
        return sum(pet.total_care_minutes() for pet in self.pets)

    def has_enough_time(self) -> bool:
        """True if the owner has enough time for all tasks today."""
        return self.total_required_minutes() <= self.available_minutes_per_day

    def __str__(self) -> str:
        return (
            f"Owner: {self.name} | "
            f"Pets: {len(self.pets)} | "
            f"Available: {self.available_minutes_per_day} min/day"
        )


# ---------------------------------------------------------------------------
# ScheduledTask  (output record)
# ---------------------------------------------------------------------------

@dataclass
class ScheduledTask:
    """A task placed at a specific time slot in the daily plan."""

    pet: Pet
    task: Task
    start_minute: int       # minutes from midnight (e.g. 480 = 8:00 AM)
    reason: str = ""        # plain-language explanation of why this slot was chosen

    @property
    def end_minute(self) -> int:
        return self.start_minute + self.task.duration_minutes

    def start_time_str(self) -> str:
        h, m = divmod(self.start_minute, 60)
        return f"{h:02d}:{m:02d}"

    def end_time_str(self) -> str:
        h, m = divmod(self.end_minute, 60)
        return f"{h:02d}:{m:02d}"

    def __str__(self) -> str:
        return (
            f"{self.start_time_str()}-{self.end_time_str()} | "
            f"{self.pet.name}: {self.task.title} - {self.reason}"
        )


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """
    Builds a prioritised daily care plan for an owner's pets.

    Algorithm (greedy, priority-first):
      1. Collect all tasks from all pets.
      2. Sort by priority (high first), then by the owner's preferred time-of-day.
      3. Fit tasks into the owner's available window, skipping tasks that
         won't fit within the remaining time budget.
      4. Detect and report any time conflicts in the resulting plan.
    """

    # Default day window: 7 AM – 9 PM (840 minutes total)
    DEFAULT_START_MINUTE = 7 * 60   # 420
    DEFAULT_END_MINUTE   = 21 * 60  # 1260

    def __init__(self, owner: Owner) -> None:
        self.owner = owner
        self.schedule: list[ScheduledTask] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_schedule(self) -> list[ScheduledTask]:
        """Build and return the daily schedule."""
        sorted_tasks = self._sort_tasks()
        self.schedule = self._fit_tasks(sorted_tasks)
        return self.schedule

    def detect_conflicts(self) -> list[tuple[ScheduledTask, ScheduledTask]]:
        """Return pairs of ScheduledTasks whose time slots overlap."""
        conflicts: list[tuple[ScheduledTask, ScheduledTask]] = []
        for i, a in enumerate(self.schedule):
            for b in self.schedule[i + 1:]:
                if a.start_minute < b.end_minute and b.start_minute < a.end_minute:
                    conflicts.append((a, b))
        return conflicts

    def explain_plan(self) -> str:
        """Return a human-readable explanation of the generated schedule."""
        if not self.schedule:
            return "No schedule generated yet. Call generate_schedule() first."

        lines = [f"Daily plan for {self.owner.name}\n" + "=" * 40]
        for st in self.schedule:
            lines.append(str(st))

        skipped_count = len(self.owner.all_tasks()) - len(self.schedule)
        if skipped_count:
            lines.append(
                f"\n{skipped_count} task(s) skipped — not enough time in the day."
            )

        conflicts = self.detect_conflicts()
        if conflicts:
            lines.append(f"\n[!] {len(conflicts)} conflict(s) detected:")
            for a, b in conflicts:
                lines.append(f"  - {a.task.title} overlaps with {b.task.title}")

        return "\n".join(lines)

    def sort_by_time(self) -> list[ScheduledTask]:
        """Return the current schedule sorted by start time (earliest first)."""
        return sorted(self.schedule, key=lambda st: st.start_minute)

    def filter_tasks(
        self,
        pet_name: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> list[tuple[Pet, Task]]:
        """Filter all owner tasks by pet name and/or completion status.

        Args:
            pet_name:  If given, only include tasks belonging to that pet (case-insensitive).
            completed: If given, only include tasks whose completed field matches.

        Returns:
            List of (Pet, Task) pairs that pass all specified filters.
        """
        results = self.owner.all_tasks()
        if pet_name is not None:
            results = [(p, t) for p, t in results if p.name.lower() == pet_name.lower()]
        if completed is not None:
            results = [(p, t) for p, t in results if t.completed == completed]
        return results

    def add_fixed_task(self, pet: Pet, task: Task, start_minute: int) -> ScheduledTask:
        """Place a task at a specific start time regardless of the current cursor.

        Useful for testing conflict detection or manually pinning a task to a time.
        """
        reason = self._build_reason(task)
        st = ScheduledTask(pet=pet, task=task, start_minute=start_minute, reason=reason)
        self.schedule.append(st)
        return st

    def renew_recurring_tasks(self) -> list[Task]:
        """Find completed recurring tasks in the schedule and generate their next occurrences.

        Returns a list of new Task objects (one per completed recurring task) ready to be
        added back to their pet for the next day.
        """
        renewed: list[Task] = []
        for st in self.schedule:
            if st.task.completed and st.task.recurring:
                renewed.append(st.task.create_next_occurrence())
        return renewed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sort_tasks(self) -> list[tuple[Pet, Task]]:
        """
        Sort all (pet, task) pairs for scheduling.

        Order: priority (high→low), then preferred_time alignment with
        owner's preferred_schedule, then duration (shorter first as tie-break).
        """
        priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        preferred = self.owner.preferred_schedule

        def sort_key(pair: tuple[Pet, Task]) -> tuple:
            _, task = pair
            time_match = 0 if task.preferred_time == preferred else 1
            return (priority_order[task.priority], time_match, task.duration_minutes)

        return sorted(self.owner.all_tasks(), key=sort_key)

    def _fit_tasks(self, sorted_tasks: list[tuple[Pet, Task]]) -> list[ScheduledTask]:
        """
        Greedily place tasks into the day window, respecting available time.
        """
        cursor = self.DEFAULT_START_MINUTE
        day_end = min(
            self.DEFAULT_END_MINUTE,
            self.DEFAULT_START_MINUTE + self.owner.available_minutes_per_day,
        )
        result: list[ScheduledTask] = []

        for pet, task in sorted_tasks:
            if cursor + task.duration_minutes > day_end:
                continue  # won't fit — skip

            reason = self._build_reason(task)
            result.append(ScheduledTask(pet=pet, task=task, start_minute=cursor, reason=reason))
            cursor += task.duration_minutes

        return result

    def _build_reason(self, task: Task) -> str:
        """Generate a short plain-language reason for scheduling this task now."""
        parts = []
        if task.priority == Priority.HIGH:
            parts.append("high priority")
        if task.preferred_time == self.owner.preferred_schedule:
            parts.append("matches owner's preferred time")
        if task.recurring:
            parts.append("recurring daily task")
        return ", ".join(parts) if parts else "fits within available time"
