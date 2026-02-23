import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone
import pandas as pd
import os
import hashlib
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="The Terran | Content Ops", layout="wide")
load_dotenv()

try:
    supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"Supabase Connection Error: {e}")
    st.stop()

# --- 2. CONSTANTS & HELPERS ---
MR_LIST = ["BBFC:U::", "BBFC:PG::", "BBFC:12::", "BBFC:15::", "BBFC:18::"]
CD_LIST = ["Violence", "Threat", "Language", "Nudity", "Sex", "Drugs", "Horror", "Discrimination"]
OP_STATUS_OPTIONS = ["In Progress", "Reviewed by Operator", "Pending Calibration", "Title Issue"]

def hash_pw(pw): return hashlib.sha256(str.encode(pw)).hexdigest()

def get_idx(val, opt_list):
    try: return opt_list.index(val)
    except: return 0

def parse_iso(iso_str):
    try: return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    except: return None

# --- 3. OPERATOR WORKFLOW ---

def render_operator(username):
    st.subheader(f"📍 Operator Workspace | {username}")
    
    if st.button("➕ Request Titles"):
        hist = supabase.table("titles").select("id").eq("assigned_to", username).execute()
        if not hist.data:
            un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(2).execute().data
            if un:
                for t in un:
                    supabase.table("titles").update({"assigned_to": username, "status": "In Progress"}).eq("id", t['id']).execute()
                st.rerun()
        else:
            supabase.table("requests").insert({"operator_email": username, "status": "Pending"}).execute()
            st.info("Request for 2 titles sent to Management.")

    tasks = supabase.table("titles").select("*").eq("assigned_to", username).execute().data
    if not tasks: st.info("No titles assigned.")
    
    for t in tasks:
        locked = t['status'] in ["Reviewed by Operator", "Pending Calibration", "Finalized"]
        # FIX: Header now dynamically updates to match the current DB status
        with st.expander(f"📖 {t['gti']} - {t['title_name']} | Current: {t['status']}"):
            if t.get('sme_comments'): st.error(f"**SME Feedback:** {t['sme_comments']}")
            
            c1, c2, c3 = st.columns(3)
            mr = c1.selectbox("MR Rating", MR_LIST, index=get_idx(t['mr_rating'], MR_LIST), key=f"mr_{t['id']}", disabled=locked)
            cds = c2.multiselect("Content Descriptors", CD_LIST, default=t.get('cd_values', []), key=f"cd_{t['id']}", disabled=locked)
            stat = c3.selectbox("Status", OP_STATUS_OPTIONS, index=get_idx(t['status'], OP_STATUS_OPTIONS), key=f"st_{t['id']}")
            
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

# --- 4. MANAGEMENT & ALLOCATOR WORKFLOW ---

def render_mgmt(role):
    st.subheader("📊 Management Control")
    t_db, t_req, t_bin, t_alloc = st.tabs(["📁 Database", "📥 Requests", "🚩 Issue Bin", "📦 Allocator"])
    
    with t_db:
        search_query = st.text_input("🔍 Search Database (GTI or Name)")
        query = supabase.table("titles").select("*")
        if search_query: query = query.or_(f"gti.ilike.%{search_query}%,title_name.ilike.%{search_query}%")
        all_t = query.execute().data
        if all_t: st.dataframe(pd.DataFrame(all_t)[['gti', 'title_name', 'assigned_to', 'status']])

    with t_req:
        st.write("### Operator Request Fulfillment")
        reqs = supabase.table("requests").select("*").eq("status", "Pending").execute().data
        if reqs:
            for r in reqs:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.write(f"**{r['operator_email']}**")
                    if c2.button(f"Approve (+2)", key=f"q_{r['id']}"):
                        un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(2).execute().data
                        for item in un: supabase.table("titles").update({"assigned_to": r['operator_email'], "status": "In Progress"}).eq("id", item['id']).execute()
                        supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r['id']).execute()
                        st.rerun()
                    qty = c3.number_input("Custom Qty", 1, 20, 5, key=f"qty_{r['id']}")
                    if c4.button("Assign Custom", key=f"c_{r['id']}"):
                        un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(qty).execute().data
                        for item in un: supabase.table("titles").update({"assigned_to": r['operator_email'], "status": "In Progress"}).eq("id", item['id']).execute()
                        supabase.table("requests").update({"status": "Fulfilled"}).eq("id", r['id']).execute()
                        st.rerun()
        else: st.info("No pending requests.")

    with t_bin:
        issues = supabase.table("issue_bin").select("*").execute().data
        if issues: st.dataframe(pd.DataFrame(issues))

    with t_alloc:
        # RESTORED: MAIN BULK ASSIGNMENT FUNCTION
        st.markdown("#### 🔄 Main Bulk Allocation")
        ops = [o['username'] for o in supabase.table("app_users").select("username").eq("role", "Operator").execute().data]
        sel_ops = st.multiselect("Target Operators", ops)
        bulk_qty = st.number_input("Batch Size per Operator", 1, 50, 5)
        if st.button("Distribute Titles"):
            for o in sel_ops:
                un = supabase.table("titles").select("id").eq("status", "Unassigned").limit(bulk_qty).execute().data
                for item in un:
                    supabase.table("titles").update({"assigned_to": o, "status": "In Progress"}).eq("id", item['id']).execute()
            st.success("Bulk Distribution Complete.")
        
        st.divider()

        # TARGETED GTI FLOW
        st.markdown("#### 🎯 Targeted GTI Assignment")
        col_a, col_b, col_c = st.columns([2, 2, 1])
        target_gti = col_a.text_input("GTI ID")
        target_op = col_b.selectbox("Assign to Operator", ops, key="target_op_sel")
        if col_c.button("Assign Specific"):
            if target_gti:
                check = supabase.table("titles").select("*").eq("gti", target_gti).execute()
                if check.data:
                    supabase.table("titles").update({"assigned_to": target_op, "status": "In Progress"}).eq("gti", target_gti).execute()
                    st.success("Targeted GTI Assigned.")
                else: st.error("GTI not found.")

# --- 5. REMAINDER OF APP (SME & LOGIN) ---

def render_sme():
    st.subheader("🔍 SME Calibration")
    pending = supabase.table("titles").select("*").eq("status", "Pending Calibration").execute().data
    for p in pending or []:
        with st.expander(f"📋 {p['gti']} | Ops: {p['assigned_to']}"):
            st.write(f"**Primary Drivers:** {p.get('primary_drivers')}")
            st.write(f"**Ops Comments:** {p.get('context_ndi')}")
            feedback = st.text_area("SME Feedback", key=f"fb_{p['id']}")
            if st.button("Approve", key=f"ap_{p['id']}"):
                supabase.table("titles").update({"status": "Finalized", "sme_comments": feedback}).eq("id", p['id']).execute()
                st.rerun()
            if st.button("Return", key=f"re_{p['id']}"):
                supabase.table("titles").update({"status": "In Progress", "sme_comments": feedback}).eq("id", p['id']).execute()
                st.rerun()

if 'user' not in st.session_state: st.session_state.user = None
if st.session_state.user is None:
    st.title("🛡️ The Terran")
    t_login, t_admin, t_signup = st.tabs(["👤 Login", "🔑 Admin Portal", "📝 Signup"])
    with t_login:
        u_l, p_l = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Enter"):
            res = supabase.table("app_users").select("*").eq("username", u_l).eq("password", hash_pw(p_l)).execute()
            if res.data and res.data[0]['is_approved']: st.session_state.user = res.data[0]; st.rerun()
    with t_admin:
        a_pw = st.text_input("Master Key", type="password")
        if st.button("Authorize"):
            res = supabase.table("app_users").select("*").eq("username", "Admin").execute()
            if res.data and (a_pw == res.data[0]['password'] or hash_pw(a_pw) == res.data[0]['password']):
                st.session_state.user = res.data[0]; st.rerun()
    with t_signup:
        with st.form("s"):
            s_u, s_p = st.text_input("Username"), st.text_input("Password", type="password")
            s_r = st.selectbox("Role", ["Operator", "SME", "Manager", "Allocator"])
            if st.form_submit_button("Sign Up"):
                supabase.table("app_users").insert({"username": s_u, "password": hash_pw(s_p), "role": s_r, "is_approved": (s_r == "Operator")}).execute()
                st.success("Done.")
else:
    u = st.session_state.user
    st.sidebar.write(f"User: {u['username']} ({u['role']})")
    if st.sidebar.button("Logout"): st.session_state.user = None; st.rerun()
    if u['role'] == "Admin":
        at1, at2, at3, at4 = st.tabs(["⚙️ Roster", "📝 Ops", "🔍 SME", "📊 Mgmt"])
        with at1:
            users = supabase.table("app_users").select("*").execute().data
            for user in users:
                if user['username'] != u['username']:
                    c1, c2 = st.columns([4,1])
                    c1.write(f"{user['username']} ({user['role']})")
                    if not user['is_approved'] and c2.button("Approve", key=user['username']):
                        supabase.table("app_users").update({"is_approved": True}).eq("username", user['username']).execute(); st.rerun()
        with at2: render_operator(u['username'])
        with at3: render_sme()
        with at4: render_mgmt("Admin")
    elif u['role'] == "Operator": render_operator(u['username'])
    elif u['role'] == "SME": render_sme()
    else: render_mgmt(u['role'])