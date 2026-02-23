import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone
import pandas as pd
import hashlib

# --- 1. CONFIGURATION & DATABASE CONNECTION ---
st.set_page_config(page_title="The Terran | Content Ops", layout="wide")

# Persistent Session Initialization
if 'user' not in st.session_state:
    st.session_state.user = None

url = st.secrets.get("SUPABASE_URL")
key = st.secrets.get("SUPABASE_KEY")

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Connection Failed. Check Streamlit Secrets.")
    st.stop()

# --- 2. CONSTANTS & HELPERS ---
MR_LIST = ["BBFC:U::", "BBFC:PG::", "BBFC:12::", "BBFC:15::", "BBFC:18::"]
CD_LIST = ["Violence", "Threat", "Language", "Nudity", "Sex", "Drugs", "Horror", "Discrimination"]
OP_STATUS_OPTIONS = ["In Progress", "Reviewed by Operator", "Pending Calibration", "Title Issue"]

def hash_pw(pw): return hashlib.sha256(str.encode(pw)).hexdigest()

def get_idx(val, opt_list):
    try: return opt_list.index(val)
    except: return 0

# --- 3. ANALYTICS COMPONENT ---
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

# --- 4. WORKFLOW MODULES ---

def render_operator(username):
    st.subheader(f"📍 Operator Workspace | {username}")
    
    # Request System
    if st.button("➕ Request Titles"):
        supabase.table("requests").insert({"operator_email": username, "status": "Pending"}).execute()
        st.info("Request for titles sent to Management.")

    tasks = supabase.table("titles").select("*").eq("assigned_to", username).execute().data
    if not tasks: st.info("No titles currently assigned.")
    
    for t in tasks or []:
        # Status Sync Fix
        locked = t['status'] in ["Reviewed by Operator", "Pending Calibration", "Finalized"]
        with st.expander(f"📖 {t['gti']} - {t['title_name']} | Current: {t['status']}"):
            if t.get('sme_comments'): st.error(f"**SME Feedback:** {t['sme_comments']}")
            
            c1, c2, c3 = st.columns(3)
            mr = c1.selectbox("MR Rating", MR_LIST, index=get_idx(t['mr_rating'], MR_LIST), key=f"mr_{t['id']}", disabled=locked)
            cds = c2.multiselect("Content Descriptors", CD_LIST, default=t.get('cd_values', []), key=f"cd_{t['id']}", disabled=locked)
            stat = c3.selectbox("Actionable Status", OP_STATUS_OPTIONS, index=get_idx(t['status'], OP_STATUS_OPTIONS), key=f"st_{t['id']}")
            
            # Separated Drivers & Comments
            st.divider()
            col_d1, col_d2 = st.columns(2)
            p_drive = col_d1.text_area("🚀 Primary Drivers", value=t.get('primary_drivers', ''), key=f"p_{t['id']}", disabled=locked)
            s_drive = col_d2.text_area("🔍 Secondary Drivers", value=t.get('secondary_drivers', ''), key=f"s_{t['id']}", disabled=locked)
            ops_comm = st.text_area("💬 Ops Comments", value=t.get('context_ndi', ''), key=f"c_{t['id']}", disabled=locked)

            if st.button("Save & Submit Changes", key=f"save_{t['id']}"):
                if stat == "Title Issue":
                    supabase.table("issue_bin").insert({"gti": t['gti'], "title_name": t['title_name'], "flagged_by": username, "issue_details": p_drive}).execute()
                    supabase.table("titles").delete().eq("id", t['id']).execute()
                else:
                    upd = {
                        "mr_rating": mr, "cd_values": cds, "status": stat, "primary_drivers": p_drive, 
                        "secondary_drivers": s_drive, "context_ndi": ops_comm, "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    if stat == "Pending Calibration": upd["calibration_start"] = datetime.now(timezone.utc).isoformat()
                    supabase.table("titles").update(upd).eq("id", t['id']).execute()
                st.rerun()

def render_sme():
    st.subheader("🔍 SME Calibration Queue")
    pending = supabase.table("titles").select("*").eq("status", "Pending Calibration").execute().data
    for p in pending or []:
        with st.expander(f"📋 {p['gti']} | Ops: {p['assigned_to']}"):
            st.write(f"**Primary Drivers:** {p.get('primary_drivers')}")
            st.write(f"**Ops Comments:** {p.get('context_ndi')}")
            feedback = st.text_area("SME Feedback", key=f"fb_{p['id']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve", key=f"ap_{p['id']}"):
                supabase.table("titles").update({"status": "Finalized", "sme_comments": feedback}).eq("id", p['id']).execute()
                st.rerun()
            if c2.button("⏪ Return to Op", key=f"re_{p['id']}"):
                supabase.table("titles").update({"status": "In Progress", "sme_comments": feedback}).eq("id", p['id']).execute()
                st.rerun()

def render_mgmt(role):
    render_status_counters()
    t_db, t_req, t_alloc, t_users, t_bin = st.tabs(["📁 Database", "📥 Requests", "📦 Allocator", "👤 Users", "🚩 Issue Bin"])
    
    with t_db:
        search = st.text_input("🔍 Search GTI/Title")
        query = supabase.table("titles").select("*")
        if search: query = query.or_(f"gti.ilike.%{search}%,title_name.ilike.%{search}%")
        all_t = query.execute().data
        if all_t: st.dataframe(pd.DataFrame(all_t)[['gti', 'title_name', 'assigned_to', 'status']])

    with t_req:
        # Dual-Action Fulfillment
        reqs = supabase.table("requests").select("*").eq("status", "Pending").execute().data
        for r in reqs or []:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                c1.write(f"**{r['operator_email']}**")
                if c2.button("Approve (+2)", key=f"q_{r['id']}"):
                    un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(2).execute().data
                    for item in un: supabase.table("titles").update({"assigned_to": r['operator_email'], "status": "In Progress"}).eq("id", item['id']).execute()
                    supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r['id']).execute()
                    st.rerun()
                qty = c3.number_input("Qty", 1, 20, 5, key=f"qty_{r['id']}")
                if c4.button("Assign Custom", key=f"c_{r['id']}"):
                    un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(qty).execute().data
                    for item in un: supabase.table("titles").update({"assigned_to": r['operator_email'], "status": "In Progress"}).eq("id", item['id']).execute()
                    supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r['id']).execute()
                    st.rerun()

    with t_alloc:
        # Bulk and Targeted Allocation logic restored
        ops = [o['username'] for o in supabase.table("app_users").select("username").eq("role", "Operator").execute().data]
        st.markdown("#### 🔄 Bulk Allocation")
        sel_ops = st.multiselect("Operators", ops)
        b_qty = st.number_input("Batch Size", 1, 50, 5)
        if st.button("Distribute"):
            for o in sel_ops:
                un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(b_qty).execute().data
                for item in un: supabase.table("titles").update({"assigned_to": o, "status": "In Progress"}).eq("id", item['id']).execute()
            st.success("Distributed.")
        
        st.divider()
        st.markdown("#### 🎯 Targeted GTI")
        col_a, col_b, col_c = st.columns([2, 2, 1])
        t_gti = col_a.text_input("GTI ID")
        t_op = col_b.selectbox("To Operator", ops)
        if col_c.button("Assign Specific"):
            supabase.table("titles").update({"assigned_to": t_op, "status": "In Progress"}).eq("gti", t_gti).execute()
            st.success("Targeted Assignment Complete.")

    with t_users:
        st.write("### Password Management")
        users = supabase.table("app_users").select("*").execute().data
        for u in users or []:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{u['username']}** ({u['role']})")
                new_p = c2.text_input("Update Password", type="password", key=f"upw_{u['username']}")
                if c3.button("Reset", key=f"ubtn_{u['username']}"):
                    supabase.table("app_users").update({"password": hash_pw(new_p)}).eq("username", u['username']).execute()
                    st.success(f"Updated {u['username']}")

    with t_bin:
        issues = supabase.table("issue_bin").select("*").execute().data
        if issues: st.dataframe(pd.DataFrame(issues))

# --- 5. AUTHENTICATION & ROUTING ---
if st.session_state.user is None:
    st.title("🛡️ The Terran")
    tab_l, tab_s = st.tabs(["Login", "Signup"])
    with tab_l:
        u_in, p_in = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Log In"):
            res = supabase.table("app_users").select("*").eq("username", u_in).execute()
            if res.data and res.data[0]['password'] == hash_pw(p_in):
                st.session_state.user = res.data[0]; st.rerun()
            else: st.error("Access Denied.")
    with tab_s:
        s_u, s_p = st.text_input("New User"), st.text_input("New Pass", type="password")
        s_r = st.selectbox("Role", ["Operator", "SME", "Manager", "Allocator"])
        if st.button("Sign Up"):
            supabase.table("app_users").insert({"username": s_u, "password": hash_pw(s_p), "role": s_r, "is_approved": True}).execute()
            st.success("Account Ready.")
else:
    u = st.session_state.user
    st.sidebar.subheader(f"User: {u['username']}")
    st.sidebar.write(f"Role: {u['role']}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None; st.rerun()

    if u['role'] in ["Admin", "Manager", "Allocator"]: render_mgmt(u['role'])
    if u['role'] == "SME": render_sme()
    if u['role'] == "Operator": render_operator(u['username'])