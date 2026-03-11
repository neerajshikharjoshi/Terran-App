import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
import pandas as pd
import hashlib

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="The Terran | Content Ops", layout="wide")

# --- 2. GLOBAL CONSTANTS ---
IST = ZoneInfo("Asia/Kolkata")
ROLES = ["Operator", "SME", "Manager", "Allocator"]
ADMIN_USERNAME = "Admin"
SYSTEM_ASSIGNER = "System"

MR_LIST = ["BBFC:U::", "BBFC:PG::", "BBFC:12::", "BBFC:15::", "BBFC:18::"]
OFFICIAL_RATING_LIST = ["Not Officially Rated", "BBFC:U::", "BBFC:PG::", "BBFC:12::", "BBFC:15::", "BBFC:18::"]
OP_STATUS_OPTIONS = ["In Progress", "Reviewed by Operator", "Pending Calibration", "Title Issue"]

DAY_START_QUEUE_TARGET = 7
AHT_MINUTES = 480 / 7
LEAVE_TYPES = ["Sick", "Annual", "Casual", "Menstrual", "Emergency", "Unpaid", "Other"]

CD_CA_MAPPING = {
    "NO ISSUES": ["no material likely to offend or harm"],
    "VIOLENCE": ["VIOLENCE", "REFERENCES TO VIOLENCE", "BULLYING", "DOMESTIC ABUSE", "DOMESTIC ABUSE REFERENCES"],
    "INJURY DETAIL": ["INJURY DETAIL", "IMAGES OF REAL DEAD BODIES"],
    "THREAT": ["THREAT", "HORROR"],
    "SEXUAL VIOLENCE & SEXUAL THREAT": [
        "SEXUAL VIOLENCE",
        "SEXUAL VIOLENCE REFERENCES",
        "SEXUAL THREAT",
        "ABUSIVE BEHAVIOUR",
        "SEXUAL VIOLENCE THEME",
        "CHILD ABUSE",
        "CHILD ABUSE REFERENCES",
    ],
    "DANGEROUS BEHAVIOUR": ["DANGEROUS BEHAVIOUR"],
    "SUICIDE & SELF-HARM": [
        "SUICIDE",
        "SUICIDE REFERENCES",
        "SUICIDE THEME",
        "SELF-HARM",
        "SELF-HARM THEME",
        "REFERENCES TO MENTAL HEALTH",
    ],
    "SEX & NUDITY": ["SEX", "SEX REFERENCES", "NUDITY", "SEXUAL IMAGES", "C/RUDE HUMOUR"],
    "LANGUAGE": ["LANGUAGE", "RUDE GESTURES", "RACIAL LANGUAGE"],
    "DRUGS": ["DRUG MISUSE", "DRUG REFERENCES", "SMOKING", "ALCOHOL", "SUBSTANCE ABUSE"],
    "DISCRIMINATION": ["DISCRIMINATION", "DISCRIMINATION REFERENCES", "DISCRIMINATORY STEREOTYPES"],
    "ANIMALS HUNTING": ["ANIMALS HUNTING"],
    "TONE & IMPACT (THEMES)": ["UPSETTING SCENES", "DISTRESSING SCENES", "DISTURBING SCENES"],
}

UNIFIED_CA_LIST = [f"{cd}: {ca}" for cd, cas in CD_CA_MAPPING.items() for ca in cas]
ALL_CAS = list(dict.fromkeys([ca for cas in CD_CA_MAPPING.values() for ca in cas]))

# --- 3. CSS / STYLING ---
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 0.8rem;
        padding-bottom: 1.2rem;
        max-width: 97%;
    }

    section[data-testid="stSidebar"] {
        min-width: 215px !important;
        max-width: 215px !important;
        background: #f3f4f6;
        border-right: 1px solid #e5e7eb;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dfe4ea;
        padding: 10px 12px;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    div[data-testid="stMetricLabel"] {
        color: #6b7280;
        font-size: 0.83rem;
    }

    div[data-testid="stMetricValue"] {
        color: #111827;
        font-weight: 800;
        font-size: 1.6rem;
    }

    .terran-header {
        background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 100%);
        border: 1px solid #dbe3f0;
        border-radius: 16px;
        padding: 14px 16px;
        margin-bottom: 0.8rem;
    }

    .terran-title {
        font-size: 1.55rem;
        font-weight: 800;
        color: #111827;
        line-height: 1.2;
    }

    .terran-subtitle {
        color: #6b7280;
        font-size: 0.95rem;
        margin-top: 0.15rem;
    }

    .terran-chip {
        display: inline-block;
        padding: 0.32rem 0.65rem;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 600;
        border: 1px solid #d1d5db;
        background: #ffffff;
        color: #374151;
        margin-left: 0.35rem;
    }

    .terran-strip {
        background: #ffffff;
        border: 1px solid #dfe4ea;
        border-radius: 14px;
        padding: 10px 12px;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    .terran-panel {
        background: #ffffff;
        border: 1px solid #dfe4ea;
        border-radius: 14px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        height: 100%;
    }

    .terran-panel-title {
        font-size: 1rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.18rem;
    }

    .terran-panel-sub {
        color: #6b7280;
        font-size: 0.82rem;
        margin-bottom: 0.65rem;
    }

    .terran-queue {
        background: #ffffff;
        border: 1px solid #dfe4ea;
        border-radius: 14px;
        padding: 12px;
        margin-top: 0.8rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    .terran-section-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.5rem;
    }

    .terran-soft-card {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 0.7rem;
    }

    .terran-soft-title {
        font-size: 0.98rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.35rem;
    }

    .terran-mini-chip {
        display: inline-block;
        padding: 0.28rem 0.58rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        border: 1px solid #d1d5db;
        background: #ffffff;
        color: #374151;
        margin-right: 0.35rem;
        margin-top: 0.18rem;
    }

    .stButton > button, [data-testid="stDownloadButton"] > button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 40px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #f3f4f6;
        border-radius: 10px 10px 0 0;
        padding: 8px 12px;
        border: 1px solid #dfe4ea;
    }

    .stTabs [aria-selected="true"] {
        background: #dbeafe !important;
        color: #1d4ed8 !important;
        font-weight: 700 !important;
    }

    .stExpander {
        border: 1px solid #dfe4ea !important;
        border-radius: 10px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 4. BASIC HELPERS ---
def hash_pw(pw):
    return hashlib.sha256(str.encode(pw)).hexdigest()


def get_idx(val, opt_list):
    try:
        return opt_list.index(val)
    except Exception:
        return 0


def now_utc():
    return datetime.now(timezone.utc)


def now_ist():
    return datetime.now(IST)


def today_ist_date():
    return now_ist().date()


def current_date_str_ist():
    return today_ist_date().isoformat()


def current_week_num_ist():
    return now_ist().isocalendar()[1]


def display_date_ist():
    return f"📅 {current_date_str_ist()} | Week {current_week_num_ist()} | IST"


def display_time_ist():
    return f"🕒 {now_ist().strftime('%H:%M:%S')} IST"


def parse_date_str(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def date_to_str(d: date) -> str:
    return d.isoformat()


def yesterday_str_ist():
    return date_to_str(today_ist_date() - timedelta(days=1))


def day_bounds_utc_for_date(date_str: str):
    d = parse_date_str(date_str)
    start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=IST)
    next_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc).isoformat(), next_local.astimezone(timezone.utc).isoformat()


def current_month_bounds_utc():
    local_now = now_ist()
    month_start_local = datetime(local_now.year, local_now.month, 1, 0, 0, 0, tzinfo=IST)
    if local_now.month == 12:
        next_month_local = datetime(local_now.year + 1, 1, 1, 0, 0, 0, tzinfo=IST)
    else:
        next_month_local = datetime(local_now.year, local_now.month + 1, 1, 0, 0, 0, tzinfo=IST)
    return month_start_local.astimezone(timezone.utc).isoformat(), next_month_local.astimezone(timezone.utc).isoformat()


def append_date_week(df):
    if not df.empty:
        df["export_date"] = current_date_str_ist()
        df["week_number"] = current_week_num_ist()
    return df


def safe_csv_from_records(records):
    if not records:
        return pd.DataFrame().to_csv(index=False).encode("utf-8")
    return pd.DataFrame(records).to_csv(index=False).encode("utf-8")


# --- 5. SUPABASE CONNECTION ---
url = st.secrets.get("SUPABASE_URL")
key = st.secrets.get("SUPABASE_KEY")

if not url or not key:
    st.error("Supabase secrets are missing. Check .streamlit/secrets.toml")
    st.stop()

try:
    supabase: Client = create_client(url, key)
    _healthcheck = supabase.table("app_users").select("username").limit(1).execute()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()


# --- 6. SESSION HELPERS ---
if "user" not in st.session_state:
    st.session_state.user = None


def set_logged_in_user(user_row):
    st.session_state.user = user_row
    st.query_params["session_token"] = user_row["username"]


def clear_logged_in_user():
    st.session_state.user = None
    if "session_token" in st.query_params:
        del st.query_params["session_token"]


def restore_session_from_query_params():
    if st.session_state.user is None and "session_token" in st.query_params:
        token_user = st.query_params["session_token"]
        try:
            res = supabase.table("app_users").select("*").eq("username", token_user).execute()
            if res.data and res.data[0].get("is_approved"):
                st.session_state.user = res.data[0]
        except Exception:
            pass


restore_session_from_query_params()


# --- 7. GENERIC DATA HELPERS ---
def get_workday_for_date(username, work_date_str):
    try:
        res = (
            supabase.table("work_days")
            .select("*")
            .eq("username", username)
            .eq("work_date", work_date_str)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_today_workday(username):
    return get_workday_for_date(username, current_date_str_ist())


def get_productivity_log_for_date(username, work_date_str):
    try:
        res = (
            supabase.table("productivity_logs")
            .select("*")
            .eq("username", username)
            .eq("work_date", work_date_str)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_today_productivity_log(username):
    return get_productivity_log_for_date(username, current_date_str_ist())


def get_snapshot_for_date(username, work_date_str):
    try:
        res = (
            supabase.table("daily_work_snapshots")
            .select("*")
            .eq("username", username)
            .eq("work_date", work_date_str)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_today_snapshot(username):
    return get_snapshot_for_date(username, current_date_str_ist())


def get_leave_for_date(username, work_date_str):
    try:
        res = (
            supabase.table("leave_logs")
            .select("*")
            .eq("username", username)
            .eq("leave_date", work_date_str)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_operator_active_tasks(username):
    try:
        return supabase.table("titles").select("*").eq("assigned_to", username).execute().data or []
    except Exception:
        return []


def get_operator_task_summary(tasks):
    counts = {}
    if tasks:
        df = pd.DataFrame(tasks)
        if "status" in df.columns:
            counts = df["status"].value_counts().to_dict()
    return {
        "total": len(tasks),
        "in_progress": counts.get("In Progress", 0),
        "reviewed": counts.get("Reviewed by Operator", 0),
        "pending_calibration": counts.get("Pending Calibration", 0),
        "finalized": counts.get("Finalized", 0),
    }


def count_carry_forward_tasks(tasks):
    return len([t for t in tasks if t.get("status") in ["In Progress", "Pending Calibration"]])


def log_title_event(gti, username, event_type, old_status=None, new_status=None, notes=None):
    try:
        supabase.table("title_event_logs").insert({
            "gti": gti,
            "username": username,
            "event_type": event_type,
            "old_status": old_status,
            "new_status": new_status,
            "notes": notes,
            "created_at": now_utc().isoformat(),
        }).execute()
    except Exception:
        pass


def log_allocation(gti, assigned_to, assigned_by, assignment_type, notes=None):
    try:
        supabase.table("allocation_logs").insert({
            "gti": gti,
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "assignment_type": assignment_type,
            "work_date": current_date_str_ist(),
            "assigned_at": now_utc().isoformat(),
            "notes": notes,
        }).execute()
    except Exception:
        pass


def bump_titles_assigned_today(username, increment_by):
    if increment_by <= 0:
        return
    try:
        workday = get_today_workday(username)
        if workday and not workday.get("ended_at"):
            current_assigned = int(workday.get("titles_assigned_today") or 0)
            supabase.table("work_days").update(
                {"titles_assigned_today": current_assigned + increment_by}
            ).eq("id", workday["id"]).execute()
    except Exception:
        pass


def allocate_unassigned_titles_to_operator(
    operator_username,
    qty,
    assigned_by,
    assignment_type,
    notes=None,
    bump_workday=True,
):
    if qty <= 0:
        return []

    try:
        unassigned = (
            supabase.table("titles")
            .select("id, gti")
            .eq("status", "Unassigned")
            .limit(qty)
            .execute()
            .data
            or []
        )

        allocated = []
        for item in unassigned:
            supabase.table("titles").update({
                "assigned_to": operator_username,
                "status": "In Progress",
                "updated_at": now_utc().isoformat(),
            }).eq("id", item["id"]).execute()

            allocated.append(item)
            log_allocation(
                gti=item.get("gti"),
                assigned_to=operator_username,
                assigned_by=assigned_by,
                assignment_type=assignment_type,
                notes=notes,
            )

        if bump_workday and allocated:
            bump_titles_assigned_today(operator_username, len(allocated))

        return allocated
    except Exception:
        return []


def save_or_update_snapshot_for_date(username, work_date_str, tasks):
    payload = {
        "username": username,
        "work_date": work_date_str,
        "snapshot_json": tasks,
        "updated_at": now_utc().isoformat(),
    }
    existing = get_snapshot_for_date(username, work_date_str)

    try:
        if existing:
            supabase.table("daily_work_snapshots").update(payload).eq("id", existing["id"]).execute()
        else:
            payload["created_at"] = now_utc().isoformat()
            supabase.table("daily_work_snapshots").insert(payload).execute()
        return True, "Snapshot saved."
    except Exception as e:
        return False, f"Failed to save snapshot: {e}"


def save_or_update_productivity_log_for_date(
    username,
    work_date_str,
    day_type,
    productive_minutes,
    non_productive_time_minutes,
    titles_completed,
    calibrations_raised,
    carry_forward_count,
    comments,
):
    existing = get_productivity_log_for_date(username, work_date_str)
    productive_hours = round(float(productive_minutes) / 60, 2)

    payload = {
        "username": username,
        "work_date": work_date_str,
        "day_type": day_type,
        "productive_minutes": int(productive_minutes),
        "productive_hours": productive_hours,
        "non_productive_time_minutes": int(non_productive_time_minutes),
        "titles_completed": int(titles_completed),
        "calibrations_raised": int(calibrations_raised),
        "carry_forward_count": int(carry_forward_count),
        "comments": comments,
        "updated_at": now_utc().isoformat(),
    }

    try:
        if existing:
            supabase.table("productivity_logs").update(payload).eq("id", existing["id"]).execute()
        else:
            payload["created_at"] = now_utc().isoformat()
            supabase.table("productivity_logs").insert(payload).execute()
        return True, "Productivity log saved."
    except Exception as e:
        return False, f"Failed to save productivity log: {e}"


def get_event_metrics_for_date(username, work_date_str):
    start_utc, end_utc = day_bounds_utc_for_date(work_date_str)
    try:
        rows = (
            supabase.table("title_event_logs")
            .select("*")
            .eq("username", username)
            .gte("created_at", start_utc)
            .lt("created_at", end_utc)
            .execute()
            .data
            or []
        )

        reviewed_today = len([
            r for r in rows
            if r.get("event_type") == "status_change" and r.get("new_status") == "Reviewed by Operator"
        ])
        calibs_today = len([
            r for r in rows
            if r.get("event_type") == "status_change" and r.get("new_status") == "Pending Calibration"
        ])
        return {
            "reviewed_today": reviewed_today,
            "calibrations_raised_today": calibs_today,
        }
    except Exception:
        return {
            "reviewed_today": 0,
            "calibrations_raised_today": 0,
        }


def get_monthly_productivity_for_operator(username):
    month_start_utc, next_month_utc = current_month_bounds_utc()
    try:
        logs = (
            supabase.table("productivity_logs")
            .select("*")
            .eq("username", username)
            .gte("created_at", month_start_utc)
            .lt("created_at", next_month_utc)
            .execute()
            .data
            or []
        )

        events = (
            supabase.table("title_event_logs")
            .select("*")
            .eq("username", username)
            .eq("event_type", "status_change")
            .eq("new_status", "Reviewed by Operator")
            .gte("created_at", month_start_utc)
            .lt("created_at", next_month_utc)
            .execute()
            .data
            or []
        )

        titles_worked = len(events)
        total_minutes = sum(int(x.get("productive_minutes") or 0) for x in logs)
        total_npt = sum(int(x.get("non_productive_time_minutes") or 0) for x in logs)
        effective_minutes = total_minutes - total_npt

        if effective_minutes <= 0:
            productivity_pct = 0.0
        else:
            productivity_pct = round(((titles_worked * AHT_MINUTES) / effective_minutes) * 100, 2)

        return {
            "titles_worked": titles_worked,
            "total_minutes": total_minutes,
            "total_npt": total_npt,
            "effective_minutes": effective_minutes,
            "productivity_pct": productivity_pct,
            "days_logged": len(logs),
        }
    except Exception:
        return {
            "titles_worked": 0,
            "total_minutes": 0,
            "total_npt": 0,
            "effective_minutes": 0,
            "productivity_pct": 0.0,
            "days_logged": 0,
        }


def get_current_month_productivity_table():
    users = supabase.table("app_users").select("username, role").execute().data or []
    operators = [u["username"] for u in users if u.get("role") == "Operator"]

    rows = []
    for op in operators:
        metrics = get_monthly_productivity_for_operator(op)
        rows.append({
            "Operator": op,
            "Titles Worked (Month)": metrics["titles_worked"],
            "Total Minutes (Month)": metrics["total_minutes"],
            "NPT (Month)": metrics["total_npt"],
            "Effective Minutes": metrics["effective_minutes"],
            "AHT": round(AHT_MINUTES, 2),
            "Productivity %": metrics["productivity_pct"],
            "Days Logged": metrics["days_logged"],
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_monthly_completed_work_records(username):
    month_start_utc, next_month_utc = current_month_bounds_utc()
    try:
        rows = (
            supabase.table("title_event_logs")
            .select("*")
            .eq("username", username)
            .eq("event_type", "status_change")
            .eq("new_status", "Reviewed by Operator")
            .gte("created_at", month_start_utc)
            .lt("created_at", next_month_utc)
            .execute()
            .data
            or []
        )
        return rows
    except Exception:
        return []


def get_todays_work_download_records(username):
    snapshot = get_today_snapshot(username)
    if snapshot and snapshot.get("snapshot_json"):
        return snapshot.get("snapshot_json") or []
    return get_operator_active_tasks(username)


def validate_titles_before_day_close(tasks):
    errors = []

    for t in tasks:
        gti = t.get("gti", "Unknown GTI")
        status = t.get("status")
        missing = []

        if not status or status == "Unassigned":
            errors.append(f"{gti}: missing valid status")
            continue

        if status in ["Reviewed by Operator", "Pending Calibration", "Finalized"]:
            if not t.get("title_name"):
                missing.append("Title Name")
            if not t.get("runtime"):
                missing.append("Runtime")
            if not t.get("mr_rating"):
                missing.append("MR Rating")
            if not t.get("cd_values"):
                missing.append("Content Advice")
            if not t.get("primary_drivers"):
                missing.append("Primary Drivers")

        if status == "Pending Calibration":
            if not t.get("calib_cd"):
                missing.append("Calibration CA")
            if not t.get("calib_mr"):
                missing.append("Proposed MR")

        if missing:
            errors.append(f"{gti}: missing {', '.join(missing)}")

    return errors


def close_completed_titles_for_operator(username):
    tasks = get_operator_active_tasks(username)
    removable_statuses = ["Reviewed by Operator", "Finalized"]
    removed_count = 0

    for t in tasks:
        if t.get("status") in removable_statuses:
            supabase.table("titles").update({
                "assigned_to": None,
                "updated_at": now_utc().isoformat(),
            }).eq("id", t["id"]).execute()
            removed_count += 1

    return removed_count


def get_all_workdays(username):
    try:
        return supabase.table("work_days").select("*").eq("username", username).execute().data or []
    except Exception:
        return []


def auto_close_overdue_workdays(username):
    workdays = get_all_workdays(username)
    auto_closed = []

    for wd in workdays:
        if wd.get("ended_at"):
            continue

        started_at = wd.get("started_at")
        if not started_at:
            continue

        start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if (now_utc() - start_dt).total_seconds() >= 12 * 3600:
            tasks_before_close = get_operator_active_tasks(username)
            save_or_update_snapshot_for_date(username, wd["work_date"], tasks_before_close)
            removed_count = close_completed_titles_for_operator(username)
            carry_forward_tasks = get_operator_active_tasks(username)
            carry_forward_count = count_carry_forward_tasks(carry_forward_tasks)

            supabase.table("work_days").update({
                "ended_at": now_utc().isoformat(),
                "session_status": "Auto Closed",
                "carry_forward_count": carry_forward_count,
                "notes": f"Auto-closed after 12 hours. Removed {removed_count} completed titles.",
            }).eq("id", wd["id"]).execute()

            auto_closed.append(wd["work_date"])

    return auto_closed


def get_latest_missing_productivity_workday(username):
    today_str = current_date_str_ist()
    workdays = get_all_workdays(username)

    candidates = []
    for wd in workdays:
        wd_date = wd.get("work_date")
        if wd_date and wd_date < today_str and wd.get("ended_at"):
            prod = get_productivity_log_for_date(username, wd_date)
            if not prod:
                candidates.append(wd)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["work_date"], reverse=True)
    return candidates[0]


def has_work_history_before(username, date_str):
    workdays = get_all_workdays(username)
    return any((wd.get("work_date") or "") < date_str for wd in workdays)


def get_missing_leave_date(username):
    yday = yesterday_str_ist()
    has_history = has_work_history_before(username, yday)
    if not has_history:
        return None

    yday_workday = get_workday_for_date(username, yday)
    yday_leave = get_leave_for_date(username, yday)

    if not yday_workday and not yday_leave:
        return yday
    return None


def save_leave_log(username, leave_date_str, leave_type, notes):
    existing = get_leave_for_date(username, leave_date_str)
    if existing:
        return False, "Leave already logged for this date."

    try:
        supabase.table("leave_logs").insert({
            "username": username,
            "leave_date": leave_date_str,
            "leave_type": leave_type,
            "notes": notes,
            "created_at": now_utc().isoformat(),
        }).execute()
        return True, "Leave logged successfully."
    except Exception as e:
        return False, f"Failed to log leave: {e}"


def begin_my_day(username):
    existing = get_today_workday(username)
    current_tasks = get_operator_active_tasks(username)

    if existing:
        if existing.get("ended_at"):
            return False, "You have already ended your day today. Reopening is not enabled yet."
        return False, "Your day has already begun."

    carry_forward_count = count_carry_forward_tasks(current_tasks)

    payload = {
        "username": username,
        "work_date": current_date_str_ist(),
        "started_at": now_utc().isoformat(),
        "session_status": "Started",
        "titles_assigned_today": len(current_tasks),
        "titles_completed_today": 0,
        "carry_forward_count": carry_forward_count,
        "notes": None,
    }

    try:
        supabase.table("work_days").insert(payload).execute()

        needed_for_today = max(0, DAY_START_QUEUE_TARGET - carry_forward_count)
        newly_allocated = allocate_unassigned_titles_to_operator(
            operator_username=username,
            qty=needed_for_today,
            assigned_by=SYSTEM_ASSIGNER,
            assignment_type="day_start_topup",
            notes=f"Auto-topup at Begin My Day to total queue target {DAY_START_QUEUE_TARGET}",
            bump_workday=True,
        )

        total_queue_now = carry_forward_count + len(newly_allocated)

        if newly_allocated:
            return True, f"Day started successfully. {len(newly_allocated)} fresh title(s) assigned. Total queue: {total_queue_now}."
        return True, f"Day started successfully. No fresh titles were needed. Total queue: {total_queue_now}."
    except Exception as e:
        return False, f"Failed to begin day: {e}"


def end_my_day(
    username,
    day_type,
    productive_minutes,
    non_productive_time_minutes,
    titles_completed,
    calibrations_raised,
    comments,
):
    workday = get_today_workday(username)
    if not workday:
        return False, ["You have not started your day yet."]
    if workday.get("ended_at"):
        return False, ["Your day is already closed."]

    tasks_before_close = get_operator_active_tasks(username)
    validation_errors = validate_titles_before_day_close(tasks_before_close)
    if validation_errors:
        return False, validation_errors

    snap_ok, snap_msg = save_or_update_snapshot_for_date(username, current_date_str_ist(), tasks_before_close)
    if not snap_ok:
        return False, [snap_msg]

    removed_count = close_completed_titles_for_operator(username)
    carry_forward_tasks = get_operator_active_tasks(username)
    carry_forward_count = count_carry_forward_tasks(carry_forward_tasks)

    prod_ok, prod_msg = save_or_update_productivity_log_for_date(
        username=username,
        work_date_str=current_date_str_ist(),
        day_type=day_type,
        productive_minutes=productive_minutes,
        non_productive_time_minutes=non_productive_time_minutes,
        titles_completed=titles_completed,
        calibrations_raised=calibrations_raised,
        carry_forward_count=carry_forward_count,
        comments=comments,
    )
    if not prod_ok:
        return False, [prod_msg]

    try:
        supabase.table("work_days").update({
            "ended_at": now_utc().isoformat(),
            "session_status": "Ended",
            "titles_completed_today": int(titles_completed),
            "carry_forward_count": int(carry_forward_count),
            "notes": comments,
        }).eq("id", workday["id"]).execute()

        return True, [
            "Day closed successfully.",
            "A daily work snapshot has been saved. You can download it later.",
            f"Removed {removed_count} completed title(s) from your queue.",
            f"Carry-forward title count: {carry_forward_count}",
            "No fresh titles were assigned at day close. Fresh titles will be assigned only when you begin the next day.",
        ]
    except Exception as e:
        return False, [f"Failed to close day: {e}"]


# --- 8. GLOBAL ANALYTICS ---
def render_status_counters():
    try:
        res = supabase.table("titles").select("status").execute()
        issue_count = supabase.table("issue_bin").select("id", count="exact").execute().count or 0
        rated_count = supabase.table("officially_rated_titles").select("id", count="exact").execute().count or 0

        counts = {}
        calib_raised = 0
        if res.data:
            df = pd.DataFrame(res.data)
            counts = df["status"].value_counts()
            calib_raised = counts.get("Pending Calibration", 0)

        start_utc, end_utc = day_bounds_utc_for_date(current_date_str_ist())
        calib_answered = (
            supabase.table("sme_logs")
            .select("id", count="exact")
            .gte("resolved_at", start_utc)
            .lt("resolved_at", end_utc)
            .execute()
            .count
            or 0
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📝 In Progress", counts.get("In Progress", 0))
        c2.metric("✅ Finalized", counts.get("Finalized", 0))
        c3.metric("🚩 Issues / Rated", issue_count + rated_count)
        c4.metric("🔍 Calibrations Pending", calib_raised)
        c5.metric("✔️ Calibrations Answered", calib_answered)
        st.divider()
    except Exception as e:
        st.error(f"Failed to load status counters: {e}")


def render_pool_health_dashboard():
    st.markdown("### 🚦 Pool Health")
    try:
        unassigned_count = supabase.table("titles").select("id", count="exact").eq("status", "Unassigned").execute().count or 0

        today_workdays = (
            supabase.table("work_days")
            .select("*")
            .eq("work_date", current_date_str_ist())
            .execute()
            .data
            or []
        )

        active_sessions = len([w for w in today_workdays if not w.get("ended_at")])
        assigned_today = sum(int(w.get("titles_assigned_today") or 0) for w in today_workdays)
        carry_forward_today = sum(int(w.get("carry_forward_count") or 0) for w in today_workdays)
        tomorrow_requirement = active_sessions * DAY_START_QUEUE_TARGET

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Unassigned Pool", unassigned_count)
        c2.metric("Active Sessions Today", active_sessions)
        c3.metric("Assigned Today", assigned_today)
        c4.metric("Carry Forward Today", carry_forward_today)
        c5.metric("Tomorrow Requirement", tomorrow_requirement)

        if unassigned_count < tomorrow_requirement:
            st.warning(
                f"Low pool warning: Unassigned pool ({unassigned_count}) is below tomorrow requirement ({tomorrow_requirement})."
            )
        else:
            st.success("Pool level looks sufficient for the current day-start target.")
        st.divider()
    except Exception as e:
        st.error(f"Failed to load pool health: {e}")


# --- 9. DATA ARCHIVAL ---
def archive_finalized_titles():
    try:
        data = supabase.table("titles").select("*").eq("status", "Finalized").execute().data
        if data:
            archive_records = []
            for d in data:
                d.pop("id", None)
                d.pop("updated_at", None)
                d.pop("calibration_start", None)
                d.pop("sme_comments", None)
                d["week_number"] = current_week_num_ist()
                archive_records.append(d)
            supabase.table("historical_titles").insert(archive_records).execute()
            supabase.table("titles").delete().eq("status", "Finalized").execute()
    except Exception as e:
        st.error(f"Archive failed: {e}")


def render_daily_wrapup():
    st.markdown("### 📊 Daily Wrap-Up & Export")
    try:
        start_utc, end_utc = day_bounds_utc_for_date(current_date_str_ist())
        res = (
            supabase.table("titles")
            .select("*")
            .gte("updated_at", start_utc)
            .lt("updated_at", end_utc)
            .execute()
        )

        if res.data:
            df = pd.DataFrame(res.data)
            st.write(f"Total titles touched today: **{len(df)}**")
            op_perf = df.groupby(["assigned_to", "status"])["gti"].count().reset_index()
            op_perf.columns = ["Operator", "Status", "Count"]
            st.dataframe(op_perf, use_container_width=True)

            df_export = append_date_week(df)
            csv = df_export.to_csv(index=False).encode("utf-8")
            st.info("⚠️ Downloading this report will archive 'Finalized' titles to the Historical Database.")
            st.download_button(
                "📥 Export Wrap-Up & Archive Finalized Data",
                data=csv,
                file_name=f"wrapup_{current_date_str_ist()}_W{current_week_num_ist()}.csv",
                mime="text/csv",
                on_click=archive_finalized_titles,
            )
        else:
            st.info("No data recorded for today yet.")
    except Exception as e:
        st.error(f"Failed to load daily wrap-up: {e}")


# --- 10. WORKFLOW MODULES ---
def render_operator(username):
    auto_closed = auto_close_overdue_workdays(username)
    for d in auto_closed:
        st.warning(f"Workday {d} was auto-closed after 12 hours. Please complete its productivity details before starting a new day.")

    try:
        missing_prod_wd = get_latest_missing_productivity_workday(username)
        missing_leave_date = None if missing_prod_wd else get_missing_leave_date(username)

        workday = get_today_workday(username)
        session_active = bool(workday and not workday.get("ended_at"))
        productivity_log = get_today_productivity_log(username)
        tasks = get_operator_active_tasks(username)
        summary = get_operator_task_summary(tasks)
        carry_forward_count = count_carry_forward_tasks(tasks)
        cumulative = get_monthly_productivity_for_operator(username)
        today_event_metrics = get_event_metrics_for_date(username, current_date_str_ist())

        st.markdown(
            f"""
            <div class="terran-header">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap;">
                    <div>
                        <div class="terran-title">Operator Workspace</div>
                        <div class="terran-subtitle">{username}</div>
                    </div>
                    <div>
                        {"<span class='terran-chip'>Day Active</span>" if session_active else "<span class='terran-chip'>Day Not Started / Closed</span>"}
                        <span class='terran-chip'>Target Queue: {DAY_START_QUEUE_TARGET}</span>
                        <span class='terran-chip'>Carry Forward: {carry_forward_count}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        blocker_active = False

        if missing_prod_wd:
            blocker_active = True
            missing_date = missing_prod_wd["work_date"]
            prev_metrics = get_event_metrics_for_date(username, missing_date)

            st.warning(f"You must complete productivity for {missing_date} before Begin My Day is enabled.")

            with st.container(border=True):
                with st.form(f"prev_prod_form_{missing_date}"):
                    day_type = st.selectbox("Previous Day Type", ["Full Day", "Half Day", "Custom"], index=0)
                    default_minutes = 480 if day_type == "Full Day" else 240 if day_type == "Half Day" else 480
                    productive_minutes = st.number_input(
                        "Previous Day Productive Minutes",
                        min_value=0,
                        max_value=1440,
                        value=default_minutes,
                        step=15,
                        key=f"prev_pm_{missing_date}",
                    )
                    st.caption(f"Productive Hours (auto): **{round(productive_minutes / 60, 2)} hrs**")
                    non_productive_time_minutes = st.number_input(
                        "Previous Day NPT (minutes)",
                        min_value=0,
                        max_value=1440,
                        value=0,
                        step=5,
                        key=f"prev_npt_{missing_date}",
                    )
                    titles_completed = st.number_input(
                        "Titles Reviewed That Day",
                        min_value=0,
                        max_value=200,
                        value=int(prev_metrics["reviewed_today"]),
                        step=1,
                        key=f"prev_titles_{missing_date}",
                    )
                    calibrations_raised = st.number_input(
                        "Calibrations Raised That Day",
                        min_value=0,
                        max_value=200,
                        value=int(prev_metrics["calibrations_raised_today"]),
                        step=1,
                        key=f"prev_calibs_{missing_date}",
                    )
                    comments = st.text_area("Comments", key=f"prev_comments_{missing_date}")
                    submitted = st.form_submit_button("✅ Save Previous Day Productivity")

                    if submitted:
                        carry_forward_from_wd = int(missing_prod_wd.get("carry_forward_count") or 0)
                        ok, msg = save_or_update_productivity_log_for_date(
                            username=username,
                            work_date_str=missing_date,
                            day_type=day_type,
                            productive_minutes=productive_minutes,
                            non_productive_time_minutes=non_productive_time_minutes,
                            titles_completed=titles_completed,
                            calibrations_raised=calibrations_raised,
                            carry_forward_count=carry_forward_from_wd,
                            comments=comments,
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        elif missing_leave_date:
            blocker_active = True
            st.warning(f"No workday or leave was logged for {missing_leave_date}. Please log leave before Begin My Day is enabled.")

            with st.container(border=True):
                with st.form(f"leave_form_{missing_leave_date}"):
                    leave_type = st.selectbox("Leave Type", LEAVE_TYPES, index=0)
                    notes = st.text_area("Notes")
                    submitted = st.form_submit_button("✅ Save Leave Log")

                    if submitted:
                        ok, msg = save_leave_log(username, missing_leave_date, leave_type, notes)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # Compact control strip
        st.markdown('<div class="terran-strip">', unsafe_allow_html=True)
        strip_c1, strip_c2, strip_c3, strip_c4, strip_c5, strip_c6, strip_c7, strip_c8 = st.columns([1.1, 1.2, 1.3, 1.0, 1.0, 1.2, 1.2, 1.4])

        strip_c1.metric("Queue", summary["total"])
        strip_c2.metric("In Progress", summary["in_progress"])
        strip_c3.metric("Pending Calibration", summary["pending_calibration"])
        strip_c4.metric("Reviewed", summary["reviewed"])
        strip_c5.metric("Carry Forward", carry_forward_count)

        if not session_active and not (workday and workday.get("ended_at")):
            if strip_c6.button(
                "🌅 Begin My Day",
                type="primary",
                use_container_width=True,
                disabled=blocker_active,
                help="Start your workday and attempt to fill your base queue to 7 titles including carry-forward."
            ):
                ok, msg = begin_my_day(username)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            strip_c6.empty()

        if session_active and summary["total"] < DAY_START_QUEUE_TARGET:
            needed = DAY_START_QUEUE_TARGET - summary["total"]
            if strip_c7.button(
                "📥 Assign Titles",
                use_container_width=True,
                help="Fill your base queue up to 7 titles for the active day."
            ):
                allocated = allocate_unassigned_titles_to_operator(
                    operator_username=username,
                    qty=needed,
                    assigned_by=SYSTEM_ASSIGNER,
                    assignment_type="manual_base_queue_fill",
                    notes=f"Operator requested base queue fill to reach {DAY_START_QUEUE_TARGET}",
                    bump_workday=True,
                )
                if allocated:
                    st.success(f"Assigned {len(allocated)} title(s). Queue topped up toward {DAY_START_QUEUE_TARGET}.")
                    st.rerun()
                else:
                    st.warning("No unassigned titles available in the pool.")
        else:
            strip_c7.empty()

        existing_reqs = supabase.table("requests").select("*").eq("operator_email", username).execute().data or []
        pending_req = any(r["status"] == "Pending" for r in existing_reqs)
        last_req = sorted(existing_reqs, key=lambda x: x.get("created_at", ""), reverse=True) if existing_reqs else []

        if strip_c8.button(
            "➕ Request Extra Titles",
            use_container_width=True,
            disabled=not session_active,
            help="Request titles above your standard base queue."
        ):
            if pending_req:
                st.warning("You already have a pending request. Please wait for management approval.")
            elif not existing_reqs:
                allocated = allocate_unassigned_titles_to_operator(
                    operator_username=username,
                    qty=2,
                    assigned_by=SYSTEM_ASSIGNER,
                    assignment_type="first_extra_request_auto",
                    notes="First extra title request auto-approved",
                    bump_workday=True,
                )
                if allocated:
                    supabase.table("requests").insert({"operator_email": username, "status": "Fulfilled"}).execute()
                    st.success(f"First extra request auto-approved! {len(allocated)} title(s) assigned.")
                    st.rerun()
                else:
                    st.error("No unassigned titles available.")
            else:
                supabase.table("requests").insert({"operator_email": username, "status": "Pending"}).execute()
                st.info("Request sent to Management.")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        if last_req and last_req[0]["status"] == "Denied":
            st.warning(f"Notice: {last_req[0].get('denial_reason', 'Request Denied.')}")

        # Compact productivity strip
        st.markdown('<div class="terran-strip">', unsafe_allow_html=True)
        p1, p2, p3, p4, p5, p6, p7 = st.columns([1.2, 1.0, 1.0, 1.2, 1.0, 1.0, 1.1])

        if productivity_log:
            p1.metric("Today Minutes", productivity_log.get("productive_minutes", 0))
            p2.metric("Today Hours", productivity_log.get("productive_hours", 0))
            p3.metric("Reviewed Today", productivity_log.get("titles_completed", 0))
            p4.metric("Calibs Today", productivity_log.get("calibrations_raised", 0))
            p5.metric("Month Titles", cumulative["titles_worked"])
            p6.metric("Month NPT", cumulative["total_npt"])
            p7.metric("Productivity %", cumulative["productivity_pct"])
        else:
            p1.metric("Today Minutes", 0)
            p2.metric("Today Hours", 0)
            p3.metric("Reviewed Today", int(today_event_metrics["reviewed_today"]))
            p4.metric("Calibs Today", int(today_event_metrics["calibrations_raised_today"]))
            p5.metric("Month Titles", cumulative["titles_worked"])
            p6.metric("Month NPT", cumulative["total_npt"])
            p7.metric("Productivity %", cumulative["productivity_pct"])
        st.markdown('</div>', unsafe_allow_html=True)

        if session_active:
            with st.expander("🌙 End My Day", expanded=False):
                st.warning("Complete your day, validate your work, and log productivity before closing.")
                with st.form("end_day_form"):
                    day_type = st.selectbox("Day Type", ["Full Day", "Half Day", "Custom"], index=0)
                    default_minutes = 480 if day_type == "Full Day" else 240 if day_type == "Half Day" else 480

                    productive_minutes = st.number_input(
                        "Productive Minutes",
                        min_value=0,
                        max_value=1440,
                        value=default_minutes,
                        step=15,
                    )
                    st.caption(f"Productive Hours (auto-calculated): **{round(productive_minutes / 60, 2)} hrs**")

                    non_productive_time_minutes = st.number_input(
                        "Non-Productive Time (minutes)",
                        min_value=0,
                        max_value=1440,
                        value=0,
                        step=5,
                    )

                    titles_completed = st.number_input(
                        "Titles Reviewed Today",
                        min_value=0,
                        max_value=200,
                        value=int(today_event_metrics["reviewed_today"]),
                        step=1,
                    )

                    calibrations_raised = st.number_input(
                        "Calibrations Raised Today",
                        min_value=0,
                        max_value=200,
                        value=int(today_event_metrics["calibrations_raised_today"]),
                        step=1,
                    )

                    comments = st.text_area("Productivity Notes / Day-End Comments")
                    submitted = st.form_submit_button("✅ Submit & End My Day")

                    if submitted:
                        ok, messages = end_my_day(
                            username=username,
                            day_type=day_type,
                            productive_minutes=productive_minutes,
                            non_productive_time_minutes=non_productive_time_minutes,
                            titles_completed=titles_completed,
                            calibrations_raised=calibrations_raised,
                            comments=comments,
                        )
                        if ok:
                            for m in messages:
                                st.success(m)
                            st.rerun()
                        else:
                            st.error("Could not close day.")
                            for m in messages:
                                st.warning(m)

        # Queue workbench
        st.markdown('<div class="terran-queue">', unsafe_allow_html=True)
        st.markdown('<div class="terran-section-title">My Queue</div>', unsafe_allow_html=True)

        if not tasks:
            st.info("No titles assigned.")
        else:
            tab_labels = []
            for i, t in enumerate(tasks, start=1):
                short_title = t.get("title_name") or t.get("gti") or f"Title {i}"
                short_title = short_title[:18]
                tab_labels.append(short_title)

            tabs = st.tabs(tab_labels)

            for tab, t in zip(tabs, tasks):
                with tab:
                    locked = t["status"] in ["Reviewed by Operator", "Pending Calibration", "Finalized"]
                    edit_disabled = locked or not session_active
                    display_title = t.get("title_name") if t.get("title_name") else "Pending EDP Lookup"

                    gti_chip = f"<span class='terran-mini-chip'>GTI: {t.get('gti')}</span>"
                    status_chip = f"<span class='terran-mini-chip'>{t.get('status', 'Unknown')}</span>"
                    asset_chip = f"<span class='terran-mini-chip'>{t.get('asset_type', 'Asset')}</span>" if t.get("asset_type") else ""

                    st.markdown(
                        f"""
                        <div class="terran-soft-card">
                            <div class="terran-soft-title">{display_title}</div>
                            {gti_chip} {status_chip} {asset_chip}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if t.get("sme_comments"):
                        st.error(f"SME Feedback: {t['sme_comments']}")

                    if not session_active:
                        st.info("Day is closed. Queue is visible, but edits are disabled.")

                    if session_active and t.get("status") == "Pending Calibration":
                        if st.button(
                            "↩️ Recall From SME Review",
                            key=f"recall_{t['id']}",
                            help="Pull this title back from SME review if it was sent by mistake."
                        ):
                            supabase.table("titles").update({
                                "status": "In Progress",
                                "updated_at": now_utc().isoformat(),
                            }).eq("id", t["id"]).execute()
                            log_title_event(
                                gti=t["gti"],
                                username=username,
                                event_type="recall_from_sme",
                                old_status="Pending Calibration",
                                new_status="In Progress",
                                notes="Operator recalled title from SME review",
                            )
                            st.success("Title recalled from SME review.")
                            st.rerun()

                    w1, w2, w3 = st.columns([1, 1, 1.1], gap="large")

                    with w1:
                        with st.container(border=True):
                            st.markdown("##### 1. Asset Identification")
                            st.code(t["gti"], language=None)
                            t_name = st.text_input("Title Name (EDP)", value=t.get("title_name", ""), key=f"tn_{t['id']}", disabled=edit_disabled)
                            edp_url = st.text_input("EDP Link", value=t.get("edp_link", ""), key=f"el_{t['id']}", disabled=edit_disabled)

                            a_type_idx = 1 if t.get("asset_type") == "Episode" else 0
                            a_type = st.radio("Asset Type", ["Movie", "Episode"], index=a_type_idx, horizontal=True, key=f"at_{t['id']}", disabled=edit_disabled)
                            amz_orig = st.radio(
                                "Amazon Original?",
                                ["No", "Yes"],
                                index=1 if t.get("amazon_original") == "Yes" else 0,
                                horizontal=True,
                                key=f"ao_{t['id']}",
                                disabled=edit_disabled,
                            )
                            st.write("")
                            st.caption(f"Current Status: {t.get('status', '-')}")
                            st.caption(f"Amazon Original: {t.get('amazon_original', '-') or 'No'}")

                    with w2:
                        with st.container(border=True):
                            st.markdown("##### 2. Classification Status")
                            run_t = st.text_input("Runtime", value=t.get("runtime", ""), placeholder="e.g. 1h 45m", key=f"rt_{t['id']}", disabled=edit_disabled)
                            off_rtg = st.selectbox(
                                "Official Rating",
                                OFFICIAL_RATING_LIST,
                                index=get_idx(t.get("official_rating", "Not Officially Rated"), OFFICIAL_RATING_LIST),
                                key=f"or_{t['id']}",
                                disabled=edit_disabled,
                            )
                            is_off = off_rtg != "Not Officially Rated"
                            mr = st.selectbox("MR Rating", MR_LIST, index=get_idx(t.get("mr_rating", MR_LIST[0]), MR_LIST), key=f"mr_{t['id']}", disabled=edit_disabled or is_off)
                            stat = st.selectbox("Actionable Status", OP_STATUS_OPTIONS, index=get_idx(t.get("status", "In Progress"), OP_STATUS_OPTIONS), key=f"st_{t['id']}", disabled=edit_disabled or is_off)

                            off_rtg_date = None
                            if is_off and not edit_disabled:
                                st.info("Title is officially rated. Please provide the rating date.")
                                off_rtg_date = st.date_input("Official Rating Date", key=f"ord_{t['id']}")

                            saved_cds = t.get("cd_values") or []
                            defaults = [opt for opt in UNIFIED_CA_LIST if opt.split(": ", 1)[1] in saved_cds]

                            selected_full = st.multiselect(
                                "Content Advice",
                                options=UNIFIED_CA_LIST,
                                default=defaults,
                                key=f"uni_{t['id']}",
                                disabled=edit_disabled,
                            )
                            clean_cds = [item.split(": ", 1)[1] for item in selected_full]

                            calib_cd_val, calib_mr_val = None, None
                            if stat == "Pending Calibration" and not edit_disabled and not is_off:
                                calib_cd_val = st.selectbox("Calibrating Content Advice", ALL_CAS, key=f"ccd_{t['id']}")
                                calib_mr_val = st.selectbox("Proposed MR", MR_LIST, key=f"cmr_{t['id']}")
                            else:
                                calib_cd_val = t.get("calib_cd")
                                calib_mr_val = t.get("calib_mr")

                    with w3:
                        with st.container(border=True):
                            st.markdown("##### 3. Analysis & Notes")
                            p_drive = st.text_area("Primary Drivers", value=t.get("primary_drivers", ""), key=f"p_{t['id']}", disabled=edit_disabled, height=90)
                            s_drive = st.text_area("Secondary Drivers", value=t.get("secondary_drivers", ""), key=f"s_{t['id']}", disabled=edit_disabled, height=90)
                            ndi_txt = st.text_area("Non-Defining Issues", value=t.get("ndi_text", ""), key=f"ndi_{t['id']}", disabled=edit_disabled, height=70)
                            ops_comm = st.text_area("Ops Comments", value=t.get("ops_comments", ""), key=f"oc_{t['id']}", disabled=edit_disabled, height=70)

                            if st.button(
                                "Save & Submit Asset",
                                type="primary",
                                key=f"save_{t['id']}",
                                disabled=not session_active,
                                help="Save the current title details and move the title through the workflow based on the selected actionable status."
                            ):
                                old_status = t.get("status")

                                if is_off:
                                    record = {
                                        "gti": t["gti"],
                                        "title_name": t_name,
                                        "edp_link": edp_url,
                                        "asset_type": a_type,
                                        "amazon_original": amz_orig,
                                        "runtime": run_t,
                                        "official_rating": off_rtg,
                                        "official_rating_date": off_rtg_date.isoformat() if off_rtg_date else None,
                                        "mr_rating": mr,
                                        "cd_values": clean_cds,
                                        "primary_drivers": p_drive,
                                        "secondary_drivers": s_drive,
                                        "ndi_text": ndi_txt,
                                        "ops_comments": ops_comm,
                                        "flagged_by": username,
                                    }
                                    supabase.table("officially_rated_titles").insert(record).execute()
                                    supabase.table("titles").delete().eq("id", t["id"]).execute()
                                    log_title_event(t["gti"], username, "officially_rated_diversion", old_status, "Officially Rated", "Moved to officially rated titles")

                                    allocated = allocate_unassigned_titles_to_operator(
                                        operator_username=username,
                                        qty=1,
                                        assigned_by=SYSTEM_ASSIGNER,
                                        assignment_type="replacement_officially_rated",
                                        notes="Replacement after officially rated diversion",
                                        bump_workday=True,
                                    )
                                    if allocated:
                                        st.success("Officially Rated Title logged. 1 new title automatically assigned.")
                                    else:
                                        st.warning("Officially Rated Title logged. No replacements available.")

                                elif stat == "Title Issue":
                                    supabase.table("issue_bin").insert({
                                        "gti": t["gti"],
                                        "title_name": t_name,
                                        "flagged_by": username,
                                        "issue_details": p_drive,
                                    }).execute()
                                    supabase.table("titles").delete().eq("id", t["id"]).execute()
                                    log_title_event(t["gti"], username, "title_issue_diversion", old_status, "Title Issue", "Moved to issue bin")

                                    allocated = allocate_unassigned_titles_to_operator(
                                        operator_username=username,
                                        qty=1,
                                        assigned_by=SYSTEM_ASSIGNER,
                                        assignment_type="replacement_title_issue",
                                        notes="Replacement after title issue diversion",
                                        bump_workday=True,
                                    )
                                    if allocated:
                                        st.success("Issue Submitted. 1 new title automatically assigned.")
                                    else:
                                        st.warning("Issue Submitted. No replacements available.")

                                else:
                                    upd = {
                                        "title_name": t_name,
                                        "edp_link": edp_url,
                                        "asset_type": a_type,
                                        "amazon_original": amz_orig,
                                        "runtime": run_t,
                                        "official_rating": off_rtg,
                                        "mr_rating": mr,
                                        "cd_values": clean_cds,
                                        "status": stat,
                                        "primary_drivers": p_drive,
                                        "secondary_drivers": s_drive,
                                        "ndi_text": ndi_txt,
                                        "ops_comments": ops_comm,
                                        "updated_at": now_utc().isoformat(),
                                    }
                                    if stat == "Pending Calibration":
                                        upd["calibration_start"] = now_utc().isoformat()
                                        upd["calib_cd"] = calib_cd_val
                                        upd["calib_mr"] = calib_mr_val

                                    supabase.table("titles").update(upd).eq("id", t["id"]).execute()

                                    if old_status != stat:
                                        log_title_event(t["gti"], username, "status_change", old_status, stat, "Operator status update")

                                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Operator workspace failed to load: {e}")


def render_sme(username):
    st.subheader("🔍 SME Calibration Dashboard")
    try:
        pending = supabase.table("titles").select("*").eq("status", "Pending Calibration").execute().data or []
        start_utc, end_utc = day_bounds_utc_for_date(current_date_str_ist())

        my_logs = (
            supabase.table("sme_logs")
            .select("*")
            .eq("sme_username", username)
            .gte("resolved_at", start_utc)
            .lt("resolved_at", end_utc)
            .execute()
            .data
            or []
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Titles in Calibration", len(pending))
        col2.metric("Calibrations Resolved Today", len(my_logs))

        if my_logs:
            df_sme = append_date_week(pd.DataFrame(my_logs))
            csv_sme = df_sme.to_csv(index=False).encode("utf-8")
            col3.download_button(
                "📥 Download My Daily Log",
                csv_sme,
                f"sme_log_{current_date_str_ist()}_W{current_week_num_ist()}.csv",
                "text/csv",
            )

        st.divider()

        for p in pending:
            calib_start = p.get("calibration_start")
            time_passed = "Unknown"
            time_mins = 0

            if calib_start:
                start_dt = datetime.fromisoformat(calib_start.replace("Z", "+00:00"))
                diff = now_utc() - start_dt
                time_mins = diff.total_seconds() / 60
                time_passed = f"{int(time_mins // 60)}h {int(time_mins % 60)}m"

            with st.expander(f"📋 {p['gti']} | Ops: {p['assigned_to']} | ⏱️ Queue Time: {time_passed}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Calib CA:** {p.get('calib_cd')}")
                c2.write(f"**Proposed MR:** {p.get('calib_mr')}")
                c3.write(f"**Asset:** {p.get('asset_type')}")

                st.info(f"**Ops Comments:** {p.get('ops_comments')}")
                feedback = st.text_area("SME Feedback & Resolution", key=f"fb_{p['id']}")

                if st.button("⏪ Close Calibration (Return to Ops)", type="primary", key=f"re_{p['id']}"):
                    log_entry = {
                        "gti": p["gti"],
                        "sme_username": username,
                        "calib_cd": p.get("calib_cd"),
                        "calib_mr": p.get("calib_mr"),
                        "ops_comments": p.get("ops_comments"),
                        "sme_comments": feedback,
                        "time_taken_minutes": round(time_mins, 2),
                        "resolved_at": now_utc().isoformat(),
                    }
                    supabase.table("sme_logs").insert(log_entry).execute()
                    supabase.table("titles").update({
                        "status": "In Progress",
                        "sme_comments": feedback,
                        "updated_at": now_utc().isoformat(),
                    }).eq("id", p["id"]).execute()
                    log_title_event(p["gti"], p.get("assigned_to"), "sme_return", "Pending Calibration", "In Progress", "SME closed calibration and returned to ops")
                    st.rerun()

    except Exception as e:
        st.error(f"SME dashboard failed to load: {e}")


def render_productivity_tab():
    st.markdown("### 📈 Productivity")
    st.caption(f"Monthly productivity formula: (Titles Worked in Month × {round(AHT_MINUTES, 2)}) / (Total Minutes Worked in Month − NPT in Month) × 100")

    try:
        workdays = (
            supabase.table("work_days")
            .select("*")
            .eq("work_date", current_date_str_ist())
            .execute()
            .data
            or []
        )

        today_logs = (
            supabase.table("productivity_logs")
            .select("*")
            .eq("work_date", current_date_str_ist())
            .execute()
            .data
            or []
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Active Sessions", len([w for w in workdays if not w.get("ended_at")]))
        c2.metric("Ended Sessions", len([w for w in workdays if w.get("ended_at")]))
        c3.metric("Today's Productivity Logs", len(today_logs))

        st.divider()

        st.markdown("#### Today's Productivity Logs")
        if today_logs:
            st.dataframe(pd.DataFrame(today_logs), use_container_width=True)
        else:
            st.info("No productivity logs for today.")

        st.markdown("#### Current Month Productivity by Operator")
        month_df = get_current_month_productivity_table()
        if not month_df.empty:
            st.dataframe(month_df, use_container_width=True)
        else:
            st.info("No monthly productivity data found.")
    except Exception as e:
        st.error(f"Failed to load productivity overview: {e}")


def render_allocation_logs_tab():
    st.markdown("### 🧾 Allocation Logs")
    try:
        logs = (
            supabase.table("allocation_logs")
            .select("*")
            .eq("work_date", current_date_str_ist())
            .execute()
            .data
            or []
        )
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True)
        else:
            st.info("No allocation logs for today.")
    except Exception as e:
        st.error(f"Failed to load allocation logs: {e}")


def render_title_event_logs_tab():
    st.markdown("### 📝 Title Event Logs")
    try:
        start_utc, end_utc = day_bounds_utc_for_date(current_date_str_ist())
        logs = (
            supabase.table("title_event_logs")
            .select("*")
            .gte("created_at", start_utc)
            .lt("created_at", end_utc)
            .execute()
            .data
            or []
        )
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True)
        else:
            st.info("No title events for today.")
    except Exception as e:
        st.error(f"Failed to load title event logs: {e}")


def render_mgmt(role):
    render_pool_health_dashboard()
    render_status_counters()

    tabs = st.tabs([
        "📁 Active DB",
        "⬆️ Upload",
        "📥 Requests",
        "📦 Allocation",
        "📊 Wrap-Up",
        "📈 Productivity",
        "🧾 Allocation Logs",
        "📝 Title Events",
        "🗄️ Historical",
        "🚩 Issues & Rated",
    ])

    t_db, t_up, t_req, t_alloc, t_wrap, t_prod, t_alog, t_tevents, t_hist, t_bin = tabs

    with t_db:
        try:
            search = st.text_input("🔍 Search Database (GTI/Name)")
            q = supabase.table("titles").select("*")
            if search:
                q = q.or_(f"gti.ilike.%{search}%,title_name.ilike.%{search}%")
            data = q.execute().data or []
            if data:
                st.dataframe(pd.DataFrame(data)[["gti", "title_name", "asset_type", "assigned_to", "status"]], use_container_width=True)
            else:
                st.info("No active title data found.")
        except Exception as e:
            st.error(f"Failed to load active database: {e}")

    with t_up:
        st.info("Upload CSV containing the header: `gti`")
        uploaded_file = st.file_uploader("Select CSV", type=["csv"])
        if uploaded_file and st.button("Upload to Pool"):
            try:
                df = pd.read_csv(uploaded_file)
                if "gti" in df.columns:
                    records = [{"gti": str(row["gti"]), "status": "Unassigned"} for _, row in df.iterrows()]
                    supabase.table("titles").insert(records).execute()
                    st.success(f"Added {len(records)} GTIs to Unassigned pool.")
                else:
                    st.error("CSV must contain 'gti' column.")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    with t_req:
        try:
            reqs = supabase.table("requests").select("*").eq("status", "Pending").execute().data or []
            for r in reqs:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.write(f"**{r['operator_email']}** requests extra work.")
                    if c2.button("Approve (+2)", key=f"q_{r['id']}"):
                        allocated = allocate_unassigned_titles_to_operator(
                            operator_username=r["operator_email"],
                            qty=2,
                            assigned_by=role,
                            assignment_type="request_approve_2",
                            notes="Approved extra title request",
                            bump_workday=True,
                        )
                        supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r["id"]).execute()
                        st.success(f"Assigned {len(allocated)} title(s).")
                        st.rerun()

                    qty = c3.number_input("Custom Qty", 1, 20, 5, key=f"qty_{r['id']}")
                    if c4.button("Assign", key=f"c_{r['id']}"):
                        allocated = allocate_unassigned_titles_to_operator(
                            operator_username=r["operator_email"],
                            qty=qty,
                            assigned_by=role,
                            assignment_type="request_custom_assign",
                            notes="Custom extra title request approval",
                            bump_workday=True,
                        )
                        supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r["id"]).execute()
                        st.success(f"Assigned {len(allocated)} title(s).")
                        st.rerun()

                    d_reason = st.text_input("Denial Reason", "Please focus on your current queue.", key=f"dr_{r['id']}")
                    if st.button("🚫 Deny Request", key=f"d_{r['id']}"):
                        supabase.table("requests").update({"status": "Denied", "denial_reason": d_reason}).eq("id", r["id"]).execute()
                        st.rerun()
        except Exception as e:
            st.error(f"Failed to load requests: {e}")

    with t_alloc:
        try:
            ops = [o["username"] for o in (supabase.table("app_users").select("username").eq("role", "Operator").execute().data or [])]
            st.markdown("#### 🔄 Bulk Operator Allocation")
            sel_ops = st.multiselect("Select Operators", ops)
            b_qty = st.number_input("Batch Size per Operator", 1, 50, 5)
            if st.button("Distribute Titles"):
                total_assigned = 0
                for o in sel_ops:
                    allocated = allocate_unassigned_titles_to_operator(
                        operator_username=o,
                        qty=b_qty,
                        assigned_by=role,
                        assignment_type="bulk_allocation",
                        notes="Bulk operator allocation",
                        bump_workday=True,
                    )
                    total_assigned += len(allocated)
                st.success(f"Bulk Distribution Complete. Assigned {total_assigned} title(s).")

            st.divider()
            st.markdown("#### 🎯 Targeted GTI Assignment")
            col_a, col_b, col_c = st.columns([2, 2, 1])
            t_gti = col_a.text_input("Specific GTI ID")
            t_op = col_b.selectbox("Assign to Operator", ops, key="target_op")
            if col_c.button("Assign Specific"):
                target = supabase.table("titles").select("id, gti").eq("gti", t_gti).limit(1).execute().data or []
                if target:
                    supabase.table("titles").update({
                        "assigned_to": t_op,
                        "status": "In Progress",
                        "updated_at": now_utc().isoformat(),
                    }).eq("id", target[0]["id"]).execute()
                    bump_titles_assigned_today(t_op, 1)
                    log_allocation(target[0]["gti"], t_op, role, "targeted_assignment", "Specific GTI targeted assignment")
                    st.success(f"GTI {t_gti} assigned to {t_op}.")
                else:
                    st.error("GTI not found.")
        except Exception as e:
            st.error(f"Failed to load allocation tools: {e}")

    with t_wrap:
        render_daily_wrapup()

    with t_prod:
        render_productivity_tab()

    with t_alog:
        render_allocation_logs_tab()

    with t_tevents:
        render_title_event_logs_tab()

    with t_hist:
        st.markdown("### 🗄️ Historical Archive Explorer")
        st.info("Filter historically finalized titles by Date Range.")
        try:
            date_range = st.date_input("Select Export Date Range", [])
            if len(date_range) == 2:
                start_date, end_date = date_range
                hist_data = (
                    supabase.table("historical_titles")
                    .select("*")
                    .gte("export_date", start_date.strftime("%Y-%m-%d"))
                    .lte("export_date", end_date.strftime("%Y-%m-%d"))
                    .execute()
                    .data
                    or []
                )

                if hist_data:
                    df_hist = append_date_week(pd.DataFrame(hist_data))
                    st.write(f"Found **{len(df_hist)}** records.")
                    st.dataframe(df_hist, use_container_width=True)
                    csv_hist = df_hist.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "📥 Download Filtered Archive",
                        csv_hist,
                        f"historical_data_{start_date}_to_{end_date}.csv",
                        "text/csv",
                    )
                else:
                    st.warning("No records found in this date range.")
            else:
                st.write("Please select both a start and end date to view records.")
        except Exception as e:
            st.error(f"Failed to load historical archive: {e}")

    with t_bin:
        try:
            st.markdown("### 🚩 Title Issues")
            issues = supabase.table("issue_bin").select("*").execute().data or []
            if issues:
                df_iss = append_date_week(pd.DataFrame(issues))
                st.dataframe(df_iss, use_container_width=True)
                csv_iss = df_iss.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Issue Bin", csv_iss, f"issue_bin_W{current_week_num_ist()}.csv", "text/csv")
            else:
                st.info("No issues currently flagged.")

            st.divider()
            st.markdown("### 📌 Officially Rated Titles")
            off_rated = supabase.table("officially_rated_titles").select("*").execute().data or []
            if off_rated:
                df_off = append_date_week(pd.DataFrame(off_rated))
                st.dataframe(df_off, use_container_width=True)
                csv_off = df_off.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Rated Titles", csv_off, f"officially_rated_W{current_week_num_ist()}.csv", "text/csv")
            else:
                st.info("No officially rated titles logged yet.")
        except Exception as e:
            st.error(f"Failed to load issues/rated titles: {e}")


# --- 11. AUTHENTICATION & ROUTING ---
if st.session_state.user is None:
    st.title("🛡️ The Terran")
    tab_l, tab_a, tab_s = st.tabs(["👤 Login", "🔑 Admin Portal", "📝 Signup"])

    with tab_l:
        u_in = st.text_input("User")
        p_in = st.text_input("Pass", type="password")
        if st.button("Log In"):
            try:
                res = supabase.table("app_users").select("*").eq("username", u_in).execute()
                if res.data and res.data[0]["password"] == hash_pw(p_in):
                    if res.data[0]["is_approved"]:
                        set_logged_in_user(res.data[0])
                        st.rerun()
                    else:
                        st.warning("Account pending Admin approval.")
                else:
                    st.error("Invalid Credentials.")
            except Exception as e:
                st.error(f"Login failed: {e}")

    with tab_a:
        a_pw = st.text_input("Master Key", type="password")
        if st.button("Authorize"):
            try:
                res = supabase.table("app_users").select("*").eq("username", ADMIN_USERNAME).execute()
                if res.data and hash_pw(a_pw) == res.data[0]["password"]:
                    set_logged_in_user(res.data[0])
                    st.rerun()
                else:
                    st.error("Master Key Invalid.")
            except Exception as e:
                st.error(f"Admin login failed: {e}")

    with tab_s:
        s_u = st.text_input("New Username")
        s_p = st.text_input("New Password", type="password")
        s_r = st.selectbox("Role", ROLES)
        if st.button("Sign Up"):
            try:
                is_app = s_r == "Operator"
                supabase.table("app_users").insert({
                    "username": s_u,
                    "password": hash_pw(s_p),
                    "role": s_r,
                    "is_approved": is_app,
                }).execute()
                st.success("Account created!" if is_app else "Account created. Awaiting Admin approval.")
            except Exception as e:
                st.error(f"Signup failed: {e}")

else:
    u = st.session_state.user

    st.sidebar.subheader(f"👋 {u['username']}")
    st.sidebar.caption(f"Role: **{u['role']}**")
    st.sidebar.info(display_date_ist())
    st.sidebar.info(display_time_ist())

    if u["role"] == "Operator":
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Downloads")

        today_prod = get_today_productivity_log(u["username"])
        today_records = get_todays_work_download_records(u["username"])
        today_csv = safe_csv_from_records(today_records)

        st.sidebar.download_button(
            "📥 Download Today's Work",
            today_csv,
            f"todays_work_{u['username']}_{current_date_str_ist()}.csv",
            "text/csv",
            disabled=today_prod is None,
            help="Download today's work after productivity has been logged for the day.",
            use_container_width=True,
        )

        month_records = get_monthly_completed_work_records(u["username"])
        month_csv = safe_csv_from_records(month_records)
        st.sidebar.download_button(
            "📥 Download All My Work",
            month_csv,
            f"all_my_work_{u['username']}_{today_ist_date().strftime('%Y_%m')}.csv",
            "text/csv",
            help="Download your month-to-date completed work backup.",
            use_container_width=True,
        )

    if st.sidebar.button("Logout"):
        clear_logged_in_user()
        st.rerun()

    if u["role"] == "Admin":
        at1, at2, at3, at4 = st.tabs(["⚙️ Roster & Security", "📝 Operator View", "🔍 SME View", "📊 Mgmt View"])
        with at1:
            try:
                users = supabase.table("app_users").select("*").execute().data or []
                st.markdown("### User Approvals & Passwords")
                for user in users:
                    if user["username"] != ADMIN_USERNAME:
                        with st.container(border=True):
                            c1, c2, c3, c4, c5 = st.columns([2, 1, 2, 1, 1])
                            c1.write(f"**{user['username']}** ({user['role']})")
                            if not user["is_approved"] and c2.button("Approve", key=f"app_{user['username']}"):
                                supabase.table("app_users").update({"is_approved": True}).eq("username", user["username"]).execute()
                                st.rerun()
                            new_pw = c3.text_input("New PW", type="password", key=f"pw_{user['username']}")
                            if c4.button("Reset", key=f"rst_{user['username']}"):
                                supabase.table("app_users").update({"password": hash_pw(new_pw)}).eq("username", user["username"]).execute()
                                st.success("Reset")
                            if c5.button("Delete", type="primary", key=f"del_{user['username']}"):
                                supabase.table("app_users").delete().eq("username", user["username"]).execute()
                                st.rerun()
            except Exception as e:
                st.error(f"Failed to load roster/security tools: {e}")

        with at2:
            render_operator(u["username"])
        with at3:
            render_sme(u["username"])
        with at4:
            render_mgmt("Admin")

    elif u["role"] in ["Manager", "Allocator"]:
        render_mgmt(u["role"])
    elif u["role"] == "SME":
        render_sme(u["username"])
    elif u["role"] == "Operator":
        render_operator(u["username"])