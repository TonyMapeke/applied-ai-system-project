"""Unit tests for core PawPal+ domain models in pawpal_system."""

from datetime import date, datetime, timedelta
from typing import Tuple, Type

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task


@pytest.fixture
def owner_pet_scheduler() -> Tuple[Owner, Pet, Type[Scheduler]]:
    """Fresh Owner with one Pet plus Scheduler (static API) for isolated tests."""
    owner = Owner()
    pet = Pet(name="QA Pet", species="dog")
    owner.add_pet(pet)
    return owner, pet, Scheduler


@pytest.fixture
def sample_task() -> Task:
    """A typical pending care task used across tests."""
    return Task(
        description="Evening walk",
        duration_mins=25,
        priority=8,
        frequency="None",
        category="exercise",
    )


@pytest.fixture
def sample_pet() -> Pet:
    """A pet with no tasks yet."""
    return Pet(name="Mochi", species="Shiba Inu")


def test_task_is_completed_defaults_to_false(sample_task: Task) -> None:
    """New tasks should start as not completed so they appear in scheduling."""
    assert sample_task.is_completed is False


def test_task_can_be_marked_complete_via_attribute(sample_task: Task) -> None:
    """After marking complete, the flag should be True (simulates finishing a chore)."""
    assert sample_task.is_completed is False
    sample_task.is_completed = True
    assert sample_task.is_completed is True


def test_pet_task_list_starts_empty(sample_pet: Pet) -> None:
    """A new pet should have no tasks until the owner adds them."""
    assert sample_pet.tasks == []
    assert len(sample_pet.tasks) == 0


def test_pet_add_task_appends_one_task(
    sample_pet: Pet,
    sample_task: Task,
) -> None:
    """add_task() should grow the pet's task list by exactly one item."""
    assert len(sample_pet.tasks) == 0
    sample_pet.add_task(sample_task)
    assert len(sample_pet.tasks) == 1
    assert sample_pet.tasks[0] is sample_task


def test_scheduler_sort_by_time_orders_chronologically(
    owner_pet_scheduler: Tuple[Owner, Pet, Type[Scheduler]],
) -> None:
    """sort_by_time should order tasks by clock time when HH:MM strings are zero-padded."""
    _owner, _pet, scheduler = owner_pet_scheduler
    tasks = [
        Task("Late", 10, 1, start_time="15:00"),
        Task("Early", 10, 1, start_time="08:00"),
        Task("Mid", 10, 1, start_time="12:00"),
    ]
    sorted_tasks = scheduler.sort_by_time(tasks)
    assert [t.start_time for t in sorted_tasks] == ["08:00", "12:00", "15:00"]
    parsed = [datetime.strptime(t.start_time, "%H:%M") for t in sorted_tasks]
    assert parsed == sorted(parsed)


def test_daily_recurrence_after_completion_original_done_and_followup_next_day(
    owner_pet_scheduler: Tuple[Owner, Pet, Type[Scheduler]],
) -> None:
    """Completing a Daily task marks it done and appends the same chore for tomorrow."""
    _owner, pet, scheduler = owner_pet_scheduler
    today = date.today()
    daily = Task(
        description="Morning meds",
        duration_mins=5,
        priority=6,
        frequency="Daily",
        due_date=today,
    )
    pet.add_task(daily)
    next_task = scheduler.handle_recurrence(pet, daily)

    assert daily.is_completed is True
    assert next_task is not None
    assert next_task.description == daily.description
    assert next_task.due_date == today + timedelta(days=1)
    assert next_task in pet.tasks
    assert pet.tasks[-1] is next_task


def test_scheduler_check_for_conflicts_detects_overlapping_intervals(
    owner_pet_scheduler: Tuple[Owner, Pet, Type[Scheduler]],
) -> None:
    """Overlapping [start, end) windows on the same day should yield at least one warning."""
    _owner, _pet, scheduler = owner_pet_scheduler
    day = date(2026, 6, 15)
    task_a = Task(
        "Task A",
        60,
        5,
        start_time="09:00",
        due_date=day,
    )
    task_b = Task(
        "Task B",
        30,
        5,
        start_time="09:30",
        due_date=day,
    )
    warnings = scheduler.check_for_conflicts([task_a, task_b])
    assert len(warnings) >= 1
    combined = " ".join(warnings)
    assert "Task A" in combined and "Task B" in combined


def test_mark_complete_daily_returns_next_with_incremented_due_date() -> None:
    base = date(2026, 3, 1)
    t = Task(
        description="Walk",
        duration_mins=15,
        priority=5,
        frequency="Daily",
        due_date=base,
    )
    nxt = t.mark_complete()
    assert t.is_completed is True
    assert nxt is not None
    assert nxt.is_completed is False
    assert nxt.frequency == "Daily"
    assert nxt.due_date == base + timedelta(days=1)


def test_mark_complete_weekly_uses_seven_day_delta() -> None:
    base = date(2026, 3, 1)
    t = Task(
        description="Groom",
        duration_mins=40,
        priority=7,
        frequency="Weekly",
        due_date=base,
    )
    nxt = t.mark_complete()
    assert nxt is not None
    assert nxt.due_date == base + timedelta(days=7)


def test_mark_complete_none_frequency_returns_none() -> None:
    t = Task(description="Vet", duration_mins=30, priority=10, frequency="None")
    nxt = t.mark_complete()
    assert nxt is None
    assert t.is_completed is True


def test_pet_complete_task_appends_next_occurrence() -> None:
    pet = Pet(name="Rex", species="dog")
    base = date(2026, 6, 10)
    walk = Task(
        description="Morning walk",
        duration_mins=20,
        priority=9,
        frequency="Daily",
        due_date=base,
    )
    pet.add_task(walk)
    nxt = pet.complete_task(walk)
    assert len(pet.tasks) == 2
    assert pet.tasks[0] is walk and walk.is_completed
    assert nxt is pet.tasks[1]
    assert nxt.due_date == base + timedelta(days=1)


def test_complete_task_rejects_foreign_task(sample_pet: Pet, sample_task: Task) -> None:
    other = Pet(name="Other", species="cat")
    other.add_task(sample_task)
    with pytest.raises(ValueError, match="not on this pet"):
        sample_pet.complete_task(sample_task)
