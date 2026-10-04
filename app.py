"""Interactive field-station interface for the simulated cocoa decision demo."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from agent import create_and_log_recommendation
from data.seed import PLOTS, generate_seed_data


ROOT = Path(__file__).parent
LOGO = ROOT / "assets" / "cocoa-field-station-logo.svg"

st.set_page_config(
    page_title="Cocoa Field Station",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()
db.seed_weather(generate_seed_data())
st.session_state.setdefault("started", False)
st.session_state.setdefault("current_recommendation", None)
st.session_state.setdefault("selected_plot", "Plot A")
st.session_state.setdefault("workspace_view", "Plot monitor")

ACTION_ICONS = {
    "spray": ":material/water_drop:",
    "wait": ":material/hourglass_empty:",
    "inspect": ":material/search:",
}


def select_plot(plot_id):
    """Apply plot-card changes before keyed sidebar widgets are instantiated."""
    st.session_state.selected_plot = plot_id
    st.session_state.current_recommendation = None


def show_home():
    """Give first-time visitors a clear, confident entry into the demo."""
    st.badge("FIELD INTELLIGENCE · DEMO", icon=":material/science:", color="orange")
    hero_left, hero_right = st.columns([1.35, 0.65], vertical_alignment="center")
    with hero_left:
        st.title("Better field decisions start with a clearer picture.", icon=":material/eco:")
        st.write(
            "Cocoa Field Station brings plot conditions, transparent recommendations, "
            "and grower judgement into one calm workspace."
        )
        preview_plot = st.selectbox("Choose a plot to explore", list(PLOTS), key="home_plot")
        preview = pd.DataFrame(db.weather_for_plot(preview_plot, limit=7))
        if not preview.empty:
            metric_a, metric_b, metric_c = st.columns(3)
            metric_a.metric("Recent rainfall", f"{preview['rainfall_mm'].sum():.1f} mm")
            metric_b.metric("Average humidity", f"{preview['humidity_pct'].mean():.0f}%")
            metric_c.metric("Observations", len(preview))
        if st.button("Enter field station", type="primary", icon=":material/arrow_forward:"):
            st.session_state.started = True
            st.session_state.selected_plot = preview_plot
            st.rerun()
    with hero_right:
        with st.container(border=True):
            if LOGO.exists():
                st.image(str(LOGO), width=150)
            st.subheader("Observe → Review → Decide")
            st.write("Recent conditions become an explainable suggestion, with the final call always in human hands.")
            st.caption("A focused prototype for cocoa plot monitoring.")
    st.space("small")
    with st.container(border=True):
        step_cols = st.columns(4)
        for col, number, title, detail in zip(
            step_cols,
            ("01", "02", "03", "04"),
            ("Observe", "Understand", "Decide", "Learn"),
            ("Compare plot conditions", "Review evidence and confidence", "Approve or record an override", "Keep a decision history"),
        ):
            with col:
                st.caption(number)
                st.markdown(f"**{title}**")
                st.caption(detail)
    st.caption("Demo data is simulated. Agronomy thresholds are unverified placeholders; suggestions are not farm advice.")


def show_authentication():
    """Render the configured identity-provider entry point."""
    st.badge("SECURE SIGN-IN", icon=":material/verified_user:", color="green")
    st.title("Welcome to your field station")
    st.write("Sign in to continue, or create an account through the identity provider.")
    sign_in_or_up = st.segmented_control(
        "Choose an account option", ["Sign in", "Create account"],
        default="Sign in", key="auth_mode",
    )
    try:
        auth_config = st.secrets.get("auth", {})
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        auth_config = {}
    google_config = auth_config.get("google") if hasattr(auth_config, "get") else None

    left, right = st.columns([1, 1])
    with left:
        with st.container(border=True):
            st.subheader("Continue with Google", icon=":material/account_circle:")
            if sign_in_or_up == "Create account":
                st.write("Continue to Google to sign in. You can create a Google account in Google's sign-in flow if you need one.")
            else:
                st.write("Your password stays with Google; this app never asks for it.")
            if google_config:
                if st.button("Continue with Google", type="primary", icon=":material/login:"):
                    st.login("google")
            else:
                st.info(
                    "Google sign-in is not configured yet. Add OAuth details to `.streamlit/secrets.toml`; setup steps are in the README.",
                    icon=":material/settings:",
                )
    with right:
        with st.container(border=True):
            st.subheader("Private by design", icon=":material/lock:")
            st.write("Authentication uses OpenID Connect. The app receives your verified name and email, and does not store a password.")
            st.caption("Plot and decision data remains shared in this prototype's local SQLite database.")

    if st.button("Back to welcome page", icon=":material/arrow_back:"):
        st.session_state.started = False
        st.rerun()


def show_sidebar():
    with st.sidebar:
        if LOGO.exists():
            st.logo(str(LOGO), size="large")
        st.caption("COCOA FIELD STATION")
        st.markdown("### Your workspace")
        st.radio(
            "Workspace", ["Plot monitor", "Decision journal"],
            key="workspace_view", label_visibility="collapsed",
            horizontal=False,
        )
        st.space("small")
        st.caption("ACTIVE PLOT")
        selected_plot = st.selectbox("Select a plot", list(PLOTS), key="selected_plot")
        st.caption(PLOTS[selected_plot])
        st.space("small")
        st.caption("ACCOUNT")
        name = st.user.get("name") or st.user.get("email") or "Signed in"
        st.caption(name)
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            st.logout()
        st.caption("SIMULATED DATA · NOT FARM ADVICE")


def get_plot_metrics(plot_id):
    observations = db.weather_for_plot(plot_id, limit=7)
    frame = pd.DataFrame(observations)
    if frame.empty:
        return frame, 0.0, 0.0, 0
    return frame, float(frame["rainfall_mm"].sum()), float(frame["humidity_pct"].mean()), len(frame)


def show_plot_picker():
    st.caption("FIELD OVERVIEW  /  PLOTS")
    st.title("Your plots", icon=":material/eco:")
    st.write("Select a station to review its conditions and the latest decision.")
    cols = st.columns(3)
    for col, (plot, description) in zip(cols, PLOTS.items()):
        observations, rain, humidity, count = get_plot_metrics(plot)
        active = st.session_state.selected_plot == plot
        with col:
            with st.container(border=True, height="stretch"):
                st.badge("ACTIVE STATION" if active else "FIELD PLOT", color="green" if active else "gray")
                st.subheader(plot)
                st.caption(description)
                a, b = st.columns(2)
                a.metric("Rain · recent", f"{rain:.1f} mm", chart_data=observations["rainfall_mm"].tolist() if not observations.empty else [])
                b.metric("Mean humidity", f"{humidity:.0f}%")
                st.caption(f"{count} recent weather observations")
                st.button(
                    "Open station" if not active else "Station selected",
                    key=f"select-{plot}",
                    type="primary" if active else "secondary",
                    icon=":material/arrow_forward:",
                    width="stretch",
                    on_click=select_plot,
                    args=(plot,),
                )


def show_plot_monitor(plot_id):
    observations = db.weather_for_plot(plot_id)
    frame = pd.DataFrame(observations)
    st.caption(f"FIELD OVERVIEW  /  {plot_id.upper()}")
    top_left, top_right = st.columns([1.4, 0.6], vertical_alignment="center")
    with top_left:
        st.title(plot_id, icon=":material/eco:")
        st.write(PLOTS[plot_id])
    with top_right:
        st.badge("SIMULATED FIELD DATA", icon=":material/science:", color="orange")

    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
        recent = frame.tail(7)
        summary = st.columns(4)
        summary[0].metric("Rainfall · 7 readings", f"{recent['rainfall_mm'].sum():.1f} mm")
        summary[1].metric("Humidity · average", f"{recent['humidity_pct'].mean():.0f}%")
        summary[2].metric("Temperature · average", f"{recent['temp_c'].mean():.1f} °C")
        summary[3].metric("Latest reading", frame["date"].iloc[-1].strftime("%d %b"))

    left, right = st.columns([1.55, 0.85], gap="large")
    with left:
        with st.container(border=True):
            chart_head, chart_select = st.columns([1.2, 0.8], vertical_alignment="center")
            with chart_head:
                st.subheader("Field conditions", icon=":material/monitoring:")
                st.caption("Explore recent observations")
            with chart_select:
                measure = st.selectbox("Measure", ["Rainfall", "Humidity", "Temperature"], label_visibility="collapsed", key="measure")
            days = st.pills("Time window", [7, 14, 30], default=14, format_func=lambda n: f"{n} days", key="days_window")
            days = days or 14
            columns = {
                "Rainfall": ("rainfall_mm", "Rainfall (mm)", "Daily rainfall across the selected window"),
                "Humidity": ("humidity_pct", "Humidity (%)", "Daily humidity across the selected window"),
                "Temperature": ("temp_c", "Temperature (°C)", "Daily temperature across the selected window"),
            }
            value_col, label, alt = columns[measure]
            window = frame.tail(days)
            st.line_chart(window, x="date", y=value_col, y_label=label, alt=alt)
            with st.expander("View observation journal", icon=":material/notes:"):
                display = window[["date", "rainfall_mm", "humidity_pct", "temp_c", "days_since_last_spray", "inspection_note"]].copy()
                display.columns = ["Date", "Rain (mm)", "Humidity (%)", "Temperature (°C)", "Days since spray", "Inspection note"]
                st.dataframe(display, hide_index=True, width="stretch", alt="Weather observations and inspection notes for this plot")

    with right:
        result = st.session_state.current_recommendation
        if result and result.get("plot_id") != plot_id:
            result = None
        if result:
            saved = db.get_decision(result["id"])
            result["pending"] = bool(saved and saved["human_decision"] is None)
            with st.container(border=True):
                st.badge("Awaiting your review" if result["pending"] else "Decision recorded", icon=":material/pending:" if result["pending"] else ":material/check_circle:", color="orange" if result["pending"] else "green")
                st.subheader(f"Suggested: {result['action'].title()}", icon=ACTION_ICONS.get(result["action"]))
                st.write(result["rationale"])
                scores = st.columns(2)
                scores[0].metric("Confidence", f"{result['confidence']:.0%}")
                scores[1].metric("Risk", result["risk_bucket"].title())
                st.caption("Inspection required" if result["gated"] else "Confidence gate passed")
                with st.expander("Recommendation evidence", expanded=True, icon=":material/lightbulb:"):
                    for evidence in result["evidence"]:
                        st.markdown(f"- {evidence}")
                    citations = result["cited_case_ids"]
                    st.caption("Past override cases: " + ", ".join(f"#{case_id}" for case_id in citations) if citations else "No similar override cases cited.")

                if result["pending"]:
                    st.markdown("**Record your decision**")
                    actions = [choice for choice in ("spray", "wait", "inspect") if choice != result["action"]]
                    with st.form(f"human-review-{result['id']}"):
                        choice = st.selectbox("Your decision", ["Keep suggestion", *actions])
                        reason = st.text_input("Reason (required for an override)", placeholder="Add context for the decision log")
                        submitted = st.form_submit_button("Save decision", type="primary", icon=":material/how_to_reg:", width="stretch")
                    if submitted:
                        if choice == "Keep suggestion":
                            db.record_human_decision(result["id"], result["action"])
                            st.toast("Approval added to the decision journal.", icon=":material/check_circle:")
                            st.rerun()
                        elif not reason.strip():
                            st.error("Add a short reason for this override.")
                        else:
                            db.record_human_decision(result["id"], choice, reason.strip())
                            st.toast("Override saved with your reason.", icon=":material/history:")
                            st.rerun()
                else:
                    decision_text = f"Recorded decision: **{result.get('human_decision') or result['action']}**"
                    if result.get("human_reason"):
                        decision_text += f" · {result['human_reason']}"
                    st.success(decision_text)
                if st.button("Refresh recommendation", icon=":material/refresh:", width="stretch"):
                    with st.spinner("Reviewing recent conditions…"):
                        st.session_state.current_recommendation = create_and_log_recommendation(plot_id)
                    st.rerun()
        else:
            with st.container(border=True):
                st.badge("HUMAN REVIEW REQUIRED", icon=":material/person_check:", color="blue")
                st.subheader("A clearer next step")
                st.write("Generate a fresh reading from the latest observations. Review the evidence before recording any decision.")
                st.caption("The assistant offers a suggestion; it never acts on the plot.")
                if st.button("Review this plot", type="primary", icon=":material/psychology:", width="stretch"):
                    with st.spinner("Reviewing recent conditions…"):
                        st.session_state.current_recommendation = create_and_log_recommendation(plot_id)
                    st.rerun()
    st.caption("Prototype only · Weather is simulated · Agronomy thresholds are unverified placeholders")


def show_journal():
    st.caption("FIELD OVERVIEW  /  DECISION JOURNAL")
    st.title("Decision journal", icon=":material/history:")
    st.write("A transparent record of suggestions, grower decisions, and the reasons behind overrides.")
    rows = db.audit_log()
    if not rows:
        st.info("The journal is empty. Open a plot and create its first reading.", icon=":material/auto_stories:")
        return
    records = []
    for row in rows:
        records.append({
            "#": row["id"], "Plot": row["plot_id"], "Time": row["ts"],
            "Risk": row["risk_bucket"].title(), "Suggestion": row["recommendation"].title(),
            "Confidence": row["confidence"], "Gate": "Inspect" if row["gated"] else "Clear",
            "Human decision": (row["human_decision"] or "Awaiting review").title(),
            "Reason": row["human_reason"] or "—",
            "Evidence": "; ".join(json.loads(row["evidence_json"])),
        })
    journal = pd.DataFrame(records)
    filters = st.columns([1, 1, 2], vertical_alignment="bottom")
    with filters[0]:
        plot_filter = st.selectbox("Plot", ["All plots", *PLOTS.keys()])
    with filters[1]:
        decision_filter = st.selectbox("Status", ["All decisions", "Awaiting review", "Recorded"])
    if plot_filter != "All plots":
        journal = journal[journal["Plot"] == plot_filter]
    if decision_filter == "Awaiting review":
        journal = journal[journal["Human decision"] == "Awaiting Review"]
    elif decision_filter == "Recorded":
        journal = journal[journal["Human decision"] != "Awaiting Review"]
    with st.container(border=True):
        st.dataframe(
            journal, hide_index=True, width="stretch",
            alt="Decision journal with recommendations, confidence, human responses, and reasons",
            column_config={
                "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="percent"),
                "Evidence": st.column_config.TextColumn("Evidence", width="large"),
                "Reason": st.column_config.TextColumn("Reason", width="medium"),
            },
        )


if not st.session_state.started:
    show_home()
    st.stop()

if not st.user.get("is_logged_in", False):
    show_authentication()
    st.stop()

show_sidebar()
show_plot_picker()
st.space("small")
if st.session_state.workspace_view == "Plot monitor":
    show_plot_monitor(st.session_state.selected_plot)
else:
    show_journal()
