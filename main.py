"""Demo script: simulates Alex's pets, prints a daily care plan, and demos sort/filter/conflicts."""

from pawpal_system import Owner, Pet, Scheduler, Task


def _print_task_rows(tasks: list[Task], indent: str = "  ") -> None:
    """Print description, start time, and completion flag for each task."""
    if not tasks:
        print(f"{indent}(none)")
        return
    for t in tasks:
        done = "yes" if t.is_completed else "no"
        print(
            f"{indent}- {t.description} | {t.start_time} | "
            f"completed={done} | {t.duration_mins} min"
        )


def run_sort_and_filter_demo(scheduler: Scheduler) -> None:
    """
    Exercise Scheduler.sort_by_time and Scheduler.filter_tasks with out-of-order
    start_time values across two pets.
    """
    owner = Owner()
    rex = Pet(name="Rex", species="dog")
    zoe = Pet(name="Zoe", species="cat")

    # Four tasks, non-sequential HH:MM times (two per pet)
    rex.add_task(
        Task(
            description="Afternoon walk",
            duration_mins=25,
            priority=7,
            frequency="None",
            category="exercise",
            start_time="14:00",
        )
    )
    rex.add_task(
        Task(
            description="Morning meal",
            duration_mins=10,
            priority=9,
            frequency="None",
            category="food",
            start_time="08:30",
        )
    )
    zoe.add_task(
        Task(
            description="Evening play",
            duration_mins=20,
            priority=6,
            frequency="None",
            category="fun",
            start_time="19:00",
        )
    )
    zoe.add_task(
        Task(
            description="Midday medication",
            duration_mins=5,
            priority=10,
            frequency="None",
            category="health",
            start_time="11:15",
        )
    )
    owner.add_pet(rex)
    owner.add_pet(zoe)

    banner = "=" * 56

    print()
    print(banner)
    print("--- TESTING CHRONOLOGICAL SORT ---")
    print(banner)
    print("  Raw order from owner.get_all_tasks() (not chronological):")
    raw = owner.get_all_tasks()
    _print_task_rows(raw)
    print()
    print("  After scheduler.sort_by_time() (expected: 08:30, 11:15, 14:00, 19:00):")
    sorted_tasks = scheduler.sort_by_time(raw)
    _print_task_rows(sorted_tasks)

    print()
    print(banner)
    print("--- TESTING FILTER BY PET (Rex only) ---")
    print(banner)
    rex_only = scheduler.filter_tasks(owner, pet_name="Rex")
    print(f"  filter_tasks(..., pet_name='Rex') -> {len(rex_only)} task(s):")
    _print_task_rows(rex_only)

    print()
    print(banner)
    print("--- TESTING FILTER BY STATUS (pending only) ---")
    print(banner)
    zoe.tasks[1].is_completed = True
    print("  Marked 'Midday medication' (Zoe) as completed.")
    pending = scheduler.filter_tasks(owner, status=False)
    print(f"  filter_tasks(..., status=False) -> {len(pending)} pending task(s):")
    _print_task_rows(pending)
    print()


def main() -> None:
    # --- Owner & pets ---
    alex = Owner()
    buddy = Pet(name="Buddy", species="Golden Retriever")
    misty = Pet(name="Misty", species="Tabby")

    # Buddy's tasks (includes a walk window that overlaps Misty's feeding below)
    buddy.add_task(
        Task(
            description="Morning Walk",
            duration_mins=45,
            priority=9,
            frequency="Daily",
            category="exercise",
            start_time="09:00",
        )
    )
    buddy.add_task(
        Task(
            description="Training session",
            duration_mins=20,
            priority=6,
            frequency="None",
            category="training",
            start_time="10:00",
        )
    )
    buddy.add_task(
        Task(
            description="Monthly flea treatment",
            duration_mins=10,
            priority=10,
            frequency="None",
            category="health",
            is_completed=True,
        )
    )

    # Misty's tasks (feeding starts mid-walk: 09:30–09:45 inside Buddy's 09:00–09:45)
    misty.add_task(
        Task(
            description="Feeding",
            duration_mins=15,
            priority=10,
            frequency="Daily",
            category="feeding",
            start_time="09:30",
        )
    )
    misty.add_task(
        Task(
            description="Full grooming",
            duration_mins=45,
            priority=7,
            frequency="Weekly",
            category="grooming",
            start_time="15:00",
        )
    )

    alex.add_pet(buddy)
    alex.add_pet(misty)

    # --- Schedule (larger window so overlapping tasks can both appear in the plan) ---
    scheduler = Scheduler()
    plan = scheduler.generate_plan(alex, available_time=180)

    # --- Output ---
    divider = "*" * 52
    section = "-" * 52

    print(divider)
    print("  DAILY CARE PLAN - Alex's pets (180 min available)")
    print(divider)
    print()

    if not plan.selected_tasks:
        print("  No tasks scheduled for this window.")
    else:
        for i, task in enumerate(plan.selected_tasks, start=1):
            print(f"  {i}. {task.description}")
            print(f"     Duration: {task.duration_mins} min  |  Priority: {task.priority}")
            print(f"     Recurrence: {task.frequency}  |  Category: {task.category}")
            print(section)

    print()
    print("  EXPLANATION")
    print(section)
    print(f"  {plan.explanation}")
    print()
    print("  TOTAL TIME USED")
    print(section)
    print(f"  {plan.total_duration} minutes")
    print()
    print(section)
    print("--- TIME OVERLAP WARNINGS (DailyPlan.conflicts) ---")
    print(section)
    if plan.conflicts:
        for msg in plan.conflicts:
            print(f"  {msg}")
    else:
        print("  (none — no overlapping start_time windows among selected tasks.)")
    print()
    walk_feed_overlap = any(
        "Morning Walk" in msg
        and "Feeding" in msg
        and "09:30" in msg
        and "09:45" in msg
        for msg in plan.conflicts
    )
    if walk_feed_overlap:
        print(
            "  Verification OK: warnings show Misty's Feeding (09:30-09:45) overlaps "
            "Buddy's Morning Walk (09:00-09:45), i.e. feeding would occur while the "
            "owner is still out on the walk."
        )
    elif plan.conflicts:
        print(
            "  Note: overlap warnings were emitted but did not match the expected "
            "Morning Walk / Feeding / 09:30–09:45 pattern; inspect messages above."
        )
    else:
        print(
            "  Verification: expected overlap not reported (both tasks may be missing "
            "from the selected plan, or due_date differed)."
        )
    print()
    print(divider)

    run_sort_and_filter_demo(scheduler)


if __name__ == "__main__":
    main()
