# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Testing PawPal+

Run the full test suite with:

```bash
python -m pytest
```

The suite contains **47 tests** across five areas:

| Area | What is tested |
|---|---|
| `Task` | `mark_complete()`, `is_high_priority()`, default field values |
| `Pet` | Adding/removing tasks, priority sorting, care-time totals |
| `Owner` | Pet registration, case-insensitive lookup, time-budget check |
| `Scheduler` | Schedule generation, time-window enforcement, `explain_plan()` |
| `TestSorting` | Chronological order from `sort_by_time()`, priority ordering |
| `TestRecurrence` | Daily/weekly `create_next_occurrence()` using `timedelta`, `renew_recurring_tasks()`, edge cases |
| `TestConflictDetection` | Overlapping slots flagged, adjacent slots not flagged, identical start times caught |
| `TestFiltering` | Filter by pet name, by completion status, and combined filters |

**Confidence level: 5/5** — all happy paths and key edge cases (empty pets, no-time budget, adjacent vs overlapping tasks, non-recurring renewal error) are covered and passing.

## Smarter Scheduling

PawPal+ goes beyond a simple task list with four algorithmic features:

| Feature | Where | How |
|---|---|---|
| **Priority-first sorting** | `Scheduler._sort_tasks()` | Tasks sorted high → medium → low priority, then by preferred time, then duration |
| **Time-based sorting** | `Scheduler.sort_by_time()` | Returns the generated schedule ordered by start time (earliest first) |
| **Task filtering** | `Scheduler.filter_tasks()` | Filter all tasks by pet name and/or completion status |
| **Recurring task renewal** | `Task.create_next_occurrence()` + `Scheduler.renew_recurring_tasks()` | Marks a recurring task done and generates the next occurrence using `timedelta` (+1 day for daily, +7 for weekly) |
| **Conflict detection** | `Scheduler.detect_conflicts()` | Scans the schedule for overlapping time windows and returns warning pairs without crashing |

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.
