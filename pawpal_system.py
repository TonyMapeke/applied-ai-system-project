from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import combinations
from typing import Iterable, List, Optional, Tuple


@dataclass
class Task:
    """Represents one pet care activity and its scheduling metadata."""

    description: str
    duration_mins: int
    priority: int
    frequency: str = "None"
    category: str = "general"
    is_completed: bool = False
    is_recurring: bool = False
    start_time: str = "00:00"
    due_date: date = field(default_factory=date.today)

    def mark_complete(self) -> Optional[Task]:
        """
        Marks this task complete. If ``frequency`` is ``Daily`` or ``Weekly``,
        builds the next occurrence with ``due_date`` advanced by 1 or 7 days
        (``timedelta``) and returns it; does not add it to any pet list.
        """
        if self.is_completed:
            return None
        self.is_completed = True
        if self.frequency == "Daily":
            delta = timedelta(days=1)
        elif self.frequency == "Weekly":
            delta = timedelta(days=7)
        else:
            return None
        return Task(
            description=self.description,
            duration_mins=self.duration_mins,
            priority=self.priority,
            frequency=self.frequency,
            category=self.category,
            is_completed=False,
            is_recurring=self.is_recurring,
            start_time=self.start_time,
            due_date=self.due_date + delta,
        )


@dataclass
class Pet:
    """Models a pet and the care tasks assigned to that pet."""

    name: str
    species: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Adds a new Task object to the pet's internal task list."""
        self.tasks.append(task)

    def complete_task(self, task: Task) -> Optional[Task]:
        """
        Marks ``task`` complete; if it is a Daily/Weekly recurring task, appends
        the next occurrence to this pet's task list and returns that new task.
        """
        if task not in self.tasks:
            raise ValueError("Task is not on this pet's list.")
        next_task = task.mark_complete()
        if next_task is not None:
            self.tasks.append(next_task)
        return next_task


@dataclass
class Owner:
    """Holds every pet belonging to one owner for household-level planning."""

    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Registers a Pet in this owner's managed list."""
        self.pets.append(pet)

    def get_all_tasks(self) -> List[Task]:
        """Returns every task from every pet in a single combined list."""
        combined: List[Task] = []
        for pet in self.pets:
            combined.extend(pet.tasks)
        return combined

    def iter_pet_tasks(self) -> Iterable[Tuple[Pet, Task]]:
        """Yields (pet, task) pairs preserving which pet owns each task."""
        for pet in self.pets:
            for task in pet.tasks:
                yield pet, task


# (pet, task, start_minute, end_minute) after placement on a shared day timeline
ScheduledSlot = Tuple[Pet, Task, int, int]


class Scheduler:
    """Builds a feasible daily plan from an owner's pending tasks and time budget."""

    @staticmethod
    def _parse_hh_mm_to_time(start_time: str) -> time:
        """Parse ``HH:MM`` (24-hour) into a :class:`datetime.time`."""
        parts = start_time.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour, minute)

    @classmethod
    def _task_start_end_datetimes(cls, task: Task) -> Tuple[datetime, datetime]:
        """
        Interval [start, end) for ``task`` on ``task.due_date`` using 24-hour ``start_time``
        and ``duration_mins`` (:func:`datetime.combine` + :class:`timedelta`).
        """
        day = task.due_date
        t0 = cls._parse_hh_mm_to_time(task.start_time)
        start_dt = datetime.combine(day, t0)
        end_dt = start_dt + timedelta(minutes=task.duration_mins)
        return start_dt, end_dt

    @staticmethod
    def check_for_conflicts(tasks: List[Task]) -> List[str]:
        """Detect pairwise time overlaps among tasks and return human-readable warnings.

        Each task is mapped to a half-open interval ``[start, end)`` on its ``due_date``
        using :func:`datetime.combine` for the ``HH:MM`` start and
        :class:`datetime.timedelta(minutes=...)` for the end (``start + duration``).

        Unordered pairs are visited via :func:`itertools.combinations`. Two intervals
        overlap with positive length if and only if ``max(s1, s2) < min(e1, e2)`` (the
        intersection is ``[max(s1,s2), min(e1,e2))``). Pet ownership is not considered.

        Args:
            tasks: Tasks to compare; typically the same list passed to scheduling output.

        Returns:
            Warning strings, one per overlapping pair, using 24-hour ``%H:%M`` times in
            the message body.
        """
        warnings: List[str] = []
        for a, b in combinations(tasks, 2):
            if a is b:
                continue
            sa, ea = Scheduler._task_start_end_datetimes(a)
            sb, eb = Scheduler._task_start_end_datetimes(b)
            overlap_start = max(sa, sb)
            overlap_end = min(ea, eb)
            if overlap_start >= overlap_end:
                continue
            warnings.append(
                f"Conflict: [{a.description}] and [{b.description}] overlap between "
                f"[{overlap_start.strftime('%H:%M')}] and [{overlap_end.strftime('%H:%M')}]."
            )
        return warnings

    @staticmethod
    def sort_by_time(tasks: List[Task]) -> List[Task]:
        """Return tasks sorted ascending by ``start_time`` (zero-padded ``HH:MM``).

        Args:
            tasks: Tasks whose ``start_time`` values use consistent two-digit hour and
                minute so lexicographic string order matches true chronological order.

        Returns:
            A new list of the same ``Task`` instances, ordered by ``start_time``.
        """
        return sorted(tasks, key=lambda t: t.start_time)

    @staticmethod
    def filter_tasks(
        owner: Owner,
        status: Optional[bool] = None,
        pet_name: Optional[str] = None,
    ) -> List[Task]:
        """Return tasks from ``owner`` matching optional completion and pet filters.

        Args:
            owner: Household whose ``iter_pet_tasks()`` pairs are scanned.
            status: If set, only tasks with this ``Task.is_completed`` value are kept.
            pet_name: If set, only tasks whose owning pet has this exact name are kept.

        Returns:
            ``Task`` instances that satisfy all supplied filters (AND logic); pet objects
            are not included in the list.
        """
        out: List[Task] = []
        for pet, task in owner.iter_pet_tasks():
            if status is not None and task.is_completed != status:
                continue
            if pet_name is not None and pet.name != pet_name:
                continue
            out.append(task)
        return out

    @staticmethod
    def handle_recurrence(pet: Pet, task: Task) -> Optional[Task]:
        """Complete a task and append the next Daily or Weekly occurrence to the pet.

        Delegates to :meth:`Pet.complete_task`, which calls :meth:`Task.mark_complete`.
        When ``Task.frequency`` is ``'Daily'`` or ``'Weekly'``, ``mark_complete``
        uses :class:`datetime.timedelta` with ``days=1`` or ``days=7`` to advance
        ``due_date`` on the cloned follow-up task while copying metadata fields.

        Args:
            pet: Pet that must already contain ``task`` in ``pet.tasks``.
            task: The concrete ``Task`` instance being finished.

        Returns:
            The new pending ``Task`` if recurrence applied, otherwise ``None``.
        """
        return pet.complete_task(task)

    @staticmethod
    def _is_walk_or_groom(task: Task) -> bool:
        """Tasks whose description indicates owner-attended walk or grooming."""
        d = task.description.lower()
        return "walk" in d or "groom" in d

    @staticmethod
    def _intervals_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
        """True iff [a0, a1) and [b0, b1) intersect with positive measure."""
        return not (a1 <= b0 or b1 <= a0)

    @classmethod
    def detect_walk_groom_conflicts(cls, scheduled: List[ScheduledSlot]) -> List[str]:
        """
        Safety check: reports cases where two Walk- or Grooming-class tasks for
        different pets occupy overlapping minutes on the owner's timeline.
        """
        conflicts: List[str] = []
        n = len(scheduled)
        for i in range(n):
            pet_i, task_i, s_i, e_i = scheduled[i]
            if not cls._is_walk_or_groom(task_i):
                continue
            for j in range(i + 1, n):
                pet_j, task_j, s_j, e_j = scheduled[j]
                if not cls._is_walk_or_groom(task_j):
                    continue
                if pet_i.name == pet_j.name:
                    continue
                if cls._intervals_overlap(s_i, e_i, s_j, e_j):
                    conflicts.append(
                        f"Overlap: '{task_i.description}' ({pet_i.name}, [{s_i},{e_i})) "
                        f"vs '{task_j.description}' ({pet_j.name}, [{s_j},{e_j}))."
                    )
        return conflicts

    @classmethod
    def _can_place_exclusive_safe(
        cls,
        start: int,
        end: int,
        pet: Pet,
        task: Task,
        placed: List[ScheduledSlot],
    ) -> bool:
        """
        Returns False if [start, end) overlaps another interval where both tasks
        are Walk/Groom-class and the pets differ (owner cannot do two at once).
        """
        new_ex = cls._is_walk_or_groom(task)
        for _p2, t2, s2, e2 in placed:
            if not cls._intervals_overlap(start, end, s2, e2):
                continue
            if new_ex and cls._is_walk_or_groom(t2) and _p2.name != pet.name:
                return False
        return True

    @classmethod
    def _find_earliest_safe_start(
        cls,
        pet: Pet,
        task: Task,
        placed: List[ScheduledSlot],
        horizon_mins: int,
    ) -> Optional[int]:
        """Earliest start minute in [0, horizon - duration] that passes the safety check."""
        d = task.duration_mins
        if d > horizon_mins:
            return None
        for s in range(0, horizon_mins - d + 1):
            e = s + d
            if cls._can_place_exclusive_safe(s, e, pet, task, placed):
                return s
        return None

    @staticmethod
    def _weighted_sort_key(task: Task) -> Tuple[float, int, int]:
        """
        Weighted priority: favor high priority per minute (density), then raw
        priority, then shorter tasks; fits more items in a fixed calendar window
        when combined with overlap-aware placement for non-exclusive work.
        """
        density = task.priority / max(task.duration_mins, 1)
        return (-density, -task.priority, task.duration_mins)

    @classmethod
    def _sort_tasks_for_scheduling(
        cls, pairs: List[Tuple[Pet, Task]]
    ) -> List[Tuple[Pet, Task]]:
        """Orders (pet, task) by weighted priority (descending density, etc.)."""
        return sorted(pairs, key=lambda pt: cls._weighted_sort_key(pt[1]))

    @staticmethod
    def filter_by_pet_name(owner: Owner, pet_name: str) -> List[Tuple[Pet, Task]]:
        """Tasks belonging to the pet with the given name (case-sensitive match)."""
        return [(p, t) for p, t in owner.iter_pet_tasks() if p.name == pet_name]

    @staticmethod
    def filter_by_category(owner: Owner, category: str) -> List[Tuple[Pet, Task]]:
        """
        Tasks whose category matches ``Task.category`` (case-insensitive).
        In PawPal+, the Streamlit UI stores the user's category string there.
        """
        c = category.strip().lower()
        if not c:
            return list(owner.iter_pet_tasks())
        return [
            (p, t)
            for p, t in owner.iter_pet_tasks()
            if (t.category or "").strip().lower() == c
        ]

    @staticmethod
    def filter_by_completion(owner: Owner, is_completed: bool) -> List[Tuple[Pet, Task]]:
        """Tasks with the given completion flag."""
        return [(p, t) for p, t in owner.iter_pet_tasks() if t.is_completed == is_completed]

    @classmethod
    def generate_plan(cls, owner: Owner, available_time: int) -> DailyPlan:
        """
        Produces a DailyPlan within a minute horizon. Tasks are placed on a shared
        timeline; Walk/Groom-class tasks for different pets cannot overlap. Other
        tasks may overlap, so calendar length (makespan) can be less than the sum
        of durations. Recurring tasks are always candidates even if completed.
        """
        all_pairs = list(owner.iter_pet_tasks())
        total_tasks = len(all_pairs)

        def is_schedulable(task: Task) -> bool:
            return (not task.is_completed) or task.is_recurring

        pending_pairs = [(p, t) for p, t in all_pairs if is_schedulable(t)]
        pending_count = len(pending_pairs)
        ordered = cls._sort_tasks_for_scheduling(pending_pairs)

        placed: List[ScheduledSlot] = []
        not_fitted: List[Task] = []

        for pet, task in ordered:
            start = cls._find_earliest_safe_start(pet, task, placed, available_time)
            if start is None:
                not_fitted.append(task)
                continue
            end = start + task.duration_mins
            placed.append((pet, task, start, end))

        placed.sort(key=lambda x: (x[2], x[0].name))
        selected = [t for _, t, _, _ in placed]
        makespan = max((e for *_, e in placed), default=0)

        conflict_messages = cls.detect_walk_groom_conflicts(placed)
        time_conflict_warnings = cls.check_for_conflicts(selected)
        explanation = cls._build_explanation(
            owner=owner,
            available_time=available_time,
            total_tasks_considered=total_tasks,
            pending_count=pending_count,
            selected=selected,
            not_fitted=not_fitted,
            conflict_messages=conflict_messages,
            time_conflict_warnings=time_conflict_warnings,
        )

        return DailyPlan(
            selected_tasks=selected,
            total_duration=makespan,
            explanation=explanation,
            scheduled_slots=placed,
            conflict_warnings=time_conflict_warnings,
        )

    @staticmethod
    def _build_explanation(
        owner: Owner,
        available_time: int,
        total_tasks_considered: int,
        pending_count: int,
        selected: List[Task],
        not_fitted: List[Task],
        conflict_messages: List[str],
        time_conflict_warnings: List[str],
    ) -> str:
        """Composes a short human-readable summary of scheduling decisions."""
        parts: List[str] = []
        pet_count = len(owner.pets)
        parts.append(
            f"Looked at {total_tasks_considered} task(s) across {pet_count} pet(s); "
            f"{pending_count} eligible (pending or recurring; one-off completed tasks skipped)."
        )
        parts.append(
            "Ordered by weighted priority: higher priority-per-minute first, then higher "
            "priority, then shorter tasks, so important short items tend to pack early and "
            "free the calendar for more work."
        )
        parts.append(
            "Walk/Groom-class tasks for different pets cannot overlap on the owner's timeline; "
            "other tasks may run in parallel when their intervals fit."
        )
        if time_conflict_warnings:
            parts.append(
                f"Time overlap notes: {len(time_conflict_warnings)} pair(s) conflict on "
                "declared start_time windows; see DailyPlan.conflict_warnings."
            )
        if conflict_messages:
            parts.append(
                "Safety note: internal conflict check reported issues; this should not "
                "happen after placement; review scheduled_slots."
            )
        if not selected:
            parts.append(
                "No tasks fit the available time; raise the time budget or shorten tasks."
            )
        elif not_fitted:
            skipped = len(not_fitted)
            highest_left = max(not_fitted, key=lambda t: t.priority)
            parts.append(
                f"Could not place {skipped} task(s) within {available_time} minutes without "
                f"violating walk/groom overlap rules or horizon; "
                f"highest priority among those left out is {highest_left.priority} "
                f"({highest_left.description})."
            )
        else:
            parts.append("All eligible tasks were placed within the available time horizon.")
        return " ".join(parts)


@dataclass
class DailyPlan:
    """Captures the chosen tasks, their total time, and why the plan looks this way."""

    selected_tasks: List[Task]
    total_duration: int
    explanation: str
    scheduled_slots: List[ScheduledSlot] = field(default_factory=list)
    conflict_warnings: List[str] = field(default_factory=list)

    @property
    def conflicts(self) -> List[str]:
        """Alias for :attr:`conflict_warnings` (declared-time overlap messages)."""
        return self.conflict_warnings

    def display_plan(self) -> str:
        """Returns a multi-line string suitable for logging or terminal display."""
        lines: List[str] = [self.explanation, "", "Selected tasks:"]
        if not self.selected_tasks:
            lines.append("  (none)")
        else:
            slot_by_id = {id(t): (p, s, e) for p, t, s, e in self.scheduled_slots}
            for t in self.selected_tasks:
                extra = ""
                if id(t) in slot_by_id:
                    _p, s, e = slot_by_id[id(t)]
                    extra = f" | {_p.name} | [{s},{e}) min"
                lines.append(
                    f"  - {t.description} | {t.duration_mins} min | "
                    f"priority {t.priority} | {t.category} | {t.frequency}{extra}"
                )
        lines.append(f"\nTotal scheduled: {self.total_duration} minutes (calendar makespan)")
        if self.conflict_warnings:
            lines.extend(["", "Time overlap warnings (start_time vs duration):"])
            for w in self.conflict_warnings:
                lines.append(f"  {w}")
        return "\n".join(lines)
