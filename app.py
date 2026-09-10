import os
import html
import base64
import mimetypes
from datetime import datetime
import streamlit as st

from database import (
    init_db, login_user, get_user, create_user, create_admin_account,
    get_all_users, approve_user, reject_user, delete_user, update_user,
    change_password, set_duty, get_online_drivers, get_today_trip_count,
    get_total_approved_trips, add_trip, get_user_trips, get_all_trips,
    approve_trip, reject_trip, get_leaderboard, create_post, get_posts,
    delete_post, toggle_pin, get_setting, set_setting, get_roles,
    get_permissions, create_role, update_role_permissions, rename_role,
    delete_role, user_has_permission, get_media, set_media
)

st.set_page_config(
    page_title="Taxi Cầu Vồng",
    page_icon="🌈",
    layout="wide",
    initial_sidebar_state="expanded",
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def esc(value):
    return html.escape(str(value or ""))


def save_uploaded(uploaded, prefix):
    if not uploaded:
        return ""
    ext = uploaded.name.rsplit(".", 1)[-1].lower()
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())
    return path



def image_data_uri(path):
    """Return a browser-safe data URI for local images."""
    if not path or not os.path.exists(path):
        return ""
    try:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except (OSError, ValueError):
        return ""


def can_toggle_own_duty(user):
    """Preserve the old driver ON/OFF duty feature while allowing admins/managers too."""
    return (
        user_has_permission(user, "manage_duty")
        or str(user.get("role", "")).lower() in {"driver", "user"}
    )


def has_admin_access(user):
    """A user can enter the admin area if they have any admin-panel capability."""
    admin_permissions = (
        "manage_users",
        "manage_roles",
        "approve_users",
        "approve_trips",
        "manage_posts",
        "view_duty",
        "manage_media",
        "manage_website",
    )
    return any(user_has_permission(user, p) for p in admin_permissions)


def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] { font-family:'Montserrat',sans-serif; }
    .stApp {
        background:
            radial-gradient(circle at top right, rgba(255,193,7,.12), transparent 35%),
            #080b10;
        color:#fff;
    }
    .block-container { max-width:1400px; padding-top:2rem; }
    [data-testid="stSidebar"] { background:#0b0f15; border-right:1px solid #282d35; }
    [data-testid="stSidebar"] * { color:#fff !important; }
    h1,h2,h3,h4,p,label { color:#fff !important; }

    .taxi-header {
        background:linear-gradient(135deg,#171b21,#090b0e);
        border:1px solid #343941;
        border-left:5px solid #ffc107;
        padding:22px; border-radius:15px; margin-bottom:20px;
    }
    .taxi-logo { font-size:35px; font-weight:900; color:#ffc107; }
    .taxi-title { font-size:27px; font-weight:900; color:#fff; }
    .taxi-subtitle { color:#8f98a5; font-size:12px; letter-spacing:2px; }

    .stat-card {
        background:#11161d; border:1px solid #2b3139; border-radius:14px;
        padding:20px; min-height:125px;
    }
    .stat-number { font-size:31px; font-weight:900; color:#ffc107; }
    .stat-label { color:#8d96a3; font-size:12px; text-transform:uppercase; letter-spacing:1px; }

    .hero {
        background:linear-gradient(135deg,rgba(255,193,7,.20),rgba(20,20,20,.95));
        border:1px solid #6e5710; border-radius:18px; padding:35px; margin-bottom:20px;
    }
    .hero-title { color:#ffc107; font-size:35px; font-weight:900; }
    .hero-text { color:#c5cbd3; font-size:14px; }

    .online-box { background:#0d1711; border:1px solid #1d6b35; border-radius:14px; padding:18px; }
    .offline-box { background:#17100e; border:1px solid #5e301d; border-radius:14px; padding:18px; }
    .post-card { background:#11161d; border:1px solid #2a3038; border-radius:14px; padding:20px; margin-bottom:15px; }
    .post-title { color:#ffc107; font-weight:800; font-size:19px; }

    .login-box {
        max-width:480px; margin:70px auto; background:#11161d;
        border:1px solid #353b43; border-top:5px solid #ffc107;
        padding:35px; border-radius:18px; box-shadow:0 15px 50px rgba(0,0,0,.5);
    }
    .login-logo { text-align:center; color:#ffc107; font-size:45px; font-weight:900; }
    .login-title { text-align:center; font-size:24px; font-weight:900; color:#fff; }
    .login-sub { text-align:center; color:#89919d; font-size:11px; letter-spacing:2px; margin-bottom:25px; }

    .stButton > button {
        background:#ffc107 !important; color:#080b10 !important;
        border:none !important; border-radius:8px !important; font-weight:800 !important;
    }
    .stButton > button:hover { background:#ffcf3a !important; }
    div[data-baseweb="input"] { background:#151a21 !important; }
    input, textarea { color:white !important; }
    [data-testid="stFileUploader"] {
        background:#11161d; border:1px dashed #4a5059;
        border-radius:12px; padding:10px;
    }
    .footer { text-align:center; color:#66707c; font-size:11px; margin-top:50px; padding:20px; }
    .role-badge {
        display:inline-block; padding:4px 9px; border-radius:999px;
        background:#242a32; color:#ffc107; font-size:11px; font-weight:800;
        margin-right:5px;
    }
    </style>
    """, unsafe_allow_html=True)


def login_page():
    logo = get_media("site_logo", "")
    logo_uri = image_data_uri(logo)

    if logo_uri:
        logo_block = (
            f'<img src="{logo_uri}" alt="Taxi Cầu Vồng" '
            'style="width:110px;height:110px;object-fit:contain;border-radius:18px;">'
        )
    else:
        logo_block = '<div class="login-logo">🌈</div>'

    st.markdown(f"""
    <div class="login-box">
        <div style="text-align:center;margin-bottom:10px;">{logo_block}</div>
        <div class="login-title">TAXI CẦU VỒNG</div>
        <div class="login-sub">TAXI CHẤM CÔNG</div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔐 ĐĂNG NHẬP", "📝 ĐĂNG KÝ"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Tài khoản", placeholder="Số MOMO (ID) Trong Game")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
            submit = st.form_submit_button("ĐĂNG NHẬP", use_container_width=True)

            if submit:
                if not username.strip() or not password:
                    st.error("Vui lòng nhập đầy đủ tài khoản và mật khẩu.")
                else:
                    user, error = login_user(username.strip(), password)
                    if error:
                        st.error(error)
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.rerun()

    with tab_register:
        with st.form("register_form"):
            full_name = st.text_input("Họ và tên", placeholder="Nguyễn Văn A")
            username = st.text_input("Tài khoản", placeholder="taxidriver01")
            password = st.text_input("Mật khẩu", type="password")
            password2 = st.text_input("Nhập lại mật khẩu", type="password")
            avatar = st.file_uploader(
                "Ảnh đại diện",
                type=["png", "jpg", "jpeg", "webp"],
                key="register_avatar",
            )
            submit = st.form_submit_button("ĐĂNG KÝ TÀI KHOẢN", use_container_width=True)

            if submit:
                if not full_name.strip() or not username.strip() or not password:
                    st.error("Vui lòng nhập đủ họ tên, tài khoản và mật khẩu.")
                elif password != password2:
                    st.error("Hai mật khẩu không giống nhau.")
                elif len(password) < 6:
                    st.error("Mật khẩu phải có ít nhất 6 ký tự.")
                else:
                    avatar_path = save_uploaded(avatar, "avatar") if avatar else ""
                    ok, message = create_user(
                        username.strip(),
                        password,
                        full_name.strip(),
                        "driver",
                        False,
                        avatar_path,
                    )
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)

def force_password_change():
    """Require the default/admin-created temporary password to be changed."""
    user = st.session_state.user
    if not user.get("must_change_password"):
        return False

    st.warning("🔐 Bạn đang dùng mật khẩu tạm thời. Hãy đổi mật khẩu trước khi tiếp tục.")
    with st.form("force_change_password"):
        old_password = st.text_input("Mật khẩu hiện tại", type="password")
        new_password = st.text_input("Mật khẩu mới", type="password")
        confirm = st.text_input("Nhập lại mật khẩu mới", type="password")
        submit = st.form_submit_button("💾 ĐỔI MẬT KHẨU", use_container_width=True)

        if submit:
            if not old_password or not new_password:
                st.error("Vui lòng nhập đầy đủ thông tin.")
            elif new_password != confirm:
                st.error("Hai mật khẩu mới không giống nhau.")
            elif len(new_password) < 6:
                st.error("Mật khẩu mới phải có ít nhất 6 ký tự.")
            else:
                ok, message = change_password(user["id"], old_password, new_password)
                if ok:
                    st.session_state.user = get_user(user["id"]) or user
                    st.success("Đổi mật khẩu thành công.")
                    st.rerun()
                else:
                    st.error(message)
    return True


def sidebar():
    user = get_user(st.session_state.user["id"]) or st.session_state.user
    st.session_state.user = user

    with st.sidebar:
        avatar = user.get("avatar", "")
        site_logo = get_media("site_logo", "")
        if avatar and os.path.exists(avatar):
            st.image(avatar, width=75)
        elif site_logo and os.path.exists(site_logo):
            st.image(site_logo, width=90)
        else:
            st.markdown('<div style="text-align:center;font-size:45px;">🌈</div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div style="text-align:center;padding:5px 0 15px;border-bottom:1px solid #292f37;">
            <div style="color:#ffc107;font-size:18px;font-weight:900;">LOS SANTOS TAXI</div>
            <div style="color:#69727e;font-size:10px;letter-spacing:2px;">DISPATCH SYSTEM</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"### 👤 {esc(user['full_name'])}")
        st.caption(f"🛡️ {user['role'].upper()}")

        options = []
        if user_has_permission(user, "view_dashboard"): options.append("🏠 Tổng quan")
        if user_has_permission(user, "submit_trip"): options.append("📸 Chấm Công (NPC)")
        if user_has_permission(user, "view_leaderboard"): options.append("🏆 BXH tài xế")
        if user_has_permission(user, "view_history"): options.append("📋 Lịch sử chuyến")
        if user_has_permission(user, "view_posts"): options.append("📢 Thông báo")
        if user_has_permission(user, "manage_users") or user_has_permission(user, "manage_roles"):
            options.append("🛠️ ADMIN")

        menu = st.radio("MENU", options or ["🏠 Tổng quan"])

        st.markdown("---")
        if user.get("duty"):
            st.markdown("""
            <div class="online-box">
                <div style="color:#4ade80;font-weight:800;">🟢 ĐANG ON DUTY</div>
                <div style="color:#8b969f;font-size:11px;">Bạn đang nhận chuyến</div>
            </div>
            """, unsafe_allow_html=True)
            if can_toggle_own_duty(user) and st.button("🔴 OFF DUTY", use_container_width=True):
                set_duty(user["id"], False); st.rerun()
        else:
            st.markdown("""
            <div class="offline-box">
                <div style="color:#f87171;font-weight:800;">🔴 ĐANG OFF DUTY</div>
                <div style="color:#8b969f;font-size:11px;">Bạn chưa nhận chuyến</div>
            </div>
            """, unsafe_allow_html=True)
            if can_toggle_own_duty(user) and st.button("🟢 ON DUTY", use_container_width=True):
                set_duty(user["id"], True); st.rerun()

        st.markdown("---")
        if st.button("🚪 ĐĂNG XUẤT", use_container_width=True):
            st.session_state.clear(); st.rerun()

    return menu


def page_header():
    title = get_setting("site_title", "LOS SANTOS TAXI")
    subtitle = get_setting("site_subtitle", "TAXI DISPATCH SYSTEM")
    logo = get_media("site_logo", "")
    logo_uri = image_data_uri(logo)

    logo_html = ""
    if logo_uri:
        logo_html = (
            f'<img src="{logo_uri}" alt="Logo" '
            'style="height:55px;width:55px;object-fit:contain;'
            'vertical-align:middle;margin-right:12px;border-radius:10px;">'
        )

    st.markdown(f"""
    <div class="taxi-header">
        <div class="taxi-logo">{logo_html}{esc(title)}</div>
        <div class="taxi-title">{esc(subtitle)}</div>
        <div class="taxi-subtitle">LOS SANTOS • TAXI MANAGEMENT</div>
    </div>
    """, unsafe_allow_html=True)

def page_dashboard():
    user = st.session_state.user
    today = get_today_trip_count(user["id"])
    total = get_total_approved_trips(user["id"])
    online = len(get_online_drivers())
    home_text = get_setting("home_text", "Hệ thống quản lý tài xế Taxi Los Santos")
    banner = get_media("home_banner", "")

    st.markdown(f"""
    <div class="hero">
        <div class="hero-title">🌈 XIN CHÀO,TÀI XẾ</div>
        <div class="hero-text">{esc(home_text)}</div>
    </div>
    """, unsafe_allow_html=True)

    if banner and os.path.exists(banner):
        st.image(banner, use_container_width=True)

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(f'<div class="stat-card"><div class="stat-number">{today}/50</div><div class="stat-label">Chuyến hôm nay</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><div class="stat-number">{total}</div><div class="stat-label">Tổng chuyến</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><div class="stat-number">{online}</div><div class="stat-label">Tài xế ON DUTY</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="stat-card"><div class="stat-number">{max(0,50-today)}</div><div class="stat-label">Chuyến còn lại</div></div>', unsafe_allow_html=True)

    st.markdown("## 📢 BÀI ĐĂNG MỚI")
    posts = get_posts()
    if not posts: st.info("Chưa có bài đăng nào.")
    for post in posts[:5]:
        st.markdown(f"""
        <div class="post-card">
            <div class="post-title">{"📌 " if post["pinned"] else ""}{esc(post["title"])}</div>
            <div style="color:#9ba4ae;font-size:11px;margin:5px 0 15px;">{esc(post["created_at"][:16].replace("T"," "))}</div>
            <div style="color:#ddd;">{esc(post["content"])}</div>
        </div>
        """, unsafe_allow_html=True)
        if post.get("image") and os.path.exists(post["image"]):
            st.image(post["image"], use_container_width=True)


def page_upload():
    user = st.session_state.user
    count = get_today_trip_count(user["id"])
    st.markdown("""
    <div class="hero">
        <div class="hero-title">📸 ĐĂNG ẢNH CHUYẾN (NPC) </div>
        <div class="hero-text">Tải ảnh bằng chứng chuyến xe. Sau khi Admin duyệt, hệ thống sẽ cộng +1 chuyến.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"### 🚕 Tiến độ hôm nay: `{count}/50` chuyến")
    if count >= 50:
        st.error("🚫 Bạn đã đạt tối đa 50 chuyến trong ngày."); return

    uploaded = st.file_uploader("Chọn ảnh chuyến xe", type=["png","jpg","jpeg","webp"])
    note = st.text_input("Ghi chú chuyến (không bắt buộc)")
    if uploaded:
        st.image(uploaded, caption="Ảnh chuyến xe", use_container_width=True)
        if st.button("🚕 GỬI ẢNH +1 CHUYẾN", use_container_width=True):
            path = save_uploaded(uploaded, f"trip_{user['id']}")
            ok, message = add_trip(user["id"], path, note)
            st.success(message) if ok else st.error(message)
            if ok: st.rerun()


def page_history():
    trips = get_user_trips(st.session_state.user["id"])
    st.markdown("## 📋 LỊCH SỬ CHUYẾN XE")
    if not trips: st.info("Bạn chưa có chuyến xe nào."); return
    for trip in trips:
        status = {"approved":"🟢 ĐÃ DUYỆT","rejected":"🔴 TỪ CHỐI"}.get(trip["status"],"🟡 CHỜ DUYỆT")
        with st.container(border=True):
            c1,c2 = st.columns([1,2])
            with c1:
                if trip.get("image") and os.path.exists(trip["image"]): st.image(trip["image"], use_container_width=True)
            with c2:
                st.markdown(f"### 🚕 Chuyến #{trip['id']}")
                st.write(f"**Trạng thái:** {status}")
                st.write(f"**Thời gian:** {trip['created_at'][:19].replace('T',' ')}")
                if trip.get("note"): st.write(f"**Ghi chú:** {trip['note']}")
                if trip.get("approved_at"): st.write(f"**Xử lý:** {trip['approved_at'][:19].replace('T',' ')}")


def page_leaderboard():
    st.markdown("## 🏆 BẢNG XẾP HẠNG TÀI XẾ")
    board = get_leaderboard()
    if not board: st.info("Chưa có dữ liệu."); return
    for index, driver in enumerate(board, 1):
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"#{index}"
        duty = "🟢 ON DUTY" if driver["duty"] else "🔴 OFF DUTY"
        st.markdown(f"""
        <div class="post-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div><span style="color:#ffc107;font-size:23px;font-weight:900;">{medal}</span>
                <span style="color:white;font-size:18px;font-weight:800;margin-left:12px;">{esc(driver["name"])}</span></div>
                <div style="color:#ffc107;font-weight:900;">{driver["trips"]} CHUYẾN</div>
            </div>
            <div style="color:#8d96a3;font-size:11px;margin-top:8px;">@{esc(driver["username"])} • {duty}</div>
        </div>
        """, unsafe_allow_html=True)


def page_posts():
    st.markdown("## 📢 THÔNG BÁO")
    posts = get_posts()
    if not posts: st.info("Chưa có thông báo."); return
    for post in posts:
        prefix = "📌 " if post["pinned"] else ""
        st.markdown(f"### {prefix}{esc(post['title'])}")
        st.caption(post["created_at"][:19].replace("T"," "))
        st.write(post["content"])
        if post.get("image") and os.path.exists(post["image"]): st.image(post["image"], use_container_width=True)
        st.markdown("---")


def admin_users():
    user = st.session_state.user
    st.markdown("### 👥 QUẢN LÝ TÀI KHOẢN")

    with st.expander("➕ TẠO TÀI KHOẢN CHO NGƯỜI KHÁC", expanded=True):
        roles = get_roles()
        role_keys = [r["role_key"] for r in roles]
        with st.form("create_account_form"):
            c1,c2 = st.columns(2)
            with c1:
                full_name = st.text_input("Họ và tên")
                username = st.text_input("Số MOMO (ID)")
                password = st.text_input("Mật khẩu", type="password")
            with c2:
                role = st.selectbox("Role", role_keys, format_func=lambda x: next((r["name"] for r in roles if r["role_key"]==x), x))
                approved = st.checkbox("Duyệt ngay", value=True)
                avatar = st.file_uploader("Ảnh đại diện", type=["png","jpg","jpeg","webp"], key="new_user_avatar")
            submit = st.form_submit_button("➕ TẠO TÀI KHOẢN", use_container_width=True)
            if submit:
                avatar_path = save_uploaded(avatar, "avatar") if avatar else ""
                ok,msg = create_user(username,password,full_name,role,approved,avatar_path,user["id"])
                st.success(msg) if ok else st.error(msg)
                if ok: st.rerun()

    with st.expander("👤 TẠO TÀI KHOẢN QUẢN LÝ"):
        with st.form("create_admin_form"):
            u = st.text_input("Tên Admin")
            n = st.text_input("Họ tên Admin")
            p = st.text_input("Mật khẩu Admin", type="password")
            av = st.file_uploader("Ảnh Admin", type=["png","jpg","jpeg","webp"], key="admin_avatar")
            if st.form_submit_button("🛡️ TẠO ADMIN", use_container_width=True):
                path = save_uploaded(av,"admin_avatar") if av else ""
                ok,msg = create_admin_account(u,p,n,user["id"],path)
                st.success(msg) if ok else st.error(msg)
                if ok: st.rerun()

    st.markdown("### 📋 DANH SÁCH TÀI KHOẢN")
    for item in get_all_users():
        with st.container(border=True):
            c1,c2,c3,c4 = st.columns([1.6,1.2,1.2,1])
            with c1:
                if item.get("avatar") and os.path.exists(item["avatar"]): st.image(item["avatar"], width=55)
                st.write(f"**{item['full_name']}**")
                st.caption(f"@{item['username']}")
            with c2:
                st.markdown(f'<span class="role-badge">{esc(item["role"].upper())}</span>', unsafe_allow_html=True)
                st.write("🟢 ĐÃ DUYỆT" if item["approved"] else "🟡 CHỜ DUYỆT")
                st.write("🟢 ACTIVE" if item["active"] else "🔴 KHÓA")
            with c3:
                if not item["approved"] and st.button("DUYỆT", key=f"au{item['id']}"):
                    approve_user(item["id"]); st.rerun()
                if item["username"] != "admin":
                    active_text = "🔒 KHÓA" if item["active"] else "🔓 MỞ KHÓA"
                    if st.button(active_text, key=f"act{item['id']}"):
                        update_user(item["id"], active=not bool(item["active"])); st.rerun()
            with c4:
                if item["username"] != "admin":
                    if st.button("🗑️ XÓA", key=f"du{item['id']}"):
                        delete_user(item["id"]); st.rerun()

            if item["username"] != "admin":
                with st.expander("✏️ Sửa tài khoản"):
                    roles = get_roles()
                    role_keys = [r["role_key"] for r in roles]
                    new_name = st.text_input("Họ tên", value=item["full_name"], key=f"nm{item['id']}")
                    new_role = st.selectbox("Role", role_keys, index=role_keys.index(item["role"]) if item["role"] in role_keys else 0, key=f"rl{item['id']}")
                    new_avatar = st.file_uploader("Đổi ảnh đại diện", type=["png","jpg","jpeg","webp"], key=f"av{item['id']}")
                    if st.button("💾 LƯU", key=f"save{item['id']}"):
                        avatar_path = save_uploaded(new_avatar,f"avatar_{item['id']}") if new_avatar else None
                        update_user(item["id"], full_name=new_name, role=new_role, avatar=avatar_path)
                        st.rerun()

            if item["approved"] == 0 and item["username"] != "admin":
                if st.button("❌ TỪ CHỐI / XÓA", key=f"rej{item['id']}"):
                    reject_user(item["id"]); st.rerun()


def admin_roles():
    st.markdown("### 🛡️ ROLE & QUYỀN")
    permissions = get_permissions()
    perm_map = {p["permission_key"]: p["name"] for p in permissions}

    with st.expander("➕ TẠO ROLE MỚI"):
        with st.form("new_role"):
            key = st.text_input("Role key", placeholder="moderator")
            name = st.text_input("Tên hiển thị", placeholder="Moderator")
            desc = st.text_input("Mô tả")
            selected = st.multiselect("Quyền", list(perm_map.keys()), format_func=lambda x: perm_map[x])
            if st.form_submit_button("➕ TẠO ROLE", use_container_width=True):
                ok,msg = create_role(key,name,desc,selected)
                st.success(msg) if ok else st.error(msg)
                if ok: st.rerun()

    for role in get_roles():
        with st.container(border=True):
            st.markdown(f"#### 🛡️ {role['name']}  ·  `{role['role_key']}`")
            st.caption(role["description"] or "")
            selected = st.multiselect(
                "Quyền được cấp",
                list(perm_map.keys()),
                default=[p for p in role["permissions"] if p in perm_map],
                format_func=lambda x: perm_map[x],
                key=f"rp_{role['id']}",
            )
            c1,c2 = st.columns(2)
            with c1:
                if st.button("💾 LƯU QUYỀN", key=f"save_role_{role['id']}"):
                    ok,msg = update_role_permissions(role["role_key"],selected)
                    st.success(msg) if ok else st.error(msg)
                    st.rerun()
            with c2:
                if role["role_key"] not in ("admin","manager","driver","user"):
                    if st.button("🗑️ XÓA ROLE", key=f"del_role_{role['id']}"):
                        ok,msg = delete_role(role["role_key"])
                        st.success(msg) if ok else st.error(msg)
                        st.rerun()


def admin_trips():
    st.markdown("### 🚕 DUYỆT CHUYẾN XE")
    pending = [x for x in get_all_trips() if x["status"] == "pending"]
    if not pending: st.success("Không có chuyến nào đang chờ duyệt.")
    for trip in pending:
        with st.container(border=True):
            st.markdown(f"### 🚕 Chuyến #{trip['id']}")
            st.write(f"**Tài xế:** {trip['full_name']} (@{trip['username']})")
            if trip.get("image") and os.path.exists(trip["image"]): st.image(trip["image"], use_container_width=True)
            if trip.get("note"): st.write(f"**Ghi chú:** {trip['note']}")
            c1,c2 = st.columns(2)
            with c1:
                if st.button("✅ DUYỆT +1 CHUYẾN", key=f"apt{trip['id']}", use_container_width=True):
                    ok,msg=approve_trip(trip["id"],st.session_state.user["id"])
                    st.success(msg) if ok else st.error(msg); st.rerun()
            with c2:
                if st.button("❌ TỪ CHỐI", key=f"rjt{trip['id']}", use_container_width=True):
                    ok,msg=reject_trip(trip["id"],st.session_state.user["id"])
                    st.success(msg) if ok else st.error(msg); st.rerun()


def admin_posts():
    st.markdown("### 📢 ĐĂNG BÀI LÊN WEBSITE")
    with st.form("create_post"):
        title = st.text_input("Tiêu đề")
        content = st.text_area("Nội dung", height=180)
        image = st.file_uploader("Ảnh bài đăng", type=["png","jpg","jpeg","webp"], key="post_image")
        pinned = st.checkbox("📌 Ghim bài")
        if st.form_submit_button("📢 ĐĂNG BÀI", use_container_width=True):
            if not title.strip(): st.error("Vui lòng nhập tiêu đề.")
            else:
                path = save_uploaded(image,"post") if image else ""
                create_post(title,content,path,st.session_state.user["id"],pinned)
                st.success("Đã đăng bài."); st.rerun()

    st.markdown("---")
    for post in get_posts():
        with st.container(border=True):
            st.write(f"**{post['title']}**")
            c1,c2=st.columns(2)
            with c1:
                label="📌 BỎ GHIM" if post["pinned"] else "📌 GHIM BÀI"
                if st.button(label,key=f"pin{post['id']}"): toggle_pin(post["id"],post["pinned"]); st.rerun()
            with c2:
                if st.button("🗑️ XÓA",key=f"dp{post['id']}"): delete_post(post["id"]); st.rerun()


def admin_media():
    st.markdown("### 🖼️ QUẢN LÝ HÌNH ẢNH")
    st.caption("Logo chính và banner được lưu trong thư mục uploads/.")

    current_logo = get_media("site_logo", "")
    current_banner = get_media("home_banner", "")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 🚕 Logo chính")
        if current_logo and os.path.exists(current_logo):
            st.image(current_logo, use_container_width=True)
        with st.form("logo_form", clear_on_submit=False):
            logo = st.file_uploader(
                "Chọn logo",
                type=["png", "jpg", "jpeg", "webp"],
                key="site_logo_upload",
            )
            save_logo = st.form_submit_button("💾 LƯU LOGO", use_container_width=True)
            if save_logo:
                if not logo:
                    st.warning("Chưa chọn ảnh logo.")
                else:
                    path = save_uploaded(logo, "site_logo")
                    set_media("site_logo", path, "Logo chính")
                    st.success("Đã lưu logo chính.")
                    st.rerun()

    with c2:
        st.markdown("#### 🖼️ Banner trang chủ")
        if current_banner and os.path.exists(current_banner):
            st.image(current_banner, use_container_width=True)
        with st.form("banner_form", clear_on_submit=False):
            banner = st.file_uploader(
                "Chọn banner",
                type=["png", "jpg", "jpeg", "webp"],
                key="home_banner_upload",
            )
            save_banner = st.form_submit_button("💾 LƯU BANNER", use_container_width=True)
            if save_banner:
                if not banner:
                    st.warning("Chưa chọn ảnh banner.")
                else:
                    path = save_uploaded(banner, "home_banner")
                    set_media("home_banner", path, "Banner trang chủ")
                    st.success("Đã lưu banner.")
                    st.rerun()

def admin_duty():
    st.markdown("### 🟢 TÀI XẾ ĐANG ON DUTY")
    drivers=get_online_drivers()
    if not drivers: st.info("Hiện không có tài xế nào ON DUTY.")
    for d in drivers:
        st.markdown(f"""
        <div class="online-box" style="margin-bottom:10px;">
            <div style="color:white;font-size:17px;font-weight:800;">🟢 {esc(d["full_name"])}</div>
            <div style="color:#7d8792;font-size:11px;">@{esc(d["username"])}</div>
        </div>
        """,unsafe_allow_html=True)


def admin_website():
    st.markdown("### ⚙️ CHỈNH SỬA WEBSITE")
    with st.form("website_settings"):
        title=st.text_input("Tên website",value=get_setting("site_title"))
        subtitle=st.text_input("Tiêu đề phụ",value=get_setting("site_subtitle"))
        home=st.text_area("Nội dung trang chủ",value=get_setting("home_text"))
        contact=st.text_area("Thông tin liên hệ",value=get_setting("contact"))
        if st.form_submit_button("💾 LƯU THAY ĐỔI",use_container_width=True):
            set_setting("site_title",title); set_setting("site_subtitle",subtitle)
            set_setting("home_text",home); set_setting("contact",contact)
            st.success("Đã cập nhật website."); st.rerun()


def admin_page():
    user=st.session_state.user
    st.markdown("## 🛠️ ADMIN CONTROL PANEL")

    tabs=[]
    if user_has_permission(user,"manage_users") or user_has_permission(user,"approve_users"): tabs.append(("👥 TÀI KHOẢN",admin_users))
    if user_has_permission(user,"manage_roles"): tabs.append(("🛡️ ROLE & QUYỀN",admin_roles))
    if user_has_permission(user,"approve_trips"): tabs.append(("🚕 DUYỆT CHUYẾN",admin_trips))
    if user_has_permission(user,"manage_posts"): tabs.append(("📢 ĐĂNG BÀI",admin_posts))
    if user_has_permission(user,"view_duty"): tabs.append(("🟢 ON DUTY",admin_duty))
    if user_has_permission(user,"manage_media"): tabs.append(("🖼️ HÌNH ẢNH",admin_media))
    if user_has_permission(user,"manage_website"): tabs.append(("⚙️ SỬA WEBSITE",admin_website))

    if not tabs:
        st.warning("Tài khoản này chưa được cấp quyền quản trị.")
        return
    rendered=st.tabs([x[0] for x in tabs])
    for tab, (_,fn) in zip(rendered,tabs):
        with tab: fn()


def main():
    init_db()
    load_css()
    if "logged_in" not in st.session_state:
        st.session_state.logged_in=False

    if not st.session_state.logged_in:
        login_page()
        st.markdown('<div class="footer">🌈 TAXI CẦU VỒNG • WEB CHẤM CÔNG</div>',unsafe_allow_html=True)
        return

    user = get_user(st.session_state.user["id"]) or st.session_state.user
    st.session_state.user = user

    if force_password_change():
        st.markdown(
            '<div class="footer">🌈 TAXI CẦU VỒNG • Vui lòng đổi mật khẩu tạm thời</div>',
            unsafe_allow_html=True,
        )
        return

    menu = sidebar()
    page_header()

    routes={
        "🏠 Tổng quan":("view_dashboard",page_dashboard),
        "📸 Đăng ảnh +1 chuyến":("submit_trip",page_upload),
        "🏆 BXH tài xế":("view_leaderboard",page_leaderboard),
        "📋 Lịch sử chuyến":("view_history",page_history),
        "📢 Thông báo":("view_posts",page_posts),
        "🛠️ ADMIN":("admin_panel",admin_page),
    }
    permission, fn = routes.get(menu, (None, page_dashboard))
    if permission == "admin_panel":
        if not has_admin_access(user):
            st.error("Bạn không có quyền sử dụng chức năng này.")
        else:
            fn()
    elif permission and not user_has_permission(user, permission):
        st.error("Bạn không có quyền sử dụng chức năng này.")
    else:
        fn()

    st.markdown("""
    <div class="footer">
        🌈 Taxi Cầu Vồng • Hệ thống đang hoạt động • Daily reset: 02:00 GMT+7
    </div>
    """,unsafe_allow_html=True)


if __name__ == "__main__":
    main()
