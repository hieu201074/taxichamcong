import os
import uuid
import streamlit as st
from PIL import Image

from database import (
    init_db,
    login_user,
    create_user,
    get_user,
    get_today_trip_count,
    add_trip,
    get_user_trips,
    get_pending_users,
    approve_user,
    delete_user,
    get_pending_trips,
    approve_trip,
    reject_trip,
    get_all_users,
    get_ranking
)


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Taxi System",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.main {
    background: #080b12;
}

[data-testid="stSidebar"] {
    background: #0d111a;
}

.hero {
    padding: 35px;
    border-radius: 20px;
    background: linear-gradient(
        135deg,
        #111827,
        #172033
    );
    border: 1px solid #293448;
    margin-bottom: 25px;
}

.hero h1 {
    color: white;
    font-size: 42px;
    margin-bottom: 5px;
}

.hero p {
    color: #9ca3af;
}

.card {
    padding: 22px;
    border-radius: 16px;
    background: #111827;
    border: 1px solid #273244;
    margin-bottom: 15px;
}

.stat {
    padding: 22px;
    border-radius: 16px;
    background: #111827;
    border: 1px solid #273244;
    text-align: center;
}

.stat-number {
    font-size: 32px;
    font-weight: bold;
    color: #facc15;
}

.stat-title {
    color: #9ca3af;
}

.trip-approved {
    color: #22c55e;
    font-weight: bold;
}

.trip-pending {
    color: #facc15;
    font-weight: bold;
}

.trip-rejected {
    color: #ef4444;
    font-weight: bold;
}

.footer {
    text-align: center;
    color: #6b7280;
    margin-top: 50px;
    padding: 20px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None


def logout():
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.rerun()


# ============================================================
# LOGIN / REGISTER
# ============================================================

def auth_page():

    st.markdown("""
    <div class="hero">
        <h1>🚕 TAXI SYSTEM</h1>
        <p>Hệ thống quản lý chuyến xe Taxi</p>
    </div>
    """, unsafe_allow_html=True)

    login_tab, register_tab = st.tabs([
        "🔐 Đăng nhập",
        "📝 Đăng ký"
    ])

    with login_tab:

        st.subheader("Đăng nhập")

        username = st.text_input(
            "Tên đăng nhập",
            key="login_username"
        )

        password = st.text_input(
            "Mật khẩu",
            type="password",
            key="login_password"
        )

        if st.button(
            "🚕 ĐĂNG NHẬP",
            use_container_width=True
        ):

            if not username or not password:
                st.error("Vui lòng nhập đầy đủ thông tin.")

            else:

                user, error = login_user(
                    username,
                    password
                )

                if error:
                    st.error(error)

                else:

                    st.session_state.logged_in = True
                    st.session_state.user_id = user["id"]

                    st.success("Đăng nhập thành công.")
                    st.rerun()

        st.info(
            "Tài khoản admin mặc định: admin / admin123"
        )

    with register_tab:

        st.subheader("Tạo tài khoản Taxi")

        full_name = st.text_input(
            "Họ và tên"
        )

        username = st.text_input(
            "Tên đăng nhập",
            key="register_username"
        )

        password = st.text_input(
            "Mật khẩu",
            type="password",
            key="register_password"
        )

        password2 = st.text_input(
            "Nhập lại mật khẩu",
            type="password"
        )

        if st.button(
            "📝 ĐĂNG KÝ",
            use_container_width=True
        ):

            if not full_name or not username or not password:
                st.error("Vui lòng nhập đầy đủ thông tin.")

            elif password != password2:
                st.error("Mật khẩu nhập lại không khớp.")

            elif len(password) < 6:
                st.error("Mật khẩu phải có ít nhất 6 ký tự.")

            else:

                success, message = create_user(
                    username.strip(),
                    password,
                    full_name.strip()
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)


# ============================================================
# SIDEBAR
# ============================================================

def sidebar(user):

    st.sidebar.markdown(
        "# 🚕 TAXI"
    )

    st.sidebar.caption(
        f"Xin chào, **{user['full_name']}**"
    )

    st.sidebar.divider()

    if user["role"] == "admin":

        page = st.sidebar.radio(
            "MENU",
            [
                "🏠 Dashboard",
                "👥 Duyệt tài khoản",
                "📸 Duyệt chuyến",
                "👤 Quản lý tài khoản",
                "🏆 Bảng xếp hạng"
            ]
        )

    else:

        page = st.sidebar.radio(
            "MENU",
            [
                "🏠 Dashboard",
                "📸 Đăng chuyến",
                "📋 Lịch sử chuyến",
                "🏆 Bảng xếp hạng"
            ]
        )

    st.sidebar.divider()

    if st.sidebar.button(
        "🚪 Đăng xuất",
        use_container_width=True
    ):
        logout()

    return page


# ============================================================
# DASHBOARD
# ============================================================

def dashboard(user):

    today = get_today_trip_count(
        user["id"]
    )

    remaining = max(
        0,
        50 - today
    )

    st.markdown("""
    <div class="hero">
        <h1>🚕 Taxi Dashboard</h1>
        <p>Quản lý hoạt động tài xế</p>
    </div>
    """, unsafe_allow_html=True)

    if user["role"] == "admin":

        pending_users = len(
            get_pending_users()
        )

        pending_trips = len(
            get_pending_trips()
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(
                f"""
                <div class="stat">
                    <div class="stat-number">{pending_users}</div>
                    <div class="stat-title">
                        Tài khoản chờ duyệt
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                f"""
                <div class="stat">
                    <div class="stat-number">{pending_trips}</div>
                    <div class="stat-title">
                        Chuyến chờ duyệt
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col3:
            st.markdown(
                """
                <div class="stat">
                    <div class="stat-number">50</div>
                    <div class="stat-title">
                        Giới hạn chuyến/ngày
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    else:

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(
                f"""
                <div class="stat">
                    <div class="stat-number">{today}</div>
                    <div class="stat-title">
                        Chuyến hôm nay
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                f"""
                <div class="stat">
                    <div class="stat-number">{remaining}</div>
                    <div class="stat-title">
                        Lượt còn lại
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col3:
            st.markdown(
                """
                <div class="stat">
                    <div class="stat-number">50</div>
                    <div class="stat-title">
                        Tối đa mỗi ngày
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.info(
            "⏰ Hệ thống reset lượt chuyến lúc 02:00 mỗi ngày "
            "(giờ Việt Nam)."
        )


# ============================================================
# UPLOAD TRIP
# ============================================================

def upload_trip(user):

    st.markdown("""
    <div class="hero">
        <h1>📸 Đăng chuyến xe</h1>
        <p>Upload ảnh để gửi chuyến cho Admin kiểm duyệt</p>
    </div>
    """, unsafe_allow_html=True)

    current = get_today_trip_count(
        user["id"]
    )

    st.progress(
        current / 50
    )

    st.write(
        f"**Đã duyệt:** {current}/50 chuyến hôm nay"
    )

    if current >= 50:

        st.error(
            "Bạn đã đạt giới hạn 50 chuyến hôm nay."
        )
        return

    uploaded = st.file_uploader(
        "Chọn ảnh chuyến xe",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp"
        ]
    )

    note = st.text_area(
        "Ghi chú",
        placeholder="Ví dụ: Chuyến LS → Sân bay..."
    )

    if uploaded:

        image = Image.open(uploaded)

        st.image(
            image,
            caption="Ảnh chuyến xe",
            use_container_width=True
        )

        if st.button(
            "🚕 GỬI CHUYẾN",
            use_container_width=True
        ):

            os.makedirs(
                "uploads",
                exist_ok=True
            )

            extension = os.path.splitext(
                uploaded.name
            )[1].lower()

            filename = (
                str(uuid.uuid4())
                + extension
            )

            path = os.path.join(
                "uploads",
                filename
            )

            with open(path, "wb") as f:
                f.write(
                    uploaded.getbuffer()
                )

            success, message = add_trip(
                user["id"],
                path,
                note
            )

            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)


# ============================================================
# HISTORY
# ============================================================

def history(user):

    st.markdown("""
    <div class="hero">
        <h1>📋 Lịch sử chuyến</h1>
        <p>Danh sách các chuyến bạn đã gửi</p>
    </div>
    """, unsafe_allow_html=True)

    trips = get_user_trips(
        user["id"]
    )

    if not trips:
        st.info(
            "Bạn chưa có chuyến nào."
        )
        return

    for trip in trips:

        with st.container():

            col1, col2 = st.columns(
                [1, 2]
            )

            with col1:

                if os.path.exists(
                    trip["image_path"]
                ):
                    st.image(
                        trip["image_path"],
                        use_container_width=True
                    )

            with col2:

                st.write(
                    f"### 🚕 Chuyến #{trip['id']}"
                )

                if trip["status"] == "approved":

                    st.markdown(
                        '<span class="trip-approved">'
                        '✅ ĐÃ DUYỆT'
                        '</span>',
                        unsafe_allow_html=True
                    )

                elif trip["status"] == "pending":

                    st.markdown(
                        '<span class="trip-pending">'
                        '⏳ CHỜ DUYỆT'
                        '</span>',
                        unsafe_allow_html=True
                    )

                else:

                    st.markdown(
                        '<span class="trip-rejected">'
                        '❌ TỪ CHỐI'
                        '</span>',
                        unsafe_allow_html=True
                    )

                st.write(
                    f"🕒 {trip['created_at']}"
                )

                if trip["note"]:
                    st.write(
                        f"📝 {trip['note']}"
                    )

            st.divider()


# ============================================================
# RANKING
# ============================================================

def ranking():

    st.markdown("""
    <div class="hero">
        <h1>🏆 Bảng xếp hạng</h1>
        <p>Top tài xế có nhiều chuyến nhất</p>
    </div>
    """, unsafe_allow_html=True)

    rows = get_ranking()

    if not rows:
        st.info(
            "Chưa có dữ liệu."
        )
        return

    for index, row in enumerate(
        rows,
        start=1
    ):

        if index == 1:
            medal = "🥇"
        elif index == 2:
            medal = "🥈"
        elif index == 3:
            medal = "🥉"
        else:
            medal = f"#{index}"

        col1, col2, col3 = st.columns(
            [1, 5, 2]
        )

        with col1:
            st.subheader(medal)

        with col2:
            st.write(
                f"**{row['full_name']}**"
            )
            st.caption(
                f"@{row['username']}"
            )

        with col3:
            st.metric(
                "Chuyến",
                row["total"]
            )

        st.divider()


# ============================================================
# ADMIN - USERS
# ============================================================

def admin_users():

    st.markdown("""
    <div class="hero">
        <h1>👥 Duyệt tài khoản</h1>
        <p>Phê duyệt tài xế mới đăng ký</p>
    </div>
    """, unsafe_allow_html=True)

    users = get_pending_users()

    if not users:
        st.success(
            "Không có tài khoản chờ duyệt."
        )
        return

    for user in users:

        col1, col2, col3 = st.columns(
            [3, 2, 2]
        )

        with col1:
            st.write(
                f"**{user['full_name']}**"
            )
            st.caption(
                f"@{user['username']}"
            )

        with col2:
            st.caption(
                user["created_at"]
            )

        with col3:

            if st.button(
                "✅ Duyệt",
                key=f"approve_user_{user['id']}"
            ):
                approve_user(
                    user["id"]
                )
                st.success(
                    "Đã duyệt."
                )
                st.rerun()

        st.divider()


# ============================================================
# ADMIN - TRIPS
# ============================================================

def admin_trips(admin):

    st.markdown("""
    <div class="hero">
        <h1>📸 Duyệt chuyến</h1>
        <p>Kiểm tra ảnh trước khi cộng chuyến</p>
    </div>
    """, unsafe_allow_html=True)

    trips = get_pending_trips()

    if not trips:
        st.success(
            "Không có chuyến chờ duyệt."
        )
        return

    for trip in trips:

        st.markdown(
            f"### 🚕 Chuyến #{trip['id']}"
        )

        st.write(
            f"👤 **{trip['full_name']}** "
            f"(@{trip['username']})"
        )

        if os.path.exists(
            trip["image_path"]
        ):
            st.image(
                trip["image_path"],
                width=500
            )

        if trip["note"]:
            st.write(
                f"📝 {trip['note']}"
            )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "✅ DUYỆT CHUYẾN",
                key=f"approve_trip_{trip['id']}",
                use_container_width=True
            ):

                success, message = approve_trip(
                    trip["id"],
                    admin["id"]
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)

                st.rerun()

        with col2:

            if st.button(
                "❌ TỪ CHỐI",
                key=f"reject_trip_{trip['id']}",
                use_container_width=True
            ):

                reject_trip(
                    trip["id"],
                    admin["id"]
                )

                st.warning(
                    "Đã từ chối chuyến."
                )

                st.rerun()

        st.divider()


# ============================================================
# ADMIN - ALL USERS
# ============================================================

def admin_all_users():

    st.markdown("""
    <div class="hero">
        <h1>👤 Quản lý tài khoản</h1>
        <p>Danh sách toàn bộ tài khoản</p>
    </div>
    """, unsafe_allow_html=True)

    users = get_all_users()

    for user in users:

        col1, col2, col3, col4 = st.columns(
            [3, 2, 2, 1]
        )

        with col1:
            st.write(
                f"**{user['full_name']}**"
            )
            st.caption(
                f"@{user['username']}"
            )

        with col2:
            st.write(
                "👑 Admin"
                if user["role"] == "admin"
                else "🚕 Tài xế"
            )

        with col3:
            st.write(
                "✅ Đã duyệt"
                if user["approved"]
                else "⏳ Chờ duyệt"
            )

        with col4:

            if user["role"] != "admin":

                if st.button(
                    "🗑️",
                    key=f"delete_{user['id']}"
                ):

                    delete_user(
                        user["id"]
                    )

                    st.rerun()

        st.divider()


# ============================================================
# MAIN
# ============================================================

if not st.session_state.logged_in:

    auth_page()

else:

    user = get_user(
        st.session_state.user_id
    )

    if not user:

        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.rerun()

    page = sidebar(user)

    if page == "🏠 Dashboard":

        dashboard(user)

    elif page == "📸 Đăng chuyến":

        upload_trip(user)

    elif page == "📋 Lịch sử chuyến":

        history(user)

    elif page == "🏆 Bảng xếp hạng":

        ranking()

    elif page == "👥 Duyệt tài khoản":

        admin_users()

    elif page == "📸 Duyệt chuyến":

        admin_trips(user)

    elif page == "👤 Quản lý tài khoản":

        admin_all_users()

    st.markdown(
        """
        <div class="footer">
            🚕 TAXI SYSTEM • Powered by Streamlit
        </div>
        """,
        unsafe_allow_html=True
    )