"""Tests for Scheduler: weighted sort, filters, recurring tasks, walk/groom conflicts."""

from datetime import date

from pawpal_system import Owner, Pet, Scheduler, Task


def test_task_is_recurring_defaults_to_false() -> None:
    t = Task(description="x", duration_mins=1, priority=1)
    assert t.is_recurring is False


def test_recurring_task_still_eligible_when_completed() -> None:
    owner = Owner()
    p = Pet(name="A", species="dog")
    p.add_task(
        Task(
            description="Daily walk",
            duration_mins=10,
            priority=9,
            frequency="None",
            category="Health",
            is_completed=True,
            is_recurring=True,
        )
    )
    owner.add_pet(p)
    plan = Scheduler.generate_plan(owner, available_time=60)
    assert len(plan.selected_tasks) == 1
    assert plan.selected_tasks[0].description == "Daily walk"


def test_completed_non_recurring_skipped() -> None:
    owner = Owner()
    p = Pet(name="A", species="dog")
    p.add_task(
        Task(
            description="One-off vet",
            duration_mins=10,
            priority=10,
            frequency="None",
            category="Health",
            is_completed=True,
            is_recurring=False,
        )
    )
    owner.add_pet(p)
    plan = Scheduler.generate_plan(owner, available_time=60)
    assert plan.selected_tasks == []


def test_walk_groom_different_pets_cannot_overlap() -> None:
    owner = Owner()
    a = Pet(name="Dog", species="dog")
    b = Pet(name="Cat", species="cat")
    a.add_task(
        Task(
            description="Walk dog",
            duration_mins=30,
            priority=9,
            frequency="None",
            category="exercise",
        )
    )
    b.add_task(
        Task(
            description="Groom cat",
            duration_mins=30,
            priority=9,
            frequency="None",
            category="Health",
        )
    )
    owner.add_pet(a)
    owner.add_pet(b)
    plan = Scheduler.generate_plan(owner, available_time=30)
    assert len(plan.selected_tasks) == 1
    assert Scheduler.detect_walk_groom_conflicts(plan.scheduled_slots) == []


def test_detect_walk_groom_conflicts_reports_overlap() -> None:
    dog = Pet(name="Dog", species="dog")
    cat = Pet(name="Cat", species="cat")
    t1 = Task(description="Walk", duration_mins=20, priority=5, frequency="None")
    t2 = Task(description="Grooming", duration_mins=20, priority=5, frequency="None")
    slots = [(dog, t1, 0, 20), (cat, t2, 10, 30)]
    msgs = Scheduler.detect_walk_groom_conflicts(slots)
    assert len(msgs) == 1
    assert "Overlap" in msgs[0]


def test_filter_by_pet_name() -> None:
    owner = Owner()
    a = Pet(name="Mochi", species="dog")
    b = Pet(name="Luna", species="cat")
    a.add_task(Task(description="t1", duration_mins=1, priority=1, frequency="None"))
    b.add_task(Task(description="t2", duration_mins=1, priority=1, frequency="None"))
    owner.add_pet(a)
    owner.add_pet(b)
    got = Scheduler.filter_by_pet_name(owner, "Mochi")
    assert len(got) == 1
    assert got[0][0].name == "Mochi"
    assert got[0][1].description == "t1"


def test_filter_by_category_case_insensitive() -> None:
    owner = Owner()
    p = Pet(name="A", species="dog")
    p.add_task(
        Task(description="t", duration_mins=1, priority=1, frequency="None", category="Health")
    )
    owner.add_pet(p)
    assert len(Scheduler.filter_by_category(owner, "health")) == 1
    assert len(Scheduler.filter_by_category(owner, "Fun")) == 0


def test_filter_by_completion() -> None:
    owner = Owner()
    p = Pet(name="A", species="dog")
    p.add_task(
        Task(
            description="done",
            duration_mins=1,
            priority=1,
            frequency="None",
            is_completed=True,
        )
    )
    p.add_task(Task(description="todo", duration_mins=1, priority=1, frequency="None"))
    owner.add_pet(p)
    assert len(Scheduler.filter_by_completion(owner, True)) == 1
    assert len(Scheduler.filter_by_completion(owner, False)) == 1


def test_weighted_sort_prefers_higher_density() -> None:
    """Higher priority/minute should sort before lower, when building plan order."""
    owner = Owner()
    p = Pet(name="A", species="dog")
    long_low_density = Task(
        description="Low density", duration_mins=60, priority=6, frequency="None"
    )
    short_high_density = Task(
        description="High density", duration_mins=10, priority=9, frequency="None"
    )
    p.add_task(long_low_density)
    p.add_task(short_high_density)
    owner.add_pet(p)
    plan = Scheduler.generate_plan(owner, available_time=100)
    assert plan.selected_tasks[0].description == "High density"


def test_task_start_time_defaults_to_midnight() -> None:
    t = Task(description="x", duration_mins=1, priority=1, frequency="None")
    assert t.start_time == "00:00"


def test_sort_by_time_orders_hh_mm_strings() -> None:
    a = Task("a", 1, 1, frequency="None", start_time="14:00")
    b = Task("b", 1, 1, frequency="None", start_time="09:00")
    c = Task("c", 1, 1, frequency="None", start_time="09:30")
    ordered = Scheduler.sort_by_time([a, b, c])
    assert [t.description for t in ordered] == ["b", "c", "a"]


def test_filter_tasks_status_and_pet_name() -> None:
    owner = Owner()
    p1 = Pet(name="Mochi", species="dog")
    p2 = Pet(name="Luna", species="cat")
    p1.add_task(Task("t1", 1, 1, frequency="None", is_completed=False))
    p1.add_task(Task("t2", 1, 1, frequency="None", is_completed=True))
    p2.add_task(Task("t3", 1, 1, frequency="None", is_completed=False))
    owner.add_pet(p1)
    owner.add_pet(p2)
    assert [t.description for t in Scheduler.filter_tasks(owner, status=False)] == [
        "t1",
        "t3",
    ]
    assert [t.description for t in Scheduler.filter_tasks(owner, pet_name="Mochi")] == ["t1", "t2"]
    assert [t.description for t in Scheduler.filter_tasks(owner, status=False, pet_name="Mochi")] == [
        "t1",
    ]
    assert len(Scheduler.filter_tasks(owner)) == 3


def test_check_for_conflicts_detects_overlap() -> None:
    day = date(2026, 5, 1)
    a = Task(
        "Walk",
        60,
        5,
        frequency="None",
        start_time="09:00",
        due_date=day,
    )
    b = Task(
        "Feed",
        30,
        5,
        frequency="None",
        start_time="09:30",
        due_date=day,
    )
    msgs = Scheduler.check_for_conflicts([a, b])
    assert len(msgs) == 1
    assert "Walk" in msgs[0] and "Feed" in msgs[0]
    assert "09:30" in msgs[0] and "10:00" in msgs[0]


def test_check_for_conflicts_no_overlap_different_days() -> None:
    a = Task("A", 60, 1, frequency="None", start_time="10:00", due_date=date(2026, 1, 1))
    b = Task("B", 60, 1, frequency="None", start_time="10:00", due_date=date(2026, 1, 2))
    assert Scheduler.check_for_conflicts([a, b]) == []


def test_generate_plan_includes_conflict_warnings_on_overlap() -> None:
    owner = Owner()
    p = Pet(name="Solo", species="dog")
    day = date(2026, 7, 1)
    p.add_task(Task("A", 60, 9, frequency="None", start_time="08:00", due_date=day))
    p.add_task(Task("B", 60, 8, frequency="None", start_time="08:30", due_date=day))
    owner.add_pet(p)
    plan = Scheduler.generate_plan(owner, available_time=200)
    assert len(plan.selected_tasks) == 2
    assert len(plan.conflict_warnings) >= 1
