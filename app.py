"""Interactive field-station interface for the simulated cocoa decision demo."""
import json
from pathlib import Path
import time

import pandas as pd
import streamlit as st

import db
import totp
from agent import create_and_log_recommendation
from data.seed import PLOTS, generate_seed_data


ROOT = Path(__file__).parent
LOGO = ROOT / "assets" / "cocoa-field-station-logo.svg"
HERO = ROOT / "assets" / "cacao-grove-hero.svg"

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


def show_home():
    """Welcome growers with cocoa-specific language and a distinct visual identity."""
    st.badge("A COCOA GROWER'S FIELD DESK", icon=":material/eco:", color="green")
    hero_left, hero_right = st.columns([1.05, 0.95], vertical_alignment="center", gap="large")
    with hero_left:
        st.title("Know your cocoa fields. Tend them with confidence.")
        st.write(
            "A thoughtful view of changing conditions across your cocoa plots, "
            "with practical next steps you can review before you act."
        )
        preview_plot = st.selectbox("Start with a plot", list(PLOTS), key="home_plot")
        preview = pd.DataFrame(db.weather_for_plot(preview_plot, limit=7))
        if not preview.empty:
            metrics = st.columns(3)
            metrics[0].metric("Rain this week", f"{preview['rainfall_mm'].sum():.1f} mm", border=True)
            metrics[1].metric("Average humidity", f"{preview['humidity_pct'].mean():.0f}%", border=True)
            metrics[2].metric("Field notes", f"{len(preview)} days", border=True)
        if st.button("Explore the field station", type="primary", icon=":material/arrow_forward:"):
            st.session_state.started = True
            st.session_state.selected_plot = preview_plot
            st.rerun()
    with hero_right:
        st.image(str(HERO), width="stretch", caption="An illustrated view of a cocoa-growing landscape")
    st.space("medium")
    st.subheader("A field routine built around your judgement")
    steps = st.columns(3)
    for col, icon, heading, detail in zip(
        steps,
        (":material/water_drop:", ":material/visibility:", ":material/how_to_reg:"),
        ("Read the conditions", "See why it matters", "Make the call"),
        (
            "Bring recent rainfall, humidity, and temperature into view.",
            "Review the evidence and confidence behind each suggestion.",
            "Approve the suggestion or record your own decision and reason.",
        ),
    ):
        with col.container(border=True):
            st.markdown(icon)
            st.markdown(f"**{heading}**")
            st.caption(detail)
    st.caption("DEMO NOTE · All weather is simulated. Agronomy thresholds are unverified placeholders, not farm advice.")


def show_authentication():
    """Render the configured identity-provider entry point."""
    st.badge("SECURE SIGN-IN", icon=":material/verified_user:", color="green")
    st.title("Welcome to your field station")
    st.write("Sign in with Google, then confirm your identity with your authenticator app.")
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
                st.write("Your password stays with Google. This app never asks for it.")
            if google_config:
                if st.button("Continue with Google", type="primary", icon=":material/login:"):
                    st.login("google")
            else:
                st.info(
                    "Google sign-in is not configured yet. Add OAuth details to `.streamlit/secrets.toml`; setup steps are in the README.",
                    icon=":material/settings:",
                )
            st.caption("The first sign-in asks you to connect Google Authenticator. Future sign-ins require a current six-digit code.")
    with right:
        with st.container(border=True):
            st.subheader("Private by design", icon=":material/lock:")
            st.write("Authentication uses OpenID Connect. The app receives your verified name and email, and does not store a password.")
            st.caption("Plot and decision data remains shared in this prototype's local SQLite database.")

    if st.button("Back to welcome page", icon=":material/arrow_back:"):
        st.session_state.started = False
        st.rerun()


def clear_mfa_state():
    for key in ("mfa_subject", "mfa_verified_sub", "mfa_pending_secret", "mfa_pending_sub", "mfa_started_at", "mfa_attempts", "auth_role"):
        st.session_state.pop(key, None)


def require_authenticator():
    """Gate protected Streamlit pages behind an enrolled TOTP factor."""
    identity = st.user
    sub = str(identity.get("sub", "")).strip()
    email = str(identity.get("email", "")).strip().lower()
    name = str(identity.get("name", "")).strip() or email
    if not sub or not email:
        st.error("Google did not provide a verified account identity. Sign out and try again.")
        if st.button("Sign out", key="mfa_identity_signout"):
            clear_mfa_state()
            st.logout()
        return False

    if st.session_state.get("mfa_subject") != sub:
        clear_mfa_state()
        st.session_state.mfa_subject = sub
        st.session_state.mfa_started_at = time.time()
        st.session_state.mfa_attempts = 0

    if st.session_state.get("mfa_verified_sub") == sub:
        return True

    auth_config = st.secrets.get("auth", {})
    cookie_secret = str(auth_config.get("cookie_secret", ""))
    if len(cookie_secret) < 32:
        st.error("Authenticator storage is not configured. Add a long random cookie_secret under [auth] in Streamlit Secrets.")
        return False

    admin_emails = st.secrets.get("ADMIN_EMAILS", [])
    is_admin = email in {str(item).strip().lower() for item in admin_emails}
    account = db.get_or_create_auth_account(sub, email, name, is_admin=is_admin)
    st.session_state.auth_role = account["role"]

    now = time.time()
    if now - st.session_state.mfa_started_at > 600:
        st.error("This authenticator challenge expired. Sign out and start again.")
        if st.button("Restart sign-in", key="mfa_expired_signout"):
            clear_mfa_state()
            st.logout()
        return False
    if st.session_state.mfa_attempts >= 5:
        st.error("Too many incorrect authenticator codes. Sign out and start again.")
        if st.button("Restart sign-in", key="mfa_locked_signout"):
            clear_mfa_state()
            st.logout()
        return False

    enrolled = bool(account.get("totp_secret_enc"))
    if enrolled:
        try:
            secret = totp.decrypt_secret(account["totp_secret_enc"], cookie_secret)
        except Exception:
            st.error("The saved authenticator key cannot be opened. Check that your Streamlit cookie_secret has not changed.")
            return False
        st.badge("SECOND STEP", icon=":material/verified_user:", color="green")
        st.title("Check your authenticator")
        st.write("Enter the current six-digit code from Google Authenticator.")
    else:
        pending_sub = st.session_state.get("mfa_pending_sub")
        if pending_sub != sub or not st.session_state.get("mfa_pending_secret"):
            st.session_state.mfa_pending_sub = sub
            st.session_state.mfa_pending_secret = totp.new_secret()
        secret = st.session_state.mfa_pending_secret
        uri = totp.provisioning_uri(secret, email)
        st.badge("SET UP TWO-STEP VERIFICATION", icon=":material/verified_user:", color="green")
        st.title("Connect Google Authenticator")
        st.write("Scan this QR code in Google Authenticator, then enter the code it creates to finish setup.")
        qr_col, key_col = st.columns([1, 1], vertical_alignment="center")
        with qr_col:
            st.image(totp.qr_image(uri), caption="Scan with Google Authenticator")
        with key_col:
            st.markdown("**Manual setup key**")
            st.code(secret, language=None)
            st.caption("Keep this key private. It can generate sign-in codes for your account.")

    with st.form("authenticator-code-form"):
        code = st.text_input("Six-digit code", max_chars=6, placeholder="000000", autocomplete="one-time-code")
        submitted = st.form_submit_button("Verify and continue", type="primary", icon=":material/lock_open:", width="stretch")
    if submitted:
        if totp.verify_code(secret, code):
            if not enrolled:
                db.set_totp_secret(sub, totp.encrypt_secret(secret, cookie_secret))
            st.session_state.mfa_verified_sub = sub
            st.session_state.pop("mfa_pending_secret", None)
            st.session_state.pop("mfa_pending_sub", None)
            st.session_state.mfa_attempts = 0
            st.rerun()
        st.session_state.mfa_attempts += 1
        st.error(f"That code is incorrect. Attempts remaining: {5 - st.session_state.mfa_attempts}.")
    st.caption(f"Signed in with Google as {email}. The code challenge expires after ten minutes.")
    if st.button("Sign out", key="mfa_signout", icon=":material/logout:"):
        clear_mfa_state()
        st.logout()
    return False


def show_sidebar():
    with st.sidebar:
        if LOGO.exists():
            st.logo(str(LOGO), size="large")
        st.caption("COCOA FIELD STATION")
        st.markdown("### Your workspace")
        role = st.session_state.get("auth_role", "user")
        views = ["Plot monitor", "Decision journal"] + (["Account directory"] if role == "admin" else [])
        if st.session_state.get("workspace_view") not in views:
            st.session_state.workspace_view = views[0]
        st.radio(
            "Workspace", views,
            key="workspace_view", label_visibility="collapsed",
            horizontal=False,
        )
        st.space("small")
        st.caption("ACCOUNT")
        name = st.user.get("name") or st.user.get("email") or "Signed in"
        st.caption(name)
        st.caption(f"ROLE · {st.session_state.get('auth_role', 'user').upper()}")
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            clear_mfa_state()
            st.logout()
        st.caption("SIMULATED DATA · NOT FARM ADVICE")


def show_account_directory():
    if st.session_state.get("auth_role") != "admin":
        st.error("Admin role required.")
        st.stop()
    st.caption("ADMINISTRATION  /  ACCOUNTS")
    st.title("Account directory", icon=":material/manage_accounts:")
    st.write("Google identities registered in this Streamlit app, with authenticator enrollment status.")
    records = pd.DataFrame(db.auth_accounts())
    if records.empty:
        st.info("No accounts have completed sign-in yet.")
    else:
        records = records.rename(columns={"email": "Email", "name": "Name", "role": "Role", "created_at": "Created", "authenticator": "Authenticator"})
        st.dataframe(records, hide_index=True, width="stretch")


def show_plot_picker():
    st.caption("FIELD JOURNAL  /  SELECT A PLOT")
    selected_plot = st.pills(
        "Choose a plot",
        options=list(PLOTS),
        selection_mode="single",
        key="selected_plot",
        label_visibility="collapsed",
        width="stretch",
    )
    selected_plot = selected_plot or list(PLOTS)[0]
    st.caption(PLOTS[selected_plot])


def show_plot_monitor(plot_id):
    observations = db.weather_for_plot(plot_id)
    frame = pd.DataFrame(observations)
    st.caption(f"FIELD NOTES  /  {plot_id.upper()}")
    top_left, top_right = st.columns([1.4, 0.6], vertical_alignment="center")
    with top_left:
        st.title(f"{plot_id} at a glance", icon=":material/eco:")
        st.write(PLOTS[plot_id])
    with top_right:
        st.badge("SIMULATED FIELD DATA", icon=":material/science:", color="orange")

    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
        recent = frame.tail(7)
        summary = st.columns(4)
        summary[0].metric("Rainfall · 7 days", f"{recent['rainfall_mm'].sum():.1f} mm", border=True)
        summary[1].metric("Average humidity", f"{recent['humidity_pct'].mean():.0f}%", border=True)
        summary[2].metric("Average temperature", f"{recent['temp_c'].mean():.1f} °C", border=True)
        summary[3].metric("Most recent reading", frame["date"].iloc[-1].strftime("%d %b"), border=True)

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
    pending_count = sum(row["human_decision"] is None for row in rows)
    recorded_count = len(rows) - pending_count
    journal_metrics = st.columns(3)
    journal_metrics[0].metric("Field readings", len(rows), border=True)
    journal_metrics[1].metric("Awaiting review", pending_count, border=True)
    journal_metrics[2].metric("Grower decisions", recorded_count, border=True)
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
    clear_mfa_state()
    show_authentication()
    st.stop()

if not require_authenticator():
    st.stop()

show_sidebar()
st.space("small")
if st.session_state.workspace_view == "Plot monitor":
    show_plot_picker()
    show_plot_monitor(st.session_state.selected_plot)
elif st.session_state.workspace_view == "Decision journal":
    show_journal()
else:
    show_account_directory()
