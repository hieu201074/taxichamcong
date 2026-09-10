import streamlit as st
import sqlite3
import os
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ============================================================
# CẤU HÌNH
# ============================================================

st.set_page_config(
    page_title="Los Santos Taxi",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "taxi.db"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def db_connect():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            approved INTEGER DEFAULT 0,
            duty INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            image TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            approved_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            image TEXT,
            pinned INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Admin mặc định
    cur.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",)
    )

    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users
            (username, password, full_name, role, approved, duty, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "admin",
            hash_password("admin123"),
            "Administrator",
            "admin",
            1,
            0,
            now_str()
        ))

    # Cài đặt mặc định
    defaults = {
        "site_title": "LOS SANTOS TAXI",
        "site_subtitle": "TAXI DISPATCH SYSTEM",
        "home_text": "Hệ thống quản lý tài xế Taxi Los Santos",
        "contact": "Liên hệ quản lý Taxi để được hỗ trợ.",
    }

    for key, value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
            (key, value)
        )

    conn.commit()
    conn.close()


# ============================================================
# TIỆN ÍCH
# ============================================================

def now():
    return datetime.now(TZ)


def now_str():
    return now().isoformat()


def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def verify_password(password, hashed):
    return hash_password(password) == hashed


def get_setting(key, default=""):
    conn = db_connect()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,)
    ).fetchone()
    conn.close()

    if row:
        return row["value"]

    return default


def set_setting(key, value):
    conn = db_connect()
    conn.execute("""
        INSERT INTO settings(key,value)
        VALUES (?,?)
        ON CONFLICT(key)
        DO UPDATE SET value=excluded.value
    """, (key, value))
    conn.commit()
    conn.close()


# ============================================================
# USER
# ============================================================

def register_user(username, password, full_name):
    username = username.strip()
    full_name = full_name.strip()

    if not username or not password or not full_name:
        return False, "Vui lòng nhập đầy đủ thông tin."

    if len(username) < 3:
        return False, "Tên tài khoản phải có ít nhất 3 ký tự."

    if len(password) < 4:
        return False, "Mật khẩu phải có ít nhất 4 ký tự."

    conn = db_connect()

    try:
        conn.execute("""
            INSERT INTO users
            (username,password,full_name,role,approved,duty,created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            username,
            hash_password(password),
            full_name,
            "user",
            0,
            0,
            now_str()
        ))

        conn.commit()
        return True, "Đăng ký thành công. Vui lòng chờ Admin duyệt."

    except sqlite3.IntegrityError:
        return False, "Tên tài khoản đã tồn tại."

    finally:
        conn.close()


def login_user(username, password):
    conn = db_connect()

    row = conn.execute("""
        SELECT *
        FROM users
        WHERE username = ?
    """, (username.strip(),)).fetchone()

    conn.close()

    if not row:
        return None, "Tài khoản hoặc mật khẩu không đúng."

    if not verify_password(password, row["password"]):
        return None, "Tài khoản hoặc mật khẩu không đúng."

    if not row["approved"]:
        return None, "Tài khoản chưa được Admin duyệt."

    return dict(row), None


def get_user(user_id):
    conn = db_connect()

    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return dict(row) if row else None


def get_users():
    conn = db_connect()

    rows = conn.execute("""
        SELECT *
        FROM users
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(x) for x in rows]


def approve_user(user_id):
    conn = db_connect()

    conn.execute("""
        UPDATE users
        SET approved = 1
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()


def reject_user(user_id):
    conn = db_connect()

    conn.execute("""
        DELETE FROM users
        WHERE id = ?
        AND role = 'user'
    """, (user_id,))

    conn.commit()
    conn.close()


def create_admin(username, password, full_name):
    username = username.strip()
    full_name = full_name.strip()

    if not username or not password or not full_name:
        return False, "Vui lòng nhập đầy đủ."

    conn = db_connect()

    try:
        conn.execute("""
            INSERT INTO users
            (username,password,full_name,role,approved,duty,created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            username,
            hash_password(password),
            full_name,
            "admin",
            1,
            0,
            now_str()
        ))

        conn.commit()
        return True, "Đã tạo tài khoản Admin."

    except sqlite3.IntegrityError:
        return False, "Tài khoản đã tồn tại."

    finally:
        conn.close()


def delete_user(user_id):
    conn = db_connect()

    conn.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()


# ============================================================
# DUTY
# ============================================================

def set_duty(user_id, status):
    conn = db_connect()

    conn.execute("""
        UPDATE users
        SET duty = ?
        WHERE id = ?
    """, (1 if status else 0, user_id))

    conn.commit()
    conn.close()


def get_online_drivers():
    conn = db_connect()

    rows = conn.execute("""
        SELECT *
        FROM users
        WHERE role = 'user'
        AND approved = 1
        AND duty = 1
        ORDER BY full_name
    """).fetchall()

    conn.close()

    return [dict(x) for x in rows]


# ============================================================
# NGÀY TÍNH CHUYẾN
# RESET LÚC 02:00
# ============================================================

def taxi_day():
    current = now()

    if current.hour < 2:
        return (current - timedelta(days=1)).date()

    return current.date()


def get_trip_count(user_id):
    conn = db_connect()

    rows = conn.execute("""
        SELECT created_at
        FROM trips
        WHERE user_id = ?
        AND status = 'approved'
    """, (user_id,)).fetchall()

    conn.close()

    total = 0
    target_day = taxi_day()

    for row in rows:
        try:
            dt = datetime.fromisoformat(row["created_at"])

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)

            if dt.astimezone(TZ).date() == target_day:
                total += 1

        except Exception:
            pass

    return total


# ============================================================
# CHUYẾN XE
# ============================================================

def add_trip(user_id, image_path):
    today_count = get_trip_count(user_id)

    if today_count >= 50:
        return False, "Bạn đã đạt giới hạn 50 chuyến trong ngày."

    conn = db_connect()

    conn.execute("""
        INSERT INTO trips
        (user_id,image,status,created_at)
        VALUES (?,?,?,?,?)
    """, (
        user_id,
        image_path,
        "pending",
        now_str()
    ))

    conn.commit()
    conn.close()

    return True, "Đã gửi chuyến xe. Chờ Admin duyệt."


def get_user_trips(user_id):
    conn = db_connect()

    rows = conn.execute("""
        SELECT *
        FROM trips
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return [dict(x) for x in rows]


def get_all_trips():
    conn = db_connect()

    rows = conn.execute("""
        SELECT
            trips.*,
            users.username,
            users.full_name
        FROM trips
        JOIN users
        ON users.id = trips.user_id
        ORDER BY trips.id DESC
    """).fetchall()

    conn.close()

    return [dict(x) for x in rows]


def approve_trip(trip_id):
    conn = db_connect()

    row = conn.execute("""
        SELECT user_id
        FROM trips
        WHERE id = ?
    """, (trip_id,)).fetchone()

    if not row:
        conn.close()
        return False, "Không tìm thấy chuyến."

    user_id = row["user_id"]

    conn.execute("""
        UPDATE trips
        SET status = 'approved',
            approved_at = ?
        WHERE id = ?
    """, (now_str(), trip_id))

    conn.commit()
    conn.close()

    return True, "Đã duyệt chuyến."


def reject_trip(trip_id):
    conn = db_connect()

    conn.execute("""
        UPDATE trips
        SET status = 'rejected'
        WHERE id = ?
    """, (trip_id,))

    conn.commit()
    conn.close()


# ============================================================
# BXH
# ============================================================

def get_leaderboard():
    users = get_users()

    result = []

    for user in users:
        if user["role"] != "user":
            continue

        total = get_total_approved_trips(user["id"])

        result.append({
            "name": user["full_name"],
            "username": user["username"],
            "trips": total,
            "duty": user["duty"]
        })

    result.sort(
        key=lambda x: x["trips"],
        reverse=True
    )

    return result


def get_total_approved_trips(user_id):
    conn = db_connect()

    row = conn.execute("""
        SELECT COUNT(*) AS total
        FROM trips
        WHERE user_id = ?
        AND status = 'approved'
    """, (user_id,)).fetchone()

    conn.close()

    return row["total"] if row else 0


# ============================================================
# POSTS
# ============================================================

def create_post(title, content, image):
    conn = db_connect()

    conn.execute("""
        INSERT INTO posts
        (title,content,image,pinned,created_at)
        VALUES (?,?,?,?,?)
    """, (
        title,
        content,
        image,
        0,
        now_str()
    ))

    conn.commit()
    conn.close()


def get_posts():
    conn = db_connect()

    rows = conn.execute("""
        SELECT *
        FROM posts
        ORDER BY pinned DESC, id DESC
    """).fetchall()

    conn.close()

    return [dict(x) for x in rows]


def delete_post(post_id):
    conn = db_connect()

    conn.execute(
        "DELETE FROM posts WHERE id = ?",
        (post_id,)
    )

    conn.commit()
    conn.close()


def toggle_pin(post_id, current):
    conn = db_connect()

    conn.execute("""
        UPDATE posts
        SET pinned = ?
        WHERE id = ?
    """, (0 if current else 1, post_id))

    conn.commit()
    conn.close()


# ============================================================
# CSS
# ============================================================

def load_css():
    st.markdown("""
    <style>

    @import url(
        'https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap'
    );

    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(
                circle at top right,
                rgba(255,193,7,.12),
                transparent 35%
            ),
            #080b10;
        color: #fff;
    }

    .block-container {
        max-width: 1400px;
        padding-top: 2rem;
    }

    [data-testid="stSidebar"] {
        background: #0b0f15;
        border-right: 1px solid #282d35;
    }

    [data-testid="stSidebar"] * {
        color: #fff !important;
    }

    h1, h2, h3, h4, p, label {
        color: #fff !important;
    }

    .taxi-header {
        background:
            linear-gradient(
                135deg,
                #171b21,
                #090b0e
            );
        border: 1px solid #343941;
        border-left: 5px solid #ffc107;
        padding: 22px;
        border-radius: 15px;
        margin-bottom: 20px;
    }

    .taxi-logo {
        font-size: 35px;
        font-weight: 900;
        color: #ffc107;
    }

    .taxi-title {
        font-size: 27px;
        font-weight: 900;
        color: #fff;
    }

    .taxi-subtitle {
        color: #8f98a5;
        font-size: 12px;
        letter-spacing: 2px;
    }

    .stat-card {
        background: #11161d;
        border: 1px solid #2b3139;
        border-radius: 14px;
        padding: 20px;
        min-height: 125px;
    }

    .stat-number {
        font-size: 31px;
        font-weight: 900;
        color: #ffc107;
    }

    .stat-label {
        color: #8d96a3;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .hero {
        background:
            linear-gradient(
                135deg,
                rgba(255,193,7,.20),
                rgba(20,20,20,.95)
            );
        border: 1px solid #6e5710;
        border-radius: 18px;
        padding: 35px;
        margin-bottom: 20px;
    }

    .hero-title {
        color: #ffc107;
        font-size: 35px;
        font-weight: 900;
    }

    .hero-text {
        color: #c5cbd3;
        font-size: 14px;
    }

    .online-box {
        background: #0d1711;
        border: 1px solid #1d6b35;
        border-radius: 14px;
        padding: 18px;
    }

    .offline-box {
        background: #17100e;
        border: 1px solid #5e301d;
        border-radius: 14px;
        padding: 18px;
    }

    .post-card {
        background: #11161d;
        border: 1px solid #2a3038;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 15px;
    }

    .post-title {
        color: #ffc107;
        font-weight: 800;
        font-size: 19px;
    }

    .login-box {
        max-width: 480px;
        margin: 70px auto;
        background: #11161d;
        border: 1px solid #353b43;
        border-top: 5px solid #ffc107;
        padding: 35px;
        border-radius: 18px;
        box-shadow: 0 15px 50px rgba(0,0,0,.5);
    }

    .login-logo {
        text-align: center;
        color: #ffc107;
        font-size: 45px;
        font-weight: 900;
    }

    .login-title {
        text-align: center;
        font-size: 24px;
        font-weight: 900;
        color: #fff;
    }

    .login-sub {
        text-align: center;
        color: #89919d;
        font-size: 11px;
        letter-spacing: 2px;
        margin-bottom: 25px;
    }

    .duty-on {
        color: #4ade80;
        font-weight: 800;
    }

    .duty-off {
        color: #f87171;
        font-weight: 800;
    }

    .footer {
        text-align: center;
        color: #66707c;
        font-size: 11px;
        margin-top: 50px;
        padding: 20px;
    }

    .stButton > button {
        background: #ffc107 !important;
        color: #080b10 !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 800 !important;
    }

    .stButton > button:hover {
        background: #ffcf3a !important;
    }

    div[data-baseweb="input"] {
        background: #151a21 !important;
    }

    input, textarea {
        color: white !important;
    }

    [data-testid="stFileUploader"] {
        background: #11161d;
        border: 1px dashed #4a5059;
        border-radius: 12px;
        padding: 10px;
    }

    </style>
    """, unsafe_allow_html=True)


# ============================================================
# LOGIN
# ============================================================

def login_page():

    st.markdown("""
    <div class="login-box">

        <div class="login-logo">🚕</div>

        <div class="login-title">
            LOS SANTOS TAXI
        </div>

        <div class="login-sub">
            TAXI DISPATCH MANAGEMENT SYSTEM
        </div>

    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs([
        "🔐 ĐĂNG NHẬP",
        "📝 ĐĂNG KÝ"
    ])

    with tab_login:

        with st.form("login_form"):

            username = st.text_input(
                "Tài khoản",
                placeholder="Nhập tài khoản"
            )

            password = st.text_input(
                "Mật khẩu",
                type="password",
                placeholder="Nhập mật khẩu"
            )

            submit = st.form_submit_button(
                "ĐĂNG NHẬP",
                use_container_width=True
            )

            if submit:

                user, error = login_user(
                    username,
                    password
                )

                if error:
                    st.error(error)

                else:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()

    with tab_register:

        with st.form("register_form"):

            full_name = st.text_input(
                "Họ và tên",
                placeholder="Nguyễn Văn A"
            )

            username = st.text_input(
                "Tài khoản"
            )

            password = st.text_input(
                "Mật khẩu",
                type="password"
            )

            password2 = st.text_input(
                "Nhập lại mật khẩu",
                type="password"
            )

            submit = st.form_submit_button(
                "ĐĂNG KÝ TÀI KHOẢN",
                use_container_width=True
            )

            if submit:

                if password != password2:
                    st.error("Hai mật khẩu không giống nhau.")

                else:

                    ok, message = register_user(
                        username,
                        password,
                        full_name
                    )

                    if ok:
                        st.success(message)

                    else:
                        st.error(message)


# ============================================================
# SIDEBAR
# ============================================================

def sidebar():

    user = st.session_state.user

    with st.sidebar:

        st.markdown("""
        <div style="
            text-align:center;
            padding:15px;
            border-bottom:1px solid #292f37;
            margin-bottom:20px;
        ">
            <div style="
                font-size:45px;
            ">🚕</div>

            <div style="
                color:#ffc107;
                font-size:18px;
                font-weight:900;
            ">
                LOS SANTOS TAXI
            </div>

            <div style="
                color:#69727e;
                font-size:10px;
                letter-spacing:2px;
            ">
                DISPATCH SYSTEM
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            f"### 👤 {user['full_name']}"
        )

        if user["role"] == "admin":
            st.caption("🛡️ ADMINISTRATOR")
        else:
            st.caption("🚕 TAXI DRIVER")

        st.markdown("---")

        menu = st.radio(
            "MENU",
            [
                "🏠 Tổng quan",
                "📸 Đăng ảnh +1 chuyến",
                "🏆 BXH tài xế",
                "📋 Lịch sử chuyến",
                "📢 Thông báo",
            ]
            + (
                [
                    "🛠️ ADMIN"
                ]
                if user["role"] == "admin"
                else []
            )
        )

        st.markdown("---")

        current = get_user(user["id"])

        if current and current["duty"]:

            st.markdown("""
            <div class="online-box">
                <div class="duty-on">
                    🟢 ĐANG ON DUTY
                </div>
                <div style="color:#8b969f;font-size:11px;">
                    Bạn đang nhận chuyến
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                "🔴 OFF DUTY",
                use_container_width=True
            ):
                set_duty(user["id"], False)
                st.session_state.user = get_user(user["id"])
                st.rerun()

        else:

            st.markdown("""
            <div class="offline-box">
                <div class="duty-off">
                    🔴 ĐANG OFF DUTY
                </div>
                <div style="color:#8b969f;font-size:11px;">
                    Bạn chưa nhận chuyến
                </div>
            </div>
            """, unsafe_allow_html=True)

            if user["role"] != "admin":

                if st.button(
                    "🟢 ON DUTY",
                    use_container_width=True
                ):
                    set_duty(user["id"], True)
                    st.session_state.user = get_user(user["id"])
                    st.rerun()

        st.markdown("---")

        if st.button(
            "🚪 ĐĂNG XUẤT",
            use_container_width=True
        ):
            st.session_state.clear()
            st.rerun()

    return menu


# ============================================================
# HEADER
# ============================================================

def page_header():

    title = get_setting(
        "site_title",
        "LOS SANTOS TAXI"
    )

    subtitle = get_setting(
        "site_subtitle",
        "TAXI DISPATCH SYSTEM"
    )

    st.markdown(f"""
    <div class="taxi-header">

        <div class="taxi-logo">
            🚕 {title}
        </div>

        <div class="taxi-title">
            {subtitle}
        </div>

        <div class="taxi-subtitle">
            LOS SANTOS • TAXI MANAGEMENT
        </div>

    </div>
    """, unsafe_allow_html=True)


# ============================================================
# TỔNG QUAN
# ============================================================

def page_dashboard():

    user = st.session_state.user

    today = get_trip_count(user["id"])
    total = get_total_approved_trips(user["id"])
    online = len(get_online_drivers())

    st.markdown("""
    <div class="hero">

        <div class="hero-title">
            🚕 XIN CHÀO, TÀI XẾ
        </div>

        <div class="hero-text">
            Quản lý chuyến xe và trạng thái làm việc
            trên hệ thống Los Santos Taxi.
        </div>

    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{today}/50</div>
            <div class="stat-label">
                Chuyến hôm nay
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{total}</div>
            <div class="stat-label">
                Tổng chuyến
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{online}</div>
            <div class="stat-label">
                Tài xế ON DUTY
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        remaining = max(0, 50 - today)

        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{remaining}</div>
            <div class="stat-label">
                Chuyến còn lại
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("## 📢 BÀI ĐĂNG MỚI")

    posts = get_posts()

    if not posts:
        st.info("Chưa có bài đăng nào.")

    for post in posts[:5]:

        st.markdown(
            f"""
            <div class="post-card">

                <div class="post-title">
                    {"📌 " if post["pinned"] else ""}
                    {post["title"]}
                </div>

                <div style="
                    color:#9ba4ae;
                    font-size:11px;
                    margin:5px 0 15px;
                ">
                    {post["created_at"][:16].replace("T"," ")}
                </div>

                <div style="color:#ddd;">
                    {post["content"] or ""}
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        if post["image"] and os.path.exists(post["image"]):
            st.image(
                post["image"],
                use_container_width=True
            )


# ============================================================
# ĐĂNG ẢNH CHUYẾN
# ============================================================

def page_upload():

    user = st.session_state.user

    count = get_trip_count(user["id"])

    st.markdown("""
    <div class="hero">

        <div class="hero-title">
            📸 ĐĂNG ẢNH CHUYẾN ĐI
        </div>

        <div class="hero-text">
            Tải ảnh bằng chứng chuyến xe.
            Sau khi Admin duyệt, hệ thống sẽ cộng +1 chuyến.
        </div>

    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"### 🚕 Tiến độ hôm nay: `{count}/50` chuyến"
    )

    if count >= 50:

        st.error(
            "🚫 Bạn đã đạt tối đa 50 chuyến trong ngày."
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

    if uploaded:

        st.image(
            uploaded,
            caption="Ảnh chuyến xe",
            use_container_width=True
        )

        st.info(
            "Ảnh sẽ ở trạng thái CHỜ DUYỆT cho tới khi Admin kiểm tra."
        )

        if st.button(
            "🚕 GỬI ẢNH +1 CHUYẾN",
            use_container_width=True
        ):

            extension = uploaded.name.split(".")[-1]

            filename = (
                f"{user['id']}_"
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
                f".{extension}"
            )

            path = os.path.join(
                UPLOAD_DIR,
                filename
            )

            with open(path, "wb") as f:
                f.write(uploaded.getbuffer())

            ok, message = add_trip(
                user["id"],
                path
            )

            if ok:
                st.success(message)
                st.rerun()

            else:
                st.error(message)


# ============================================================
# LỊCH SỬ
# ============================================================

def page_history():

    user = st.session_state.user

    trips = get_user_trips(user["id"])

    st.markdown("## 📋 LỊCH SỬ CHUYẾN XE")

    if not trips:
        st.info("Bạn chưa có chuyến xe nào.")
        return

    for trip in trips:

        if trip["status"] == "approved":
            status = "🟢 ĐÃ DUYỆT"

        elif trip["status"] == "rejected":
            status = "🔴 TỪ CHỐI"

        else:
            status = "🟡 CHỜ DUYỆT"

        with st.container(border=True):

            c1, c2 = st.columns([1, 2])

            with c1:

                if (
                    trip["image"]
                    and os.path.exists(trip["image"])
                ):
                    st.image(
                        trip["image"],
                        use_container_width=True
                    )

            with c2:

                st.markdown(
                    f"### 🚕 Chuyến #{trip['id']}"
                )

                st.write(
                    f"**Trạng thái:** {status}"
                )

                st.write(
                    f"**Thời gian:** "
                    f"{trip['created_at'][:19].replace('T',' ')}"
                )

                if trip["approved_at"]:
                    st.write(
                        f"**Duyệt:** "
                        f"{trip['approved_at'][:19].replace('T',' ')}"
                    )


# ============================================================
# BXH
# ============================================================

def page_leaderboard():

    st.markdown("## 🏆 BẢNG XẾP HẠNG TÀI XẾ")

    board = get_leaderboard()

    if not board:
        st.info("Chưa có dữ liệu.")
        return

    for index, driver in enumerate(board, start=1):

        if index == 1:
            medal = "🥇"
        elif index == 2:
            medal = "🥈"
        elif index == 3:
            medal = "🥉"
        else:
            medal = f"#{index}"

        duty = (
            "🟢 ON DUTY"
            if driver["duty"]
            else "🔴 OFF DUTY"
        )

        st.markdown(f"""
        <div class="post-card">

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
            ">

                <div>
                    <span style="
                        color:#ffc107;
                        font-size:23px;
                        font-weight:900;
                    ">
                        {medal}
                    </span>

                    <span style="
                        color:white;
                        font-size:18px;
                        font-weight:800;
                        margin-left:12px;
                    ">
                        {driver["name"]}
                    </span>
                </div>

                <div style="
                    color:#ffc107;
                    font-weight:900;
                ">
                    {driver["trips"]} CHUYẾN
                </div>

            </div>

            <div style="
                color:#8d96a3;
                font-size:11px;
                margin-top:8px;
            ">
                @{driver["username"]} • {duty}
            </div>

        </div>
        """, unsafe_allow_html=True)


# ============================================================
# THÔNG BÁO
# ============================================================

def page_posts():

    st.markdown("## 📢 THÔNG BÁO")

    posts = get_posts()

    if not posts:
        st.info("Chưa có thông báo.")
        return

    for post in posts:

        title = (
            f"📌 {post['title']}"
            if post["pinned"]
            else post["title"]
        )

        st.markdown(
            f"### {title}"
        )

        st.caption(
            post["created_at"][:19].replace(
                "T",
                " "
            )
        )

        st.write(post["content"])

        if (
            post["image"]
            and os.path.exists(post["image"])
        ):
            st.image(
                post["image"],
                use_container_width=True
            )

        st.markdown("---")


# ============================================================
# ADMIN
# ============================================================

def admin_page():

    st.markdown("## 🛠️ ADMIN CONTROL PANEL")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 TÀI KHOẢN",
        "🚕 DUYỆT CHUYẾN",
        "📢 ĐĂNG BÀI",
        "🟢 ON DUTY",
        "⚙️ SỬA WEBSITE"
    ])

    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

    with tab1:

        st.markdown("### 👤 TẠO TÀI KHOẢN ADMIN")

        with st.form("create_admin"):

            username = st.text_input(
                "Tên Admin"
            )

            full_name = st.text_input(
                "Họ tên"
            )

            password = st.text_input(
                "Mật khẩu",
                type="password"
            )

            submit = st.form_submit_button(
                "➕ TẠO ADMIN",
                use_container_width=True
            )

            if submit:

                ok, message = create_admin(
                    username,
                    password,
                    full_name
                )

                if ok:
                    st.success(message)
                else:
                    st.error(message)

        st.markdown("---")

        st.markdown("### 👥 TÀI KHOẢN NGƯỜI DÙNG")

        users = get_users()

        for user in users:

            with st.container(border=True):

                c1, c2, c3, c4 = st.columns(
                    [2, 2, 1, 1]
                )

                with c1:
                    st.write(
                        f"**{user['full_name']}**"
                    )
                    st.caption(
                        f"@{user['username']}"
                    )

                with c2:

                    if user["role"] == "admin":
                        st.write("🛡️ ADMIN")

                    else:
                        if user["approved"]:
                            st.write("🟢 ĐÃ DUYỆT")
                        else:
                            st.write("🟡 CHỜ DUYỆT")

                with c3:

                    if (
                        user["role"] == "user"
                        and not user["approved"]
                    ):

                        if st.button(
                            "DUYỆT",
                            key=f"approve_user_{user['id']}"
                        ):
                            approve_user(
                                user["id"]
                            )
                            st.rerun()

                with c4:

                    if user["username"] != "admin":

                        if st.button(
                            "XÓA",
                            key=f"delete_user_{user['id']}"
                        ):
                            delete_user(
                                user["id"]
                            )
                            st.rerun()

    # --------------------------------------------------------
    # TRIPS
    # --------------------------------------------------------

    with tab2:

        st.markdown("### 🚕 DUYỆT CHUYẾN XE")

        trips = get_all_trips()

        pending = [
            x for x in trips
            if x["status"] == "pending"
        ]

        if not pending:
            st.success(
                "Không có chuyến nào đang chờ duyệt."
            )

        for trip in pending:

            with st.container(border=True):

                st.markdown(
                    f"### 🚕 Chuyến #{trip['id']}"
                )

                st.write(
                    f"**Tài xế:** "
                    f"{trip['full_name']} "
                    f"(@{trip['username']})"
                )

                if (
                    trip["image"]
                    and os.path.exists(trip["image"])
                ):
                    st.image(
                        trip["image"],
                        use_container_width=True
                    )

                c1, c2 = st.columns(2)

                with c1:

                    if st.button(
                        "✅ DUYỆT +1 CHUYẾN",
                        key=f"approve_trip_{trip['id']}",
                        use_container_width=True
                    ):

                        ok, message = approve_trip(
                            trip["id"]
                        )

                        if ok:
                            st.success(message)
                        else:
                            st.error(message)

                        st.rerun()

                with c2:

                    if st.button(
                        "❌ TỪ CHỐI",
                        key=f"reject_trip_{trip['id']}",
                        use_container_width=True
                    ):

                        reject_trip(
                            trip["id"]
                        )

                        st.warning(
                            "Đã từ chối chuyến."
                        )

                        st.rerun()

    # --------------------------------------------------------
    # POSTS
    # --------------------------------------------------------

    with tab3:

        st.markdown("### 📢 ĐĂNG BÀI LÊN WEBSITE")

        with st.form("create_post"):

            title = st.text_input(
                "Tiêu đề"
            )

            content = st.text_area(
                "Nội dung",
                height=180
            )

            image = st.file_uploader(
                "Ảnh bài đăng",
                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp"
                ],
                key="post_image"
            )

            submit = st.form_submit_button(
                "📢 ĐĂNG BÀI",
                use_container_width=True
            )

            if submit:

                if not title.strip():
                    st.error(
                        "Vui lòng nhập tiêu đề."
                    )

                else:

                    image_path = ""

                    if image:

                        extension = (
                            image.name.split(".")[-1]
                        )

                        filename = (
                            "post_"
                            + datetime.now().strftime(
                                "%Y%m%d%H%M%S"
                            )
                            + "."
                            + extension
                        )

                        image_path = os.path.join(
                            UPLOAD_DIR,
                            filename
                        )

                        with open(
                            image_path,
                            "wb"
                        ) as f:
                            f.write(
                                image.getbuffer()
                            )

                    create_post(
                        title,
                        content,
                        image_path
                    )

                    st.success(
                        "Đã đăng bài."
                    )

                    st.rerun()

        st.markdown("---")

        st.markdown("### 🗑️ QUẢN LÝ BÀI ĐĂNG")

        posts = get_posts()

        for post in posts:

            with st.container(border=True):

                st.write(
                    f"**{post['title']}**"
                )

                st.caption(
                    post["created_at"][:19]
                )

                c1, c2 = st.columns(2)

                with c1:

                    text = (
                        "📌 BỎ GHIM"
                        if post["pinned"]
                        else "📌 GHIM BÀI"
                    )

                    if st.button(
                        text,
                        key=f"pin_{post['id']}"
                    ):

                        toggle_pin(
                            post["id"],
                            post["pinned"]
                        )

                        st.rerun()

                with c2:

                    if st.button(
                        "🗑️ XÓA",
                        key=f"delete_post_{post['id']}"
                    ):

                        delete_post(
                            post["id"]
                        )

                        st.rerun()

    # --------------------------------------------------------
    # ON DUTY
    # --------------------------------------------------------

    with tab4:

        st.markdown("### 🟢 TÀI XẾ ĐANG ON DUTY")

        drivers = get_online_drivers()

        if not drivers:
            st.info(
                "Hiện không có tài xế nào ON DUTY."
            )

        for driver in drivers:

            st.markdown(f"""
            <div class="online-box"
                 style="margin-bottom:10px;">

                <div style="
                    color:white;
                    font-size:17px;
                    font-weight:800;
                ">
                    🟢 {driver["full_name"]}
                </div>

                <div style="
                    color:#7d8792;
                    font-size:11px;
                ">
                    @{driver["username"]}
                </div>

            </div>
            """, unsafe_allow_html=True)

    # --------------------------------------------------------
    # WEBSITE SETTINGS
    # --------------------------------------------------------

    with tab5:

        st.markdown(
            "### ⚙️ CHỈNH SỬA WEBSITE"
        )

        current_title = get_setting(
            "site_title"
        )

        current_subtitle = get_setting(
            "site_subtitle"
        )

        current_home = get_setting(
            "home_text"
        )

        current_contact = get_setting(
            "contact"
        )

        with st.form("website_settings"):

            new_title = st.text_input(
                "Tên website",
                value=current_title
            )

            new_subtitle = st.text_input(
                "Tiêu đề phụ",
                value=current_subtitle
            )

            new_home = st.text_area(
                "Nội dung trang chủ",
                value=current_home
            )

            new_contact = st.text_area(
                "Thông tin liên hệ",
                value=current_contact
            )

            save = st.form_submit_button(
                "💾 LƯU THAY ĐỔI",
                use_container_width=True
            )

            if save:

                set_setting(
                    "site_title",
                    new_title
                )

                set_setting(
                    "site_subtitle",
                    new_subtitle
                )

                set_setting(
                    "home_text",
                    new_home
                )

                set_setting(
                    "contact",
                    new_contact
                )

                st.success(
                    "Đã cập nhật website."
                )

                st.rerun()


# ============================================================
# MAIN
# ============================================================

def main():

    init_database()
    load_css()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()

        st.markdown("""
        <div class="footer">
            🚕 LOS SANTOS TAXI • TAXI DISPATCH SYSTEM
        </div>
        """, unsafe_allow_html=True)

        return

    menu = sidebar()

    page_header()

    if menu == "🏠 Tổng quan":
        page_dashboard()

    elif menu == "📸 Đăng ảnh +1 chuyến":
        page_upload()

    elif menu == "🏆 BXH tài xế":
        page_leaderboard()

    elif menu == "📋 Lịch sử chuyến":
        page_history()

    elif menu == "📢 Thông báo":
        page_posts()

    elif menu == "🛠️ ADMIN":
        if st.session_state.user["role"] == "admin":
            admin_page()
        else:
            st.error("Bạn không có quyền Admin.")

    st.markdown("""
    <div class="footer">
        🚕 LOS SANTOS TAXI
        • Hệ thống đang hoạt động
        • Daily reset: 02:00 GMT+7
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()