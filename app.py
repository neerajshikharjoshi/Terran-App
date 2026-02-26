import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone
import pandas as pd
import hashlib

# --- 1. CONFIGURATION & PERSISTENCE ---
st.set_page_config(page_title="The Terran | Content Ops", layout="wide")

url = st.secrets.get("SUPABASE_URL")
key = st.secrets.get("SUPABASE_KEY")

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Database Connection Failed. Check Streamlit Secrets.")
    st.stop()

# --- REFRESH FIX: URL Session Sync ---
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None and "session_token" in st.query_params:
    token_user = st.query_params["session_token"]
    res = supabase.table("app_users").select("*").eq("username", token_user).execute()
    if res.data and res.data[0]['is_approved']:
        st.session_state.user = res.data[0]

# --- 2. CONSTANTS, HELPERS & GLOBALS ---
MR_LIST = ["BBFC:U::", "BBFC:PG::", "BBFC:12::", "BBFC:15::", "BBFC:18::"]
OFFICIAL_RATING_LIST = ["Not Officially Rated", "BBFC:U::", "BBFC:PG::", "BBFC:12::", "BBFC:15::", "BBFC:18::"]
OP_STATUS_OPTIONS = ["In Progress", "Reviewed by Operator", "Pending Calibration", "Title Issue"]

# Full Mapping Including NO ISSUES
CD_CA_MAPPING = {
    "NO ISSUES": ["no material likely to offend or harm"],
    "VIOLENCE": ["VIOLENCE", "REFERENCES TO VIOLENCE", "BULLYING", "DOMESTIC ABUSE", "DOMESTIC ABUSE REFERENCES"],
    "INJURY DETAIL": ["INJURY DETAIL", "IMAGES OF REAL DEAD BODIES"],
    "THREAT": ["THREAT", "HORROR"],
    "SEXUAL VIOLENCE & SEXUAL THREAT": ["SEXUAL VIOLENCE", "SEXUAL VIOLENCE REFERENCES", "SEXUAL THREAT", "ABUSIVE BEHAVIOUR", "SEXUAL VIOLENCE THEME", "CHILD ABUSE", "CHILD ABUSE REFERENCES"],
    "DANGEROUS BEHAVIOUR": ["DANGEROUS BEHAVIOUR"],
    "SUICIDE & SELF-HARM": ["SUICIDE", "SUICIDE REFERENCES", "SUICIDE THEME", "SELF-HARM", "SELF-HARM THEME", "REFERENCES TO MENTAL HEALTH"],
    "SEX & NUDITY": ["SEX", "SEX REFERENCES", "NUDITY", "SEXUAL IMAGES", "C/RUDE HUMOUR"],
    "LANGUAGE": ["LANGUAGE", "RUDE GESTURES", "RACIAL LANGUAGE"],
    "DRUGS": ["DRUG MISUSE", "DRUG REFERENCES", "SMOKING", "ALCOHOL", "SUBSTANCE ABUSE"],
    "DISCRIMINATION": ["DISCRIMINATION", "DISCRIMINATION REFERENCES", "DISCRIMINATORY STEREOTYPES"],
    "ANIMALS HUNTING": ["ANIMALS HUNTING"],
    "TONE & IMPACT (THEMES)": ["UPSETTING SCENES", "DISTRESSING SCENES", "DISTURBING SCENES"]
}

# Unified List for Searchable Dropdown
UNIFIED_CA_LIST = [f"{cd}: {ca}" for cd, cas in CD_CA_MAPPING.items() for ca in cas]
ALL_CAS = list(dict.fromkeys([ca for cas in CD_CA_MAPPING.values() for ca in cas]))

def hash_pw(pw): return hashlib.sha256(str.encode(pw)).hexdigest()
def get_idx(val, opt_list):
    try: return opt_list.index(val)
    except: return 0

NOW_UTC = datetime.now(timezone.utc)
CURRENT_DATE_STR = NOW_UTC.strftime('%Y-%m-%d')
WEEK_NUM = NOW_UTC.isocalendar()[1]
DISPLAY_DATE = f"📅 {CURRENT_DATE_STR} | Week {WEEK_NUM}"

def append_date_week(df):
    if not df.empty:
        df['export_date'] = CURRENT_DATE_STR
        df['week_number'] = WEEK_NUM
    return df

# --- 3. GLOBAL ANALYTICS ---
def render_status_counters():
    res = supabase.table("titles").select("status").execute()
    issue_count = supabase.table("issue_bin").select("id", count="exact").execute().count or 0
    rated_count = supabase.table("officially_rated_titles").select("id", count="exact").execute().count or 0
    
    counts = {}
    calib_raised = 0
    if res.data:
        df = pd.DataFrame(res.data)
        counts = df['status'].value_counts()
        calib_raised = counts.get("Pending Calibration", 0)
        
    calib_answered = supabase.table("sme_logs").select("id", count="exact").gte("resolved_at", CURRENT_DATE_STR).execute().count or 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📝 In Progress", counts.get("In Progress", 0))
    c2.metric("✅ Finalized", counts.get("Finalized", 0))
    c3.metric("🚩 Issues / Rated", issue_count + rated_count)
    c4.metric("🔍 Calibrations Pending", calib_raised)
    c5.metric("✔️ Calibrations Answered", calib_answered)
    st.divider()

# --- 4. DATA ARCHIVAL (WRAP-UP) ---
def archive_finalized_titles():
    data = supabase.table("titles").select("*").eq("status", "Finalized").execute().data
    if data:
        archive_records = []
        for d in data:
            d.pop('id', None); d.pop('updated_at', None); d.pop('calibration_start', None); d.pop('sme_comments', None)
            d['week_number'] = WEEK_NUM 
            archive_records.append(d)
        supabase.table("historical_titles").insert(archive_records).execute()
        supabase.table("titles").delete().eq("status", "Finalized").execute()

def render_daily_wrapup():
    st.markdown("### 📊 Daily Wrap-Up & Export")
    res = supabase.table("titles").select("*").gte("updated_at", CURRENT_DATE_STR).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        st.write(f"Total titles touched today: **{len(df)}**")
        op_perf = df.groupby(['assigned_to', 'status'])['id'].count().reset_index()
        op_perf.columns = ['Operator', 'Status', 'Count']
        st.dataframe(op_perf, use_container_width=True)
        
        df_export = append_date_week(df)
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.info("⚠️ Downloading this report will archive 'Finalized' titles to the Historical Database.")
        st.download_button("📥 Export Wrap-Up & Archive Finalized Data", data=csv, file_name=f"wrapup_{CURRENT_DATE_STR}_W{WEEK_NUM}.csv", mime="text/csv", on_click=archive_finalized_titles)
    else:
        st.info("No data recorded for today yet.")

# --- 5. WORKFLOW MODULES ---
def render_operator(username):
    c_head, c_btn = st.columns([3, 1])
    c_head.subheader(f"📍 Operator Workspace | {username}")
    
    my_data = supabase.table("titles").select("*").eq("assigned_to", username).execute().data
    if my_data:
        df_op = append_date_week(pd.DataFrame(my_data))
        csv_op = df_op.to_csv(index=False).encode('utf-8')
        c_btn.download_button("📥 Download My Work", csv_op, f"work_{username}_{CURRENT_DATE_STR}.csv", "text/csv")

    existing_reqs = supabase.table("requests").select("*").eq("operator_email", username).execute().data
    pending_req = any(r['status'] == "Pending" for r in existing_reqs) if existing_reqs else False
    
    if last_req := sorted(existing_reqs, key=lambda x: x['created_at'], reverse=True) if existing_reqs else []:
        if last_req[0]['status'] == "Denied":
            st.warning(f"⚠️ **Notice:** {last_req[0].get('denial_reason', 'Request Denied.')}")

    if st.button("➕ Request Titles"):
        if pending_req:
            st.warning("You already have a pending request. Please wait for management approval.")
        elif not existing_reqs:
            un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(2).execute().data
            if un:
                for item in un:
                    supabase.table("titles").update({"assigned_to": username, "status": "In Progress"}).eq("id", item['id']).execute()
                supabase.table("requests").insert({"operator_email": username, "status": "Fulfilled"}).execute()
                st.success("First request auto-approved! 2 titles assigned.")
                st.rerun()
            else:
                st.error("No unassigned titles available.")
        else:
            supabase.table("requests").insert({"operator_email": username, "status": "Pending"}).execute()
            st.info("Request sent to Management.")
            st.rerun()

    tasks = supabase.table("titles").select("*").eq("assigned_to", username).execute().data
    if not tasks: st.info("No titles assigned.")
    
    for t in tasks or []:
        locked = t['status'] in ["Reviewed by Operator", "Pending Calibration", "Finalized"]
        display_title = t.get('title_name') if t.get('title_name') else "Pending EDP Lookup"
        
        with st.expander(f"📖 {t['gti']} - {display_title} | Current: {t['status']}"):
            if t.get('sme_comments'): st.error(f"**SME Feedback:** {t['sme_comments']}")
            
            with st.container(border=True):
                st.markdown("##### 1. Asset Identification")
                id_c1, id_c2, id_c3, id_c4 = st.columns([1, 2, 1, 1])
                id_c1.code(t['gti'], language=None)
                t_name = id_c2.text_input("Title Name (EDP)", value=t.get('title_name', ''), key=f"tn_{t['id']}", disabled=locked)
                edp_url = id_c3.text_input("EDP Link", value=t.get('edp_link', ''), key=f"el_{t['id']}", disabled=locked)
                
                a_type_idx = 1 if t.get('asset_type') == 'Episode' else 0
                a_type = id_c4.radio("Asset Type", ["Movie", "Episode"], index=a_type_idx, horizontal=True, key=f"at_{t['id']}", disabled=locked)
                amz_orig = id_c4.radio("Amazon Original?", ["No", "Yes"], index=1 if t.get('amazon_original') == 'Yes' else 0, horizontal=True, key=f"ao_{t['id']}", disabled=locked)

            with st.container(border=True):
                st.markdown("##### 2. Classification Status")
                c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                run_t = c1.text_input("Runtime", value=t.get('runtime', ''), placeholder="e.g. 1h 45m", key=f"rt_{t['id']}", disabled=locked)
                off_rtg = c2.selectbox("Official Rating", OFFICIAL_RATING_LIST, index=get_idx(t.get('official_rating', 'Not Officially Rated'), OFFICIAL_RATING_LIST), key=f"or_{t['id']}", disabled=locked)
                is_off = off_rtg != "Not Officially Rated"
                mr = c3.selectbox("MR Rating", MR_LIST, index=get_idx(t['mr_rating'], MR_LIST), key=f"mr_{t['id']}", disabled=locked or is_off)
                stat = c4.selectbox("Actionable Status", OP_STATUS_OPTIONS, index=get_idx(t['status'], OP_STATUS_OPTIONS), key=f"st_{t['id']}", disabled=locked or is_off)

                off_rtg_date = None
                if is_off and not locked:
                    st.info("📌 **Title is Officially Rated.** Please provide the rating date.")
                    off_rtg_date = st.date_input("Official Rating Date", key=f"ord_{t['id']}")

                st.markdown("###### Content Advice (Searchable)")
                saved_cds = t.get('cd_values') or []
                defaults = [opt for opt in UNIFIED_CA_LIST if opt.split(": ", 1)[1] in saved_cds]
                
                selected_full = st.multiselect(
                    "Search or select categories and advice", 
                    options=UNIFIED_CA_LIST, 
                    default=defaults, 
                    key=f"uni_{t['id']}", 
                    disabled=locked
                )
                clean_cds = [item.split(": ", 1)[1] for item in selected_full]

                calib_cd_val, calib_mr_val = None, None
                if stat == "Pending Calibration" and not locked and not is_off:
                    st.warning("Please specify Calibration details:")
                    cc1, cc2 = st.columns(2)
                    calib_cd_val = cc1.selectbox("Calibrating Content Advice", ALL_CAS, key=f"ccd_{t['id']}")
                    calib_mr_val = cc2.selectbox("Proposed MR", MR_LIST, key=f"cmr_{t['id']}")
                else:
                    calib_cd_val = t.get('calib_cd'); calib_mr_val = t.get('calib_mr')
            
            with st.container(border=True):
                st.markdown("##### 3. Analysis & Notes")
                d_c1, d_c2 = st.columns(2)
                p_drive = d_c1.text_area("🚀 Primary Drivers", value=t.get('primary_drivers', ''), key=f"p_{t['id']}", disabled=locked)
                s_drive = d_c2.text_area("🔍 Secondary Drivers", value=t.get('secondary_drivers', ''), key=f"s_{t['id']}", disabled=locked)
                n_c1, n_c2 = st.columns(2)
                ndi_txt = n_c1.text_area("🛡️ Non-Defining Issues", value=t.get('ndi_text', ''), key=f"ndi_{t['id']}", disabled=locked)
                ops_comm = n_c2.text_area("💬 Ops Comments", value=t.get('ops_comments', ''), key=f"oc_{t['id']}", disabled=locked)

            if st.button("Save & Submit Asset", type="primary", key=f"save_{t['id']}"):
                if is_off:
                    record = {
                        "gti": t['gti'], "title_name": t_name, "edp_link": edp_url,
                        "asset_type": a_type, "amazon_original": amz_orig,
                        "runtime": run_t, "official_rating": off_rtg, 
                        "official_rating_date": off_rtg_date.isoformat() if off_rtg_date else None,
                        "mr_rating": mr, "cd_values": clean_cds,
                        "primary_drivers": p_drive, "secondary_drivers": s_drive,
                        "ndi_text": ndi_txt, "ops_comments": ops_comm, "flagged_by": username
                    }
                    supabase.table("officially_rated_titles").insert(record).execute()
                    supabase.table("titles").delete().eq("id", t['id']).execute()
                    
                    un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(1).execute().data
                    if un:
                        supabase.table("titles").update({"assigned_to": username, "status": "In Progress"}).eq("id", un[0]['id']).execute()
                        st.success("Officially Rated Title logged. 1 new title automatically assigned.")
                    else: st.warning("Officially Rated Title logged. No replacements available.")
                        
                elif stat == "Title Issue":
                    supabase.table("issue_bin").insert({"gti": t['gti'], "title_name": t_name, "flagged_by": username, "issue_details": p_drive}).execute()
                    supabase.table("titles").delete().eq("id", t['id']).execute()
                    
                    un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(1).execute().data
                    if un:
                        supabase.table("titles").update({"assigned_to": username, "status": "In Progress"}).eq("id", un[0]['id']).execute()
                        st.success("Issue Submitted. 1 new title automatically assigned.")
                    else: st.warning("Issue Submitted. No replacements available.")
                else:
                    upd = {
                        "title_name": t_name, "edp_link": edp_url, "asset_type": a_type, "amazon_original": amz_orig,
                        "runtime": run_t, "official_rating": off_rtg, "mr_rating": mr, "cd_values": clean_cds, 
                        "status": stat, "primary_drivers": p_drive, "secondary_drivers": s_drive, 
                        "ndi_text": ndi_txt, "ops_comments": ops_comm, "updated_at": NOW_UTC.isoformat()
                    }
                    if stat == "Pending Calibration":
                        upd["calibration_start"] = NOW_UTC.isoformat()
                        upd["calib_cd"] = calib_cd_val
                        upd["calib_mr"] = calib_mr_val
                    supabase.table("titles").update(upd).eq("id", t['id']).execute()
                st.rerun()

def render_sme(username):
    st.subheader("🔍 SME Calibration Dashboard")
    
    pending = supabase.table("titles").select("*").eq("status", "Pending Calibration").execute().data
    my_logs = supabase.table("sme_logs").select("*").eq("sme_username", username).gte("resolved_at", CURRENT_DATE_STR).execute().data
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Titles in Calibration", len(pending) if pending else 0)
    col2.metric("Calibrations Resolved Today", len(my_logs) if my_logs else 0)
    
    if my_logs:
        df_sme = append_date_week(pd.DataFrame(my_logs))
        csv_sme = df_sme.to_csv(index=False).encode('utf-8')
        col3.download_button("📥 Download My Daily Log", csv_sme, f"sme_log_{CURRENT_DATE_STR}_W{WEEK_NUM}.csv", "text/csv")

    st.divider()

    for p in pending or []:
        calib_start = p.get('calibration_start')
        time_passed = "Unknown"; time_mins = 0
        if calib_start:
            start_dt = datetime.fromisoformat(calib_start.replace('Z', '+00:00'))
            diff = NOW_UTC - start_dt
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
                    "gti": p['gti'], "sme_username": username, "calib_cd": p.get('calib_cd'),
                    "calib_mr": p.get('calib_mr'), "ops_comments": p.get('ops_comments'),
                    "sme_comments": feedback, "time_taken_minutes": round(time_mins, 2)
                }
                supabase.table("sme_logs").insert(log_entry).execute()
                supabase.table("titles").update({"status": "In Progress", "sme_comments": feedback}).eq("id", p['id']).execute()
                st.rerun()

def render_mgmt(role):
    render_status_counters()
    t_db, t_up, t_req, t_alloc, t_wrap, t_hist, t_bin = st.tabs(["📁 Active DB", "⬆️ Upload", "📥 Requests", "📦 Allocation", "📊 Wrap-Up", "🗄️ Historical", "🚩 Issues & Rated"])
    
    with t_db:
        search = st.text_input("🔍 Search Database (GTI/Name)")
        q = supabase.table("titles").select("*")
        if search: q = q.or_(f"gti.ilike.%{search}%,title_name.ilike.%{search}%")
        data = q.execute().data
        if data: st.dataframe(pd.DataFrame(data)[['gti', 'title_name', 'asset_type', 'assigned_to', 'status']])

    with t_up:
        st.info("Upload CSV containing the header: `gti`")
        uploaded_file = st.file_uploader("Select CSV", type=["csv"])
        if uploaded_file and st.button("Upload to Pool"):
            df = pd.read_csv(uploaded_file)
            if 'gti' in df.columns:
                records = [{"gti": str(row['gti']), "status": "Unassigned"} for _, row in df.iterrows()]
                supabase.table("titles").insert(records).execute()
                st.success(f"Added {len(records)} GTIs to Unassigned pool.")
            else: st.error("CSV must contain 'gti' column.")

    with t_req:
        reqs = supabase.table("requests").select("*").eq("status", "Pending").execute().data
        for r in reqs or []:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                c1.write(f"**{r['operator_email']}** requests work.")
                if c2.button("Approve (+2)", key=f"q_{r['id']}"):
                    un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(2).execute().data
                    for item in un: supabase.table("titles").update({"assigned_to": r['operator_email'], "status": "In Progress"}).eq("id", item['id']).execute()
                    supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r['id']).execute()
                    st.rerun()
                qty = c3.number_input("Custom Qty", 1, 20, 5, key=f"qty_{r['id']}")
                if c4.button("Assign", key=f"c_{r['id']}"):
                    un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(qty).execute().data
                    for item in un: supabase.table("titles").update({"assigned_to": r['operator_email'], "status": "In Progress"}).eq("id", item['id']).execute()
                    supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r['id']).execute()
                    st.rerun()
                d_reason = st.text_input("Denial Reason", "Please focus on your current queue.", key=f"dr_{r['id']}")
                if st.button("🚫 Deny Request", key=f"d_{r['id']}"):
                    supabase.table("requests").update({"status": "Denied", "denial_reason": d_reason}).eq("id", r['id']).execute()
                    st.rerun()

    with t_alloc:
        ops = [o['username'] for o in supabase.table("app_users").select("username").eq("role", "Operator").execute().data]
        st.markdown("#### 🔄 Bulk Operator Allocation")
        sel_ops = st.multiselect("Select Operators", ops)
        b_qty = st.number_input("Batch Size per Operator", 1, 50, 5)
        if st.button("Distribute Titles"):
            for o in sel_ops:
                un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(b_qty).execute().data
                for item in un: supabase.table("titles").update({"assigned_to": o, "status": "In Progress"}).eq("id", item['id']).execute()
            st.success("Bulk Distribution Complete.")

        st.divider()
        st.markdown("#### 🎯 Targeted GTI Assignment")
        col_a, col_b, col_c = st.columns([2, 2, 1])
        t_gti = col_a.text_input("Specific GTI ID")
        t_op = col_b.selectbox("Assign to Operator", ops, key="target_op")
        if col_c.button("Assign Specific"):
            supabase.table("titles").update({"assigned_to": t_op, "status": "In Progress"}).eq("gti", t_gti).execute()
            st.success(f"GTI {t_gti} assigned to {t_op}.")

    with t_wrap: render_daily_wrapup()

    with t_hist:
        st.markdown("### 🗄️ Historical Archive Explorer")
        st.info("Filter historically finalized titles by Date Range.")
        
        # FEATURE: Date Range Download
        date_range = st.date_input("Select Export Date Range", [])
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            q = supabase.table("historical_titles").select("*").gte("export_date", start_date.strftime('%Y-%m-%d')).lte("export_date", end_date.strftime('%Y-%m-%d'))
            hist_data = q.execute().data
            
            if hist_data:
                df_hist = append_date_week(pd.DataFrame(hist_data))
                st.write(f"Found **{len(df_hist)}** records.")
                st.dataframe(df_hist)
                csv_hist = df_hist.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Filtered Archive", csv_hist, f"historical_data_{start_date}_to_{end_date}.csv", "text/csv")
            else:
                st.warning("No records found in this date range.")
        else:
            st.write("Please select both a start and end date to view records.")

    with t_bin:
        st.markdown("### 🚩 Title Issues")
        issues = supabase.table("issue_bin").select("*").execute().data
        if issues: 
            df_iss = append_date_week(pd.DataFrame(issues))
            st.dataframe(df_iss)
            csv_iss = df_iss.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Issue Bin", csv_iss, f"issue_bin_W{WEEK_NUM}.csv", "text/csv")
        else: st.info("No issues currently flagged.")
        
        st.divider()
        st.markdown("### 📌 Officially Rated Titles")
        off_rated = supabase.table("officially_rated_titles").select("*").execute().data
        if off_rated:
            df_off = append_date_week(pd.DataFrame(off_rated))
            st.dataframe(df_off)
            csv_off = df_off.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Rated Titles", csv_off, f"officially_rated_W{WEEK_NUM}.csv", "text/csv")
        else: st.info("No officially rated titles logged yet.")

# --- 6. AUTHENTICATION & ROUTING ---
if st.session_state.user is None:
    st.title("🛡️ The Terran")
    tab_l, tab_a, tab_s = st.tabs(["👤 Login", "🔑 Admin Portal", "📝 Signup"])
    
    with tab_l:
        u_in, p_in = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Log In"):
            res = supabase.table("app_users").select("*").eq("username", u_in).execute()
            if res.data and res.data[0]['password'] == hash_pw(p_in):
                if res.data[0]['is_approved']: 
                    st.session_state.user = res.data[0]
                    st.query_params["session_token"] = u_in
                    st.rerun()
                else: st.warning("Account pending Admin approval.")
            else: st.error("Invalid Credentials.")
            
    with tab_a:
        a_pw = st.text_input("Master Key", type="password")
        if st.button("Authorize"):
            res = supabase.table("app_users").select("*").eq("username", "Admin").execute()
            if res.data and (a_pw == res.data[0]['password'] or hash_pw(a_pw) == res.data[0]['password']):
                st.session_state.user = res.data[0]
                st.query_params["session_token"] = "Admin"
                st.rerun()
            else: st.error("Master Key Invalid.")
            
    with tab_s:
        s_u, s_p = st.text_input("New Username"), st.text_input("New Password", type="password")
        s_r = st.selectbox("Role", ["Operator", "SME", "Manager", "Allocator"])
        if st.button("Sign Up"):
            is_app = (s_r == "Operator")
            supabase.table("app_users").insert({"username": s_u, "password": hash_pw(s_p), "role": s_r, "is_approved": is_app}).execute()
            st.success("Account created!" if is_app else "Account created. Awaiting Admin approval.")

else:
    u = st.session_state.user
    
    st.sidebar.subheader(f"👋 {u['username']}")
    st.sidebar.caption(f"Role: **{u['role']}**")
    st.sidebar.info(DISPLAY_DATE)
    
    if st.sidebar.button("Logout"): 
        st.session_state.user = None
        if "session_token" in st.query_params:
            del st.query_params["session_token"] 
        st.rerun()

    if u['role'] == "Admin":
        at1, at2, at3, at4 = st.tabs(["⚙️ Roster & Security", "📝 Operator View", "🔍 SME View", "📊 Mgmt View"])
        with at1:
            users = supabase.table("app_users").select("*").execute().data
            st.markdown("### User Approvals & Passwords")
            for user in users or []:
                if user['username'] != "Admin":
                    with st.container(border=True):
                        c1, c2, c3, c4, c5 = st.columns([2, 1, 2, 1, 1])
                        c1.write(f"**{user['username']}** ({user['role']})")
                        if not user['is_approved'] and c2.button("Approve", key=f"app_{user['username']}"):
                            supabase.table("app_users").update({"is_approved": True}).eq("username", user['username']).execute(); st.rerun()
                        new_pw = c3.text_input("New PW", type="password", key=f"pw_{user['username']}")
                        if c4.button("Reset", key=f"rst_{user['username']}"):
                            supabase.table("app_users").update({"password": hash_pw(new_pw)}).eq("username", user['username']).execute()
                            st.success("Reset")
                        if c5.button("Delete", type="primary", key=f"del_{user['username']}"):
                            supabase.table("app_users").delete().eq("username", user['username']).execute()
                            st.rerun()
        with at2: render_operator(u['username'])
        with at3: render_sme(u['username'])
        with at4: render_mgmt("Admin")
        
    elif u['role'] in ["Manager", "Allocator"]: render_mgmt(u['role'])
    elif u['role'] == "SME": render_sme(u['username'])
    elif u['role'] == "Operator": render_operator(u['username'])