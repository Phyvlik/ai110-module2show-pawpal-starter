import streamlit as st

from pawpal_system import Owner, Pet, Task, Scheduler, Priority, TimeOfDay, Frequency

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="PawPal+", layout="centered")
st.title("PawPal+")
st.caption("Your smart daily pet care planner.")

# ---------------------------------------------------------------------------
# Session state — initialize once per browser session
# ---------------------------------------------------------------------------
if "owner" not in st.session_state:
    st.session_state.owner: Owner | None = None


# ---------------------------------------------------------------------------
# Sidebar — Owner setup
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Owner Setup")
    owner_name = st.text_input("Your name", value="Jordan")
    available_mins = st.number_input(
        "Available time today (minutes)", min_value=10, max_value=720, value=180, step=10
    )
    preferred_time = st.selectbox(
        "Preferred time of day",
        options=[t.value for t in TimeOfDay],
        index=0,
    )

    if st.button("Save owner", use_container_width=True):
        st.session_state.owner = Owner(
            name=owner_name,
            available_minutes_per_day=int(available_mins),
            preferred_schedule=TimeOfDay(preferred_time),
        )
        st.success(f"Owner '{owner_name}' saved!")

# Guard: nothing works without an Owner
if st.session_state.owner is None:
    st.info("Fill in your name in the sidebar and click **Save owner** to get started.")
    st.stop()

owner: Owner = st.session_state.owner


# ---------------------------------------------------------------------------
# Section 1 — Pets
# ---------------------------------------------------------------------------
st.subheader("1. Your Pets")

with st.expander("Add a new pet", expanded=len(owner.pets) == 0):
    with st.form("add_pet_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            pet_name    = st.text_input("Pet name", value="Mochi")
            pet_species = st.selectbox("Species", ["dog", "cat", "rabbit", "bird", "other"])
        with col2:
            pet_breed = st.text_input("Breed (optional)")
            pet_age   = st.number_input("Age (years)", min_value=0.0, max_value=30.0, value=2.0, step=0.5)
        pet_needs = st.text_input("Special needs (comma-separated, optional)")

        if st.form_submit_button("Add pet"):
            if not pet_name.strip():
                st.error("Pet name cannot be empty.")
            elif owner.get_pet(pet_name.strip()):
                st.error(f"A pet named '{pet_name}' already exists.")
            else:
                needs = [n.strip() for n in pet_needs.split(",") if n.strip()]
                owner.add_pet(Pet(
                    name=pet_name.strip(),
                    species=pet_species,
                    breed=pet_breed.strip(),
                    age_years=pet_age,
                    special_needs=needs,
                ))
                st.success(f"Added {pet_name.strip()} the {pet_species}!")
                st.rerun()

if owner.pets:
    for pet in owner.pets:
        label = f"{pet.name} ({pet.species}"
        label += f", {pet.breed}" if pet.breed else ""
        label += f", {pet.age_years:.1f} yrs)"
        done  = sum(1 for t in pet.tasks if t.completed)
        total = len(pet.tasks)
        st.markdown(
            f"- **{label}** — {total} task(s), {pet.total_care_minutes()} min total"
            + (f", {done}/{total} done" if total else "")
        )
else:
    st.caption("No pets added yet.")


# ---------------------------------------------------------------------------
# Section 2 — Tasks
# ---------------------------------------------------------------------------
st.divider()
st.subheader("2. Care Tasks")

if not owner.pets:
    st.caption("Add a pet first before adding tasks.")
else:
    with st.expander("Add a task to a pet", expanded=True):
        with st.form("add_task_form", clear_on_submit=True):
            pet_choice = st.selectbox("Pet", options=[p.name for p in owner.pets])
            col1, col2, col3 = st.columns(3)
            with col1:
                task_title    = st.text_input("Task title", value="Morning walk")
                task_category = st.selectbox(
                    "Category", ["walk", "feeding", "meds", "grooming", "enrichment", "general"]
                )
            with col2:
                task_duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
                task_priority = st.selectbox("Priority", [p.value for p in Priority], index=1)
            with col3:
                task_time  = st.selectbox("Preferred time", [t.value for t in TimeOfDay], index=3)
                task_recur = st.checkbox("Recurring")
                task_freq  = st.selectbox(
                    "Frequency", [f.value for f in Frequency if f != Frequency.ONCE],
                    disabled=not task_recur,
                )
            task_notes = st.text_input("Notes (optional)")

            if st.form_submit_button("Add task"):
                if not task_title.strip():
                    st.error("Task title cannot be empty.")
                else:
                    owner.get_pet(pet_choice).add_task(Task(
                        title=task_title.strip(),
                        duration_minutes=int(task_duration),
                        priority=Priority(task_priority),
                        category=task_category,
                        preferred_time=TimeOfDay(task_time),
                        recurring=task_recur,
                        frequency=Frequency(task_freq) if task_recur else Frequency.ONCE,
                        notes=task_notes.strip(),
                    ))
                    st.success(f"Added '{task_title.strip()}' to {pet_choice}.")
                    st.rerun()

    # Filter controls
    st.markdown("**View tasks**")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filter_pet = st.selectbox(
            "Filter by pet", ["All"] + [p.name for p in owner.pets], key="filter_pet"
        )
    with col_f2:
        filter_status = st.selectbox(
            "Filter by status", ["All", "Incomplete", "Complete"], key="filter_status"
        )

    # Build filtered task table
    all_pairs = owner.all_tasks()
    if filter_pet != "All":
        all_pairs = [(p, t) for p, t in all_pairs if p.name == filter_pet]
    if filter_status == "Incomplete":
        all_pairs = [(p, t) for p, t in all_pairs if not t.completed]
    elif filter_status == "Complete":
        all_pairs = [(p, t) for p, t in all_pairs if t.completed]

    if all_pairs:
        rows = []
        for pet, task in all_pairs:
            rows.append({
                "Pet": pet.name,
                "Task": task.title,
                "Duration (min)": task.duration_minutes,
                "Priority": task.priority.value,
                "Time": task.preferred_time.value,
                "Recurring": f"Yes ({task.frequency.value})" if task.recurring else "No",
                "Done": "Yes" if task.completed else "No",
            })
        st.table(rows)
    else:
        st.caption("No tasks match the selected filters.")


# ---------------------------------------------------------------------------
# Section 3 — Generate Schedule
# ---------------------------------------------------------------------------
st.divider()
st.subheader("3. Generate Schedule")

total_req   = owner.total_required_minutes()
time_ok     = owner.has_enough_time()
col1, col2, col3 = st.columns(3)
col1.metric("Tasks total", f"{total_req} min")
col2.metric("Available", f"{owner.available_minutes_per_day} min")
col3.metric("Fits in day?", "Yes" if time_ok else "Partial — some tasks will be skipped")

if not time_ok:
    st.warning(
        f"Your tasks need **{total_req} min** but you only have "
        f"**{owner.available_minutes_per_day} min** today. "
        "Lower-priority tasks will be skipped automatically."
    )

if not owner.pets or not any(p.tasks for p in owner.pets):
    st.caption("Add at least one task to generate a schedule.")
else:
    if st.button("Generate schedule", type="primary", use_container_width=True):
        scheduler = Scheduler(owner)
        schedule  = scheduler.generate_schedule()
        conflicts = scheduler.detect_conflicts()

        if not schedule:
            st.warning("No tasks could be scheduled. Increase your available time or reduce task durations.")
        else:
            scheduled_mins = sum(s.task.duration_minutes for s in schedule)
            skipped_mins   = total_req - scheduled_mins

            st.success(
                f"Scheduled **{len(schedule)} task(s)** across **{len(owner.pets)} pet(s)** "
                f"({scheduled_mins} min used)."
            )

            # Conflict banner — shown before the table so it is prominent
            if conflicts:
                st.error(
                    f"**{len(conflicts)} scheduling conflict(s) detected.** "
                    "The following tasks overlap in time — consider adjusting durations or available hours."
                )
                for a, b in conflicts:
                    st.markdown(
                        f"- **{a.task.title}** ({a.start_time_str()}-{a.end_time_str()}) "
                        f"overlaps **{b.task.title}** ({b.start_time_str()}-{b.end_time_str()})"
                    )

            # Schedule table — sorted by start time
            st.markdown("**Today's plan (sorted by time):**")
            sorted_schedule = scheduler.sort_by_time()
            rows = []
            for item in sorted_schedule:
                rows.append({
                    "Time": f"{item.start_time_str()} - {item.end_time_str()}",
                    "Pet": item.pet.name,
                    "Task": item.task.title,
                    "Priority": item.priority.value if hasattr(item, "priority") else item.task.priority.value,
                    "Recurring": "Yes" if item.task.recurring else "No",
                    "Why": item.reason,
                })
            st.table(rows)

            if skipped_mins:
                st.warning(
                    f"**{skipped_mins} min** of lower-priority tasks were skipped "
                    "because there was not enough time today."
                )
            else:
                st.info("All tasks fit within today's available time.")

            # Recurring renewal notice
            recurring_done = [s for s in schedule if s.task.recurring and s.task.completed]
            if recurring_done:
                st.markdown("**Recurring tasks ready to renew:**")
                renewed = scheduler.renew_recurring_tasks()
                for t in renewed:
                    st.success(
                        f"'{t.title}' marked complete — next occurrence created for **{t.due_date}**."
                    )
