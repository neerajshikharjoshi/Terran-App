import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone
import pandas as pd
import hashlib

# --- 1. CONFIGURATION & PERSISTENCE ---
st.set_page_config(page_title="The Terran | Content Ops", layout="wide")

if 'user' not in st.session_state:
    st.session_state.user = None

url = st.secrets.get("SUPABASE_URL")
key = st.secrets.get("SUPABASE_KEY")

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Database Connection Failed. Check Streamlit Secrets.")
    st.stop()

# --- 2. CONSTANTS & HELPERS ---
MR_LIST = ["BBFC:U::", "BBFC:PG::", "BBFC:12::", "BBFC:15::", "BBFC:18::"]
CD_LIST = ["Violence", "Threat", "Language", "Nudity", "Sex", "Drugs", "Horror", "Discrimination"]
OP_STATUS_OPTIONS = ["In Progress", "Reviewed by Operator", "Pending Calibration", "Title Issue"]

def hash_pw(pw): return hashlib.sha256(str.encode(pw)).hexdigest()
def get_idx(val, opt_list):
    try: return opt_list.index(val)
    except: return 0

# --- 3. ANALYTICS & WRAP-UP ---
def render_status_counters():
    res = supabase.table("titles").select("status").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        counts = df['status'].value_counts()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📝 In Progress", counts.get("In Progress", 0))
        c2.metric("🔍 Pending Calib", counts.get("Pending Calibration", 0))
        c3.metric("✅ Finalized", counts.get("Finalized", 0))
        c4.metric("🚩 Issues", counts.get("Title Issue", 0))
        st.divider()

def purge_finalized_titles():
    supabase.table("titles").delete().eq("status", "Finalized").execute()

def render_daily_wrapup():
    st.markdown("### 📊 Daily Wrap-Up & Export")
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    res = supabase.table("titles").select("*").gte("updated_at", today).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        st.write(f"Total titles touched today: **{len(df)}**")
        op_perf = df.groupby(['assigned_to', 'status'])['id'].count().reset_index()
        op_perf.columns = ['Operator', 'Status', 'Count']
        st.dataframe(op_perf, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.info("⚠️ Downloading this report will permanently purge all 'Finalized' titles from the database.")
        st.download_button(
            label="📥 Export Wrap-Up & Purge Finalized",
            data=csv, file_name=f"wrapup_{today}.csv", mime="text/csv", on_click=purge_finalized_titles
        )
    else:
        st.info("No data recorded for today yet.")

# --- 4. WORKFLOW MODULES ---

def render_operator(username):
    st.subheader(f"📍 Operator Workspace | {username}")
    
    # Check for denied requests
    last_req = supabase.table("requests").select("*").eq("operator_email", username).order("created_at", desc=True).limit(1).execute()
    if last_req.data and last_req.data[0]['status'] == "Denied":
        st.warning(f"⚠️ **Notice from Allocator:** {last_req.data[0].get('denial_reason', 'Request Denied.')}")

    if st.button("➕ Request Titles"):
        supabase.table("requests").insert({"operator_email": username, "status": "Pending"}).execute()
        st.info("Request sent to Management.")

    tasks = supabase.table("titles").select("*").eq("assigned_to", username).execute().data
    if not tasks: st.info("No titles assigned.")
    
    for t in tasks or []:
        locked = t['status'] in ["Reviewed by Operator", "Pending Calibration", "Finalized"]
        display_title = t.get('title_name') if t.get('title_name') else "Pending EDP Lookup"
        
        with st.expander(f"📖 {t['gti']} - {display_title} | Current: {t['status']}"):
            if t.get('sme_comments'): st.error(f"**SME Feedback:** {t['sme_comments']}")
            
            # --- UI ZONE 1: Asset Identification ---
            with st.container(border=True):
                st.markdown("##### 1. Asset Identification")
                id_c1, id_c2, id_c3 = st.columns([1, 2, 1])
                id_c1.caption("Click the icon to copy GTI:")
                id_c1.code(t['gti'], language=None) # Native Streamlit Copy Button
                t_name = id_c2.text_input("Title Name (EDP Lookup)", value=t.get('title_name', ''), key=f"tn_{t['id']}", disabled=locked)
                
                # Default to Movie if not set
                a_type_idx = 1 if t.get('asset_type') == 'Episode' else 0
                a_type = id_c3.radio("Asset Type", ["Movie", "Episode"], index=a_type_idx, horizontal=True, key=f"at_{t['id']}", disabled=locked)

            # --- UI ZONE 2: Classification ---
            with st.container(border=True):
                st.markdown("##### 2. Classification Status")
                c1, c2, c3 = st.columns(3)
                mr = c1.selectbox("MR Rating", MR_LIST, index=get_idx(t['mr_rating'], MR_LIST), key=f"mr_{t['id']}", disabled=locked)
                cds = c2.multiselect("Content Descriptors", CD_LIST, default=t.get('cd_values', []), key=f"cd_{t['id']}", disabled=locked)
                stat = c3.selectbox("Actionable Status", OP_STATUS_OPTIONS, index=get_idx(t['status'], OP_STATUS_OPTIONS), key=f"st_{t['id']}")
            
            # --- UI ZONE 3: Analysis & Drivers ---
            with st.container(border=True):
                st.markdown("##### 3. Analysis & Notes")
                d_c1, d_c2 = st.columns(2)
                p_drive = d_c1.text_area("🚀 Primary Drivers", value=t.get('primary_drivers', ''), key=f"p_{t['id']}", disabled=locked)
                s_drive = d_c2.text_area("🔍 Secondary Drivers", value=t.get('secondary_drivers', ''), key=f"s_{t['id']}", disabled=locked)
                
                n_c1, n_c2 = st.columns(2)
                ndi_txt = n_c1.text_area("🛡️ Non-Defining Issues (NDI)", value=t.get('ndi_text', ''), key=f"ndi_{t['id']}", disabled=locked)
                ops_comm = n_c2.text_area("💬 Ops Comments", value=t.get('ops_comments', ''), key=f"oc_{t['id']}", disabled=locked)

            if st.button("Save & Submit Asset", type="primary", key=f"save_{t['id']}"):
                if stat == "Title Issue":
                    supabase.table("issue_bin").insert({"gti": t['gti'], "title_name": t_name, "flagged_by": username, "issue_details": p_drive}).execute()
                    supabase.table("titles").delete().eq("id", t['id']).execute()
                else:
                    upd = {
                        "title_name": t_name, "asset_type": a_type, "mr_rating": mr, "cd_values": cds, 
                        "status": stat, "primary_drivers": p_drive, "secondary_drivers": s_drive, 
                        "ndi_text": ndi_txt, "ops_comments": ops_comm, "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    if stat == "Pending Calibration": upd["calibration_start"] = datetime.now(timezone.utc).isoformat()
                    supabase.table("titles").update(upd).eq("id", t['id']).execute()
                st.rerun()

def render_sme():
    st.subheader("🔍 SME Calibration")
    pending = supabase.table("titles").select("*").eq("status", "Pending Calibration").execute().data
    for p in pending or []:
        with st.expander(f"📋 {p['gti']} - {p.get('title_name', 'Unknown')} | Ops: {p['assigned_to']}"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Asset:** {p.get('asset_type')}")
            c2.write(f"**Primary Drivers:** {p.get('primary_drivers')}")
            c3.write(f"**NDI:** {p.get('ndi_text')}")
            
            st.info(f"**Ops Comments:** {p.get('ops_comments')}")
            
            feedback = st.text_area("SME Feedback", key=f"fb_{p['id']}")
            b1, b2 = st.columns(2)
            if b1.button("✅ Approve", key=f"ap_{p['id']}"):
                supabase.table("titles").update({"status": "Finalized", "sme_comments": feedback}).eq("id", p['id']).execute()
                st.rerun()
            if b2.button("⏪ Return to Op", key=f"re_{p['id']}"):
                supabase.table("titles").update({"status": "In Progress", "sme_comments": feedback}).eq("id", p['id']).execute()
                st.rerun()

def render_mgmt(role):
    render_status_counters()
    t_db, t_up, t_req, t_alloc, t_wrap, t_bin = st.tabs(["📁 Database", "⬆️ Upload CSV", "📥 Requests", "📦 Allocation", "📊 Wrap-Up", "🚩 Issue Bin"])
    
    with t_db:
        search = st.text_input("🔍 Search Database (GTI/Name)")
        q = supabase.table("titles").select("*")
        if search: q = q.or_(f"gti.ilike.%{search}%,title_name.ilike.%{search}%")
        data = q.execute().data
        if data: st.dataframe(pd.DataFrame(data)[['gti', 'title_name', 'asset_type', 'assigned_to', 'status']])

    with t_up:
        st.markdown("### ⬆️ Ingest New Titles")
        st.info("**Instructions:** Upload a CSV file. It must contain the header: `gti` (Other columns will be ignored).")
        uploaded_file = st.file_uploader("Select CSV", type=["csv"])
        if uploaded_file and st.button("Upload to Pool"):
            df = pd.read_csv(uploaded_file)
            if 'gti' in df.columns:
                records = [{"gti": str(row['gti']), "status": "Unassigned"} for _, row in df.iterrows()]
                supabase.table("titles").insert(records).execute()
                st.success(f"Successfully added {len(records)} GTIs to the Unassigned pool.")
            else:
                st.error("CSV format invalid. Ensure it contains a column named 'gti'.")

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
                
                d_reason = st.text_input("Denial Reason", "Don't overwork yourself! Focus on your current queue.", key=f"dr_{r['id']}")
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
        t_op = col_b.selectbox("Assign to", ops)
        if col_c.button("Assign Specifc"):
            supabase.table("titles").update({"assigned_to": t_op, "status": "In Progress"}).eq("gti", t_gti).execute()
            st.success("Targeted Assignment Complete.")

    with t_wrap: render_daily_wrapup()

    with t_bin:
        issues = supabase.table("issue_bin").select("*").execute().data
        if issues: st.dataframe(pd.DataFrame(issues))

# --- 5. AUTHENTICATION & ROUTING ---
if st.session_state.user is None:
    st.title("🛡️ The Terran")
    tab_l, tab_a, tab_s = st.tabs(["👤 Login", "🔑 Admin Portal", "📝 Signup"])
    
    with tab_l:
        u_in, p_in = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Log In"):
            res = supabase.table("app_users").select("*").eq("username", u_in).execute()
            if res.data and res.data[0]['password'] == hash_pw(p_in):
                if res.data[0]['is_approved']: st.session_state.user = res.data[0]; st.rerun()
                else: st.warning("Account pending Admin approval.")
            else: st.error("Invalid Credentials.")
            
    with tab_a:
        a_pw = st.text_input("Master Key", type="password")
        if st.button("Authorize"):
            res = supabase.table("app_users").select("*").eq("username", "Admin").execute()
            if res.data and (a_pw == res.data[0]['password'] or hash_pw(a_pw) == res.data[0]['password']):
                st.session_state.user = res.data[0]; st.rerun()
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
    st.sidebar.subheader(f"{u['username']}")
    st.sidebar.write(f"Role: {u['role']}")
    if st.sidebar.button("Logout"): st.session_state.user = None; st.rerun()

    if u['role'] == "Admin":
        at1, at2, at3, at4 = st.tabs(["⚙️ Roster & Security", "📝 Operator View", "🔍 SME View", "📊 Mgmt View"])
        with at1:
            users = supabase.table("app_users").select("*").execute().data
            st.markdown("### User Approvals & Passwords")
            for user in users or []:
                if user['username'] != "Admin":
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
                        c1.write(f"**{user['username']}** ({user['role']})")
                        if not user['is_approved'] and c2.button("Approve", key=f"app_{user['username']}"):
                            supabase.table("app_users").update({"is_approved": True}).eq("username", user['username']).execute(); st.rerun()
                        new_pw = c3.text_input("New PW", type="password", key=f"pw_{user['username']}")
                        if c4.button("Reset", key=f"rst_{user['username']}"):
                            supabase.table("app_users").update({"password": hash_pw(new_pw)}).eq("username", user['username']).execute()
                            st.success("Reset")
        with at2: render_operator(u['username'])
        with at3: render_sme()
        with at4: render_mgmt("Admin")
        
    elif u['role'] in ["Manager", "Allocator"]: render_mgmt(u['role'])
    elif u['role'] == "SME": render_sme()
    elif u['role'] == "Operator": render_operator(u['username'])