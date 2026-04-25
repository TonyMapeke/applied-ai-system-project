from datetime import date, time
from itertools import combinations

import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")

# Streamlit reruns this entire script on every widget change; without session_state,
# a new Owner would be created each time and you would lose pets/tasks. Only
# initialize when the key is missing so the same object survives across reruns.
if "owner" not in st.session_state:
    st.session_state["owner"] = Owner()
    st.session_state["owner_name"] = "Guest"

if "last_plan" not in st.session_state:
    st.session_state.last_plan = None

if "plan_conflict_detail" not in st.session_state:
    st.session_state.plan_conflict_detail = []


def _time_to_hhmm(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _conflict_messages_with_pets(owner: Owner) -> list[str]:
    """Human-readable overlap lines including pet names (same overlap rule as Scheduler)."""
    messages: list[str] = []
    pairs = list(owner.iter_pet_tasks())
    for (pet_a, task_a), (pet_b, task_b) in combinations(pairs, 2):
        if task_a is task_b:
            continue
        sa, ea = Scheduler._task_start_end_datetimes(task_a)
        sb, eb = Scheduler._task_start_end_datetimes(task_b)
        overlap_start = max(sa, sb)
        overlap_end = min(ea, eb)
        if overlap_start >= overlap_end:
            continue
        messages.append(
            f"**{pet_a.name}** — “{task_a.description}” **vs** **{pet_b.name}** — “{task_b.description}” "
            f"compete for **{overlap_start.strftime('%H:%M')}–{overlap_end.strftime('%H:%M')}** "
            f"on **{task_a.due_date.isoformat()}**."
        )
    return messages


st.title("🐾 PawPal+")

# Show completion feedback after rerun (toast/success are lost if fired immediately before st.rerun()).
if "_pawpal_feedback" in st.session_state:
    _kind, _text = st.session_state.pop("_pawpal_feedback")
    if _kind == "toast":
        st.toast(_text, icon="📅")
    else:
        st.success(_text)

st.markdown(
    """
Plan pet care tasks, attach them to pets, and generate a schedule that fits your available time.
"""
)

with st.expander("Scenario", expanded=False):
    st.markdown(
        """
**PawPal+** helps a pet owner plan care tasks based on time, priority, and preferences.
Add pets, add tasks to each pet, then generate a daily plan.
"""
    )

st.divider()

owner = st.session_state.owner
st.session_state.owner_name = st.text_input(
    "Owner display name",
    value=st.session_state.get("owner_name", "Guest"),
)

st.subheader("Pets")
col_pet_a, col_pet_b = st.columns(2)
with col_pet_a:
    new_pet_name = st.text_input("Pet name", value="Mochi", key="new_pet_name")
with col_pet_b:
    new_pet_species = st.text_input("Species", value="dog", key="new_pet_species")

if st.button("Add Pet"):
    name = new_pet_name.strip()
    species = new_pet_species.strip() or "unknown"
    if not name:
        st.warning("Please enter a pet name.")
    else:
        owner.add_pet(Pet(name=name, species=species))
        st.success(f"Added {name} ({species}).")
        st.rerun()

if owner.pets:
    st.caption("Your pets:")
    for p in owner.pets:
        st.write(f"- **{p.name}** ({p.species}) — {len(p.tasks)} task(s)")
else:
    st.info("No pets yet. Add at least one pet to unlock tasks and scheduling.")

st.divider()

has_pets = len(owner.pets) > 0
total_tasks = len(owner.get_all_tasks()) if has_pets else 0
if has_pets and total_tasks == 0:
    st.session_state.last_plan = None
    st.session_state.plan_conflict_detail = []

if has_pets:
    st.subheader("Tasks")
    st.caption(
        "Pick a pet, then add a task. Category is Task.category; "
        "recurrence is Task.frequency (None / Daily / Weekly). Start time is used for preview sort and overlap checks."
    )

    pet_labels = [f"{p.name} ({p.species})" for p in owner.pets]
    chosen_label = st.selectbox("Pet for this task", options=pet_labels, key="task_pet_select")
    pet_index = pet_labels.index(chosen_label)
    selected_pet = owner.pets[pet_index]

    t1, t2 = st.columns(2)
    with t1:
        task_description = st.text_input("Description", value="Morning walk", key="task_desc")
    with t2:
        task_category = st.text_input("Category", value="exercise", key="task_cat")

    t3, t4 = st.columns(2)
    with t3:
        task_duration = st.number_input(
            "Duration (minutes)",
            min_value=1,
            max_value=480,
            value=20,
            key="task_dur",
        )
    with t4:
        priority_label = st.selectbox(
            "Priority",
            ["low", "medium", "high"],
            index=2,
            key="task_pri",
        )

    task_start_time = st.time_input(
        "Start time (24h)",
        value=time(9, 0),
        key="task_start_time",
    )

    priority_value = {"low": 3, "medium": 6, "high": 9}[priority_label]
    task_recurrence = st.selectbox(
        "Recurrence (frequency)",
        ["None", "Daily", "Weekly"],
        index=0,
        key="task_recurrence",
    )
    task_recurring = st.checkbox(
        "Also include in every plan while done (is_recurring flag)",
        value=False,
        key="task_recurring",
    )

    if st.button("Add Task"):
        desc = task_description.strip()
        if not desc:
            st.warning("Please enter a task description.")
        else:
            selected_pet.add_task(
                Task(
                    description=desc,
                    duration_mins=int(task_duration),
                    priority=priority_value,
                    frequency=task_recurrence,
                    category=task_category.strip() or "general",
                    is_recurring=task_recurring,
                    start_time=_time_to_hhmm(task_start_time),
                    due_date=date.today(),
                )
            )
            st.success(f"Task added for **{selected_pet.name}**.")
            st.rerun()

    st.divider()

    if total_tasks == 0:
        st.info("You have not added any tasks yet. Add at least one task to see a chronological preview and generate a plan.")
    else:
        st.subheader("Preview (chronological)")
        st.caption("All tasks across your pets, ordered with `Scheduler.sort_by_time()` before you generate a plan.")
        all_tasks = owner.get_all_tasks()
        sorted_tasks = Scheduler.sort_by_time(all_tasks)
        pet_by_task_id = {id(t): p.name for p, t in owner.iter_pet_tasks()}
        preview_rows = [
            {
                "Pet": pet_by_task_id[id(t)],
                "Description": t.description,
                "Start": t.start_time,
                "Duration (min)": t.duration_mins,
                "Priority": t.priority,
                "Category": t.category,
                "Recurrence": t.frequency,
                "Done": "Yes" if t.is_completed else "No",
            }
            for t in sorted_tasks
        ]
        st.dataframe(preview_rows, use_container_width=True, hide_index=True)

        st.subheader("Mark tasks complete")
        st.caption("Daily/Weekly tasks get the next occurrence appended automatically.")
        for pet, task in list(owner.iter_pet_tasks()):
            cb_key = f"complete_cb_{id(task)}"
            was_completed = task.is_completed
            checked = st.checkbox(
                f"**{pet.name}** — {task.description} ({task.start_time}, {task.duration_mins} min)",
                value=was_completed,
                disabled=was_completed,
                key=cb_key,
            )
            if checked and not was_completed:
                next_task = pet.complete_task(task)
                if next_task is not None:
                    st.session_state["_pawpal_feedback"] = (
                        "toast",
                        f"Next {next_task.frequency} occurrence added (due {next_task.due_date.isoformat()}).",
                    )
                else:
                    st.session_state["_pawpal_feedback"] = ("success", "Task marked complete.")
                st.rerun()

    st.divider()

    st.subheader("Build schedule")
    available_time = st.number_input(
        "Available time (minutes)",
        min_value=1,
        max_value=1440,
        value=60,
        key="avail_time",
    )

    if st.button("Generate Schedule"):
        tasks_for_check = owner.get_all_tasks()
        conflict_warnings = Scheduler.check_for_conflicts(tasks_for_check)
        st.session_state.plan_conflict_detail = (
            _conflict_messages_with_pets(owner) if conflict_warnings else []
        )
        st.session_state.last_plan = Scheduler.generate_plan(
            owner,
            available_time=int(available_time),
        )
        st.rerun()

else:
    st.session_state.last_plan = None
    st.session_state.plan_conflict_detail = []

if st.session_state.last_plan is not None and has_pets:
    plan = st.session_state.last_plan
    st.divider()
    st.subheader("Results")

    if st.session_state.plan_conflict_detail:
        st.warning("**Calendar overlap detected** — these pets/tasks compete for the same time window:")
        for msg in st.session_state.plan_conflict_detail:
            st.warning(msg)

    col_plan, col_explain = st.columns(2)
    with col_plan:
        st.markdown("#### Selected plan")
        if plan.selected_tasks:
            slot_by_id = {id(t): (p, s, e) for p, t, s, e in plan.scheduled_slots}
            rows = []
            for t in plan.selected_tasks:
                pet_name = ""
                window = ""
                if id(t) in slot_by_id:
                    p, s, e = slot_by_id[id(t)]
                    pet_name = p.name
                    window = f"[{s}, {e}) min"
                rows.append(
                    {
                        "Pet": pet_name,
                        "Description": t.description,
                        "Window": window,
                        "Minutes": t.duration_mins,
                        "Priority": t.priority,
                        "Category": t.category,
                        "Recurrence": t.frequency,
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No tasks fit this time window.")
        st.caption(f"Total scheduled time: **{plan.total_duration}** minutes.")

    with col_explain:
        st.markdown("#### Scheduler explanation")
        st.markdown(plan.explanation)
        if plan.conflict_warnings:
            st.caption("Declared-time overlap among **selected** tasks:")
            for msg in plan.conflict_warnings:
                st.warning(msg)
