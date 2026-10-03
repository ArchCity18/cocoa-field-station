"""Interactive field-station interface for the simulated cocoa decision demo."""
import json

import pandas as pd
import streamlit as st

import db
from agent import create_and_log_recommendation
from data.seed import PLOTS, generate_seed_data


st.set_page_config(
    page_title="Cocoa Field Station",
    page_icon=":material/eco:",
    layout="wide",
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


def show_home():
    st.badge("SIMULATED FIELD DATA", icon=":material/science:", color="orange")
    st.title("A calmer way to decide what a plot needs", icon=":material/eco:")
    st.write(
        "Cocoa Field Station turns a week of weather observations into a clear, "
        "reviewable suggestion: **spray, wait, or inspect**. The grower stays in charge."
    )
    left, right = st.columns([1.2, 0.8], vertical_alignment="center")
    with left:
        st.subheader("See the signal. Make the call.")
        st.write(
            "Explore three simulated plots, compare their weather, and see why the "
            "assistant suggests a next step. Approvals and overrides become part of "
            "the decision journal, so the demo can show feedback in action."
        )
        preview_plot = st.selectbox("Take a quick look at a plot", list(PLOTS), key="home_plot")
        preview_data = pd.DataFrame(db.weather_for_plot(preview_plot, limit=7))
        if not preview_data.empty:
            a, b = st.columns(2)
            a.metric("Rain in latest observations", f"{preview_data['rainfall_mm'].sum():.1f} mm")
            b.metric("Average humidity", f"{preview_data['humidity_pct'].mean():.0f}%")
        if st.button("Get started", type="primary", icon=":material/arrow_forward:"):
            st.session_state.started = True
            st.session_state.selected_plot = preview_plot
            st.rerun()
    with right:
        with st.container(border=True):
            st.subheader("Your field station")
            st.markdown(
                "**01 · Observe**  Recent plot weather\n\n"
                "**02 · Review**  Evidence and confidence\n\n"
                "**03 · Decide**  Approve or record an override\n\n"
                "**04 · Learn**  Revisit decisions in the journal"
            )
            st.caption("A decision aid with a human at every step.")
    st.warning(
        "Prototype only: all weather is simulated, thresholds are unverified "
        "placeholders, and suggestions are not real farm advice.",
        icon=":material/info:",
    )


def show_authentication():
    st.badge("SECURE SIGN-IN", icon=":material/verified_user:", color="green")
    st.title("Welcome to your field station")
    st.write("Sign in to continue, or create an account through the identity provider.")
    sign_in_or_up = st.segmented_control(
        "Choose an account option",
        ["Sign in", "Create account"],
        default="Sign in",
        key="auth_mode",
    )
    auth_config = st.secrets.get("auth", {})
    google_config = auth_config.get("google") if hasattr(auth_config, "get") else None

    left, right = st.columns([1, 1])
    with left:
        with st.container(border=True):
            st.subheader("Continue with Google", icon=":material/account_circle:")
            if sign_in_or_up == "Create account":
                st.write(
                    "Continue to Google to sign in. If you need a Google account, you "
                    "can create one in Google's sign-in flow; this app recognizes your "
                    "verified identity when you return."
                )
            else:
                st.write("Your password stays with Google; this app never asks for it.")
            if google_config:
                if st.button("Continue with Google", type="primary", icon=":material/login:"):
                    st.login("google")
            else:
                st.info(
                    "Google sign-in is not configured yet. Add your OAuth app details "
                    "to `.streamlit/secrets.toml`; setup steps are in the README.",
                    icon=":material/settings:",
                )
    with right:
        with st.container(border=True):
            st.subheader("Private by design", icon=":material/lock:")
            st.write(
                "Authentication is handled by OpenID Connect. The app receives your "
                "verified name and email, and does not store a password."
            )
            st.caption("For this prototype, plot and decision data remains shared in its local SQLite database.")

    if st.button("Back to welcome page", icon=":material/arrow_back:"):
        st.session_state.started = False
        st.rerun()


if not st.session_state.started:
    show_home()
    st.stop()

if not st.user.is_logged_in:
    show_authentication()
    st.stop()

with st.sidebar:
    st.title("Cocoa Field Station", anchor=False)
    st.caption("A human-reviewed plot assistant")
    st.caption(f"Signed in as {st.user.name or st.user.email}")
    if st.button("Sign out", icon=":material/logout:"):
        st.logout()
    if st.button("Welcome page", icon=":material/home:"):
        st.session_state.started = False
        st.rerun()
    st.warning("SIMULATED DATA · NOT FARM ADVICE", icon=":material/science:")

st.badge("SIMULATED DATA", icon=":material/science:", color="orange")
st.title("Field overview", icon=":material/eco:")
st.caption("Choose a plot, explore its recent conditions, then review a suggestion.")

plot_cols = st.columns(3)
for col, (plot, description) in zip(plot_cols, PLOTS.items()):
    observations = db.weather_for_plot(plot, limit=7)
    humidity = sum(r["humidity_pct"] for r in observations) / max(len(observations), 1)
    rain = sum(r["rainfall_mm"] for r in observations)
    with col.container(border=True, height="stretch"):
        st.markdown(f"#### {plot}")
        st.caption(description)
        st.metric("7-observation rainfall", f"{rain:.1f} mm", chart_data=[r["rainfall_mm"] for r in observations])
        st.metric("Mean humidity", f"{humidity:.0f}%")
        if st.button(
            "Viewing this plot" if st.session_state.selected_plot == plot else "Open plot",
            key=f"select-{plot}",
            type="primary" if st.session_state.selected_plot == plot else "secondary",
            icon=":material/arrow_forward:",
        ):
            st.session_state.selected_plot = plot
            st.session_state.current_recommendation = None
            st.rerun()

plot_id = st.session_state.selected_plot
view = st.selectbox("Station view", ["Plot monitor", "Decision journal"], key="workspace_view", label_visibility="collapsed")

if view == "Plot monitor":
    st.header(f"{plot_id} · Plot monitor")
    st.caption(PLOTS[plot_id])
    all_observations = db.weather_for_plot(plot_id)
    chart_data = pd.DataFrame(all_observations)
    if not chart_data.empty:
        chart_data["date"] = pd.to_datetime(chart_data["date"])
        controls = st.columns([1, 1.2, 2])
        with controls[0]:
            days_to_show = st.selectbox("Weather window", [7, 14, 30], format_func=lambda d: f"Last {d} days")
        with controls[1]:
            measure = st.selectbox(
                "Explore", ["Rainfall", "Humidity", "Temperature"],
                format_func=lambda value: f"Explore: {value.lower()}",
            )
        metric_columns = {
            "Rainfall": ("rainfall_mm", "Rainfall (mm)", "Daily rainfall across the selected window"),
            "Humidity": ("humidity_pct", "Humidity (%)", "Daily humidity across the selected window"),
            "Temperature": ("temp_c", "Temperature (°C)", "Daily temperature across the selected window"),
        }
        value_col, label, alt = metric_columns[measure]
        window = chart_data.tail(days_to_show)
        st.line_chart(window, x="date", y=value_col, y_label=label, alt=alt)
        with st.expander("Open observation journal", icon=":material/notes:"):
            display = window[["date", "rainfall_mm", "humidity_pct", "temp_c", "days_since_last_spray", "inspection_note"]].copy()
            display.columns = ["Date", "Rain (mm)", "Humidity (%)", "Temperature (°C)", "Days since spray", "Inspection note"]
            st.dataframe(display, hide_index=True, alt="Weather observations and inspection notes for this plot")

    result = st.session_state.current_recommendation
    if result and result.get("plot_id") != plot_id:
        result = None
    if result:
        saved = db.get_decision(result["id"])
        result["pending"] = bool(saved and saved["human_decision"] is None)

    if not result:
        st.subheader("Ready when you are")
        st.write("Create a fresh suggestion from this plot’s latest observations.")
        if st.button("Read this plot", type="primary", icon=":material/psychology:"):
            with st.spinner("Reviewing recent conditions…"):
                st.session_state.current_recommendation = create_and_log_recommendation(plot_id)
            st.rerun()
    else:
        action = result["action"]
        with st.container(border=True):
            st.badge("Needs your review" if result["pending"] else "Decision recorded",
                     icon=":material/pending:" if result["pending"] else ":material/check_circle:",
                     color="orange" if result["pending"] else "green")
            st.subheader(f"{ACTION_ICONS.get(action, '')} Suggested next step: {action}")
            st.write(result["rationale"])
            metric_a, metric_b, metric_c = st.columns(3)
            metric_a.metric("Confidence", f"{result['confidence']:.0%}")
            metric_b.metric("Risk bucket", result["risk_bucket"].title())
            metric_c.metric("Confidence gate", "Inspection required" if result["gated"] else "Passed")
            with st.expander("Why this suggestion?", expanded=True, icon=":material/lightbulb:"):
                for evidence in result["evidence"]:
                    st.markdown(f"- {evidence}")
                citations = result["cited_case_ids"]
                if citations:
                    st.caption("Past override cases considered: " + ", ".join(f"#{case_id}" for case_id in citations))
                else:
                    st.caption("No similar past override cases were cited.")

            if result["pending"]:
                st.markdown("**Your call**")
                actions = [choice for choice in ("spray", "wait", "inspect") if choice != action]
                with st.form(f"human-review-{result['id']}"):
                    choice = st.selectbox("Override action (optional)", ["Keep suggestion", *actions])
                    reason = st.text_input("Reason for override", placeholder="Required only when overriding")
                    submitted = st.form_submit_button("Record my decision", type="primary", icon=":material/how_to_reg:")
                if submitted:
                    if choice == "Keep suggestion":
                        db.record_human_decision(result["id"], action)
                        st.toast("Approval recorded in the decision journal.", icon=":material/check_circle:")
                        st.rerun()
                    elif not reason.strip():
                        st.error("Add a short reason so the override is useful in the journal.")
                    else:
                        db.record_human_decision(result["id"], choice, reason.strip())
                        st.toast("Override and reason recorded.", icon=":material/history:")
                        st.rerun()
            else:
                decision_text = f"Recorded decision: **{result.get('human_decision') or action}**"
                if result.get("human_reason"):
                    decision_text += f" · {result['human_reason']}"
                st.success(decision_text)
        if st.button("Read plot again", icon=":material/refresh:"):
            with st.spinner("Reviewing recent conditions…"):
                st.session_state.current_recommendation = create_and_log_recommendation(plot_id)
            st.rerun()

else:
    st.header("Decision journal", icon=":material/history:")
    st.caption("Every suggestion and human decision, together in one place.")
    rows = db.audit_log()
    if rows:
        records = []
        for row in rows:
            record = {
                "#": row["id"], "Plot": row["plot_id"], "Time": row["ts"],
                "Risk": row["risk_bucket"].title(), "Suggestion": row["recommendation"].title(),
                "Confidence": row["confidence"], "Gate": "Inspect" if row["gated"] else "Clear",
                "Human decision": (row["human_decision"] or "Awaiting review").title(),
                "Reason": row["human_reason"] or "—",
                "Evidence": "; ".join(json.loads(row["evidence_json"])),
            }
            records.append(record)
        journal = pd.DataFrame(records)
        filters = st.columns(2)
        with filters[0]:
            plot_filter = st.selectbox("Filter by plot", ["All plots", *PLOTS.keys()])
        with filters[1]:
            decision_filter = st.selectbox("Filter by status", ["All decisions", "Awaiting review", "Recorded"])
        if plot_filter != "All plots":
            journal = journal[journal["Plot"] == plot_filter]
        if decision_filter == "Awaiting review":
            journal = journal[journal["Human decision"] == "Awaiting review"]
        elif decision_filter == "Recorded":
            journal = journal[journal["Human decision"] != "Awaiting review"]
        st.dataframe(
            journal,
            hide_index=True,
            alt="Decision journal with recommendations, confidence, human responses, and reasons",
            column_config={"Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="percent")},
        )
    else:
        st.info("Your decision journal is empty. Visit a plot and ask for its first reading.", icon=":material/auto_stories:")
