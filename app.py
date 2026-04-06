import streamlit as st

from pawpal_system import Owner, Pet, Task, Scheduler, Priority, TimeOfDay

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="PawPal+", layout="centered")
st.title("PawPal+")

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
# Section 1 — Add a Pet
# ---------------------------------------------------------------------------
st.subheader("1. Your Pets")

with st.expander("Add a new pet", expanded=len(owner.pets) == 0):
    with st.form("add_pet_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            pet_name    = st.text_input("Pet name", value="Mochi")
            pet_species = st.selectbox("Species", ["dog", "cat", "rabbit", "bird", "other"])
        with col2:
            pet_breed   = st.text_input("Breed (optional)")
            pet_age     = st.number_input("Age (years)", min_value=0.0, max_value=30.0, value=2.0, step=0.5)
        pet_needs = st.text_input("Special needs (comma-separated, optional)")

        submitted = st.form_submit_button("Add pet")
        if submitted:
            if not pet_name.strip():
                st.error("Pet name cannot be empty.")
            elif owner.get_pet(pet_name.strip()):
                st.error(f"A pet named '{pet_name}' already exists.")
            else:
                needs = [n.strip() for n in pet_needs.split(",") if n.strip()]
                new_pet = Pet(
                    name=pet_name.strip(),
                    species=pet_species,
                    breed=pet_breed.strip(),
                    age_years=pet_age,
                    special_needs=needs,
                )
                owner.add_pet(new_pet)
                st.success(f"Added {new_pet.name} the {pet_species}!")
                st.rerun()

# Show existing pets
if owner.pets:
    for pet in owner.pets:
        label = f"{pet.name} ({pet.species}"
        label += f", {pet.breed}" if pet.breed else ""
        label += f", {pet.age_years:.1f} yrs)"
        st.markdown(f"- **{label}** — {len(pet.tasks)} task(s), {pet.total_care_minutes()} min total")
else:
    st.caption("No pets added yet.")

# ---------------------------------------------------------------------------
# Section 2 — Add Tasks
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
                task_category = st.selectbox("Category", ["walk", "feeding", "meds", "grooming", "enrichment", "general"])
            with col2:
                task_duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
                task_priority = st.selectbox("Priority", [p.value for p in Priority], index=1)
            with col3:
                task_time   = st.selectbox("Preferred time", [t.value for t in TimeOfDay], index=3)
                task_recur  = st.checkbox("Recurring daily")
            task_notes = st.text_input("Notes (optional)")

            submitted = st.form_submit_button("Add task")
            if submitted:
                if not task_title.strip():
                    st.error("Task title cannot be empty.")
                else:
                    target_pet = owner.get_pet(pet_choice)
                    new_task = Task(
                        title=task_title.strip(),
                        duration_minutes=int(task_duration),
                        priority=Priority(task_priority),
                        category=task_category,
                        preferred_time=TimeOfDay(task_time),
                        recurring=task_recur,
                        notes=task_notes.strip(),
                    )
                    target_pet.add_task(new_task)
                    st.success(f"Added '{new_task.title}' to {target_pet.name}.")
                    st.rerun()

    # Show all tasks per pet
    for pet in owner.pets:
        if pet.tasks:
            st.markdown(f"**{pet.name}'s tasks:**")
            rows = []
            for t in pet.tasks:
                rows.append({
                    "Title": t.title,
                    "Duration (min)": t.duration_minutes,
                    "Priority": t.priority.value,
                    "Time": t.preferred_time.value,
                    "Recurring": "Yes" if t.recurring else "No",
                    "Done": "Yes" if t.completed else "No",
                })
            st.table(rows)

# ---------------------------------------------------------------------------
# Section 3 — Generate Schedule
# ---------------------------------------------------------------------------
st.divider()
st.subheader("3. Generate Schedule")

time_ok = owner.has_enough_time()
total_req = owner.total_required_minutes()
col1, col2, col3 = st.columns(3)
col1.metric("Tasks total", f"{total_req} min")
col2.metric("Available", f"{owner.available_minutes_per_day} min")
col3.metric("Fits?", "Yes" if time_ok else "No (tasks will be skipped)")

if not owner.pets or not any(p.tasks for p in owner.pets):
    st.caption("Add at least one task to generate a schedule.")
else:
    if st.button("Generate schedule", type="primary", use_container_width=True):
        scheduler = Scheduler(owner)
        schedule  = scheduler.generate_schedule()
        conflicts = scheduler.detect_conflicts()

        if not schedule:
            st.warning("No tasks could be scheduled. Check your available time.")
        else:
            st.success(f"Scheduled {len(schedule)} task(s) across {len(owner.pets)} pet(s).")

            # Build display table
            rows = []
            for st_item in schedule:
                rows.append({
                    "Time": f"{st_item.start_time_str()} - {st_item.end_time_str()}",
                    "Pet": st_item.pet.name,
                    "Task": st_item.task.title,
                    "Priority": st_item.task.priority.value,
                    "Why": st_item.reason,
                })
            st.table(rows)

            skipped = total_req - sum(s.task.duration_minutes for s in schedule)
            if skipped:
                st.warning(f"{skipped} minutes of tasks were skipped — not enough time today.")

            if conflicts:
                st.error(f"{len(conflicts)} conflict(s) detected:")
                for a, b in conflicts:
                    st.markdown(f"- **{a.task.title}** overlaps with **{b.task.title}**")
            else:
                st.info("No scheduling conflicts.")
