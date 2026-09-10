import sqlite3
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DB_FILE = "taxi.db"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def now():
    return datetime.now(TZ)


def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # =========================
    # USERS
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            approved INTEGER DEFAULT 0,
            duty INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # =========================
    # TRIPS
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            note TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            approved_at TEXT,
            approved_by INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # =========================
    # POSTS
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            pinned INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    """)

    # =========================
    # WEBSITE SETTINGS
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # =========================
    # ADMIN MẶC ĐỊNH
    # =========================

    admin = cur.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if not admin:
        cur.execute("""
            INSERT INTO users
            (
                username,
                password,
                full_name,
                role,
                approved,
                duty,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "admin",
            hash_password("admin123"),
            "Administrator",
            "admin",
            1,
            0,
            now().isoformat()
        ))

    conn.commit()
    conn.close()


# ============================================================
# LOGIN
# ============================================================

def login_user(username, password):

    conn = get_connection()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE username = ?
        AND password = ?
    """, (
        username,
        hash_password(password)
    )).fetchone()

    conn.close()

    if not user:
        return None, "Sai tài khoản hoặc mật khẩu."

    if not user["approved"]:
        return None, "Tài khoản chưa được Admin duyệt."

    return user, None


def get_user(user_id):

    conn = get_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return user


# ============================================================
# USER REGISTER
# ============================================================

def create_user(username, password, full_name):

    conn = get_connection()

    try:

        conn.execute("""
            INSERT INTO users
            (
                username,
                password,
                full_name,
                role,
                approved,
                duty,
                created_at
            )
            VALUES (?, ?, ?, 'user', 0, 0, ?)
        """, (
            username,
            hash_password(password),
            full_name,
            now().isoformat()
        ))

        conn.commit()

        return True, "Đăng ký thành công. Vui lòng chờ Admin duyệt."

    except sqlite3.IntegrityError:

        return False, "Tên đăng nhập đã tồn tại."

    finally:

        conn.close()


# ============================================================
# ADMIN TẠO ADMIN
# ============================================================

def create_admin_account(username, password, full_name):

    conn = get_connection()

    try:

        conn.execute("""
            INSERT INTO users
            (
                username,
                password,
                full_name,
                role,
                approved,
                duty,
                created_at
            )
            VALUES (?, ?, ?, 'admin', 1, 0, ?)
        """, (
            username,
            hash_password(password),
            full_name,
            now().isoformat()
        ))

        conn.commit()

        return True, "Đã tạo tài khoản Admin thành công."

    except sqlite3.IntegrityError:

        return False, "Tên đăng nhập đã tồn tại."

    finally:

        conn.close()


# ============================================================
# ĐỔI MẬT KHẨU
# ============================================================

def change_password(user_id, new_password):

    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET password = ?
        WHERE id = ?
    """, (
        hash_password(new_password),
        user_id
    ))

    conn.commit()
    conn.close()


# ============================================================
# DUYỆT USER
# ============================================================

def get_pending_users():

    conn = get_connection()

    users = conn.execute("""
        SELECT *
        FROM users
        WHERE role = 'user'
        AND approved = 0
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return users


def approve_user(user_id):

    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET approved = 1
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()


# ============================================================
# QUẢN LÝ USER
# ============================================================

def get_all_users():

    conn = get_connection()

    users = conn.execute("""
        SELECT *
        FROM users
        ORDER BY
            CASE
                WHEN role = 'admin' THEN 0
                ELSE 1
            END,
            id DESC
    """).fetchall()

    conn.close()

    return users


def delete_user(user_id):

    conn = get_connection()

    user = conn.execute(
        "SELECT role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if user and user["role"] != "admin":

        conn.execute(
            "DELETE FROM trips WHERE user_id = ?",
            (user_id,)
        )

        conn.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,)
        )

    conn.commit()
    conn.close()


# ============================================================
# DUTY
# ============================================================

def set_duty(user_id, duty):

    conn = get_connection()

    conn.execute("""
        UPDATE users
        SET duty = ?
        WHERE id = ?
    """, (
        1 if duty else 0,
        user_id
    ))

    conn.commit()
    conn.close()


def get_online_drivers():

    conn = get_connection()

    users = conn.execute("""
        SELECT *
        FROM users
        WHERE role = 'user'
        AND approved = 1
        AND duty = 1
        ORDER BY full_name ASC
    """).fetchall()

    conn.close()

    return users


# ============================================================
# NGÀY HỆ THỐNG
# RESET 02:00
# ============================================================

def get_today_key():

    current = now()

    if current.hour < 2:
        current -= timedelta(days=1)

    return current.strftime("%Y-%m-%d")


def get_today_trip_count(user_id):

    conn = get_connection()

    trips = conn.execute("""
        SELECT created_at
        FROM trips
        WHERE user_id = ?
        AND status = 'approved'
    """, (
        user_id,
    )).fetchall()

    conn.close()

    today_key = get_today_key()

    count = 0

    for trip in trips:

        try:

            dt = datetime.fromisoformat(
                trip["created_at"]
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)

            if dt.hour < 2:
                dt -= timedelta(days=1)

            if dt.strftime("%Y-%m-%d") == today_key:
                count += 1

        except Exception:
            pass

    return count


# ============================================================
# TRIPS
# ============================================================

def add_trip(user_id, image_path, note):

    if get_today_trip_count(user_id) >= 50:
        return False, "Bạn đã đạt tối đa 50 chuyến hôm nay."

    conn = get_connection()

    conn.execute("""
        INSERT INTO trips
        (
            user_id,
            image_path,
            note,
            status,
            created_at
        )
        VALUES (?, ?, ?, 'pending', ?)
    """, (
        user_id,
        image_path,
        note,
        now().isoformat()
    ))

    conn.commit()
    conn.close()

    return True, "Đã gửi chuyến, chờ Admin duyệt."


def get_pending_trips():

    conn = get_connection()

    trips = conn.execute("""
        SELECT
            trips.*,
            users.username,
            users.full_name
        FROM trips
        JOIN users
        ON users.id = trips.user_id
        WHERE trips.status = 'pending'
        ORDER BY trips.id DESC
    """).fetchall()

    conn.close()

    return trips


def approve_trip(trip_id, admin_id):

    conn = get_connection()

    trip = conn.execute(
        "SELECT * FROM trips WHERE id = ?",
        (trip_id,)
    ).fetchone()

    if not trip:
        conn.close()
        return False, "Không tìm thấy chuyến."

    if trip["status"] != "pending":
        conn.close()
        return False, "Chuyến đã được xử lý."

    if get_today_trip_count(
        trip["user_id"]
    ) >= 50:

        conn.close()

        return False, "Tài xế đã đạt 50 chuyến hôm nay."

    conn.execute("""
        UPDATE trips
        SET
            status = 'approved',
            approved_at = ?,
            approved_by = ?
        WHERE id = ?
    """, (
        now().isoformat(),
        admin_id,
        trip_id
    ))

    conn.commit()
    conn.close()

    return True, "Đã duyệt chuyến."


def reject_trip(trip_id, admin_id):

    conn = get_connection()

    conn.execute("""
        UPDATE trips
        SET
            status = 'rejected',
            approved_at = ?,
            approved_by = ?
        WHERE id = ?
        AND status = 'pending'
    """, (
        now().isoformat(),
        admin_id,
        trip_id
    ))

    conn.commit()
    conn.close()


def get_user_trips(user_id):

    conn = get_connection()

    trips = conn.execute("""
        SELECT *
        FROM trips
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        user_id,
    )).fetchall()

    conn.close()

    return trips


# ============================================================
# RANKING
# ============================================================

def get_ranking():

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            users.id,
            users.username,
            users.full_name,
            COUNT(trips.id) AS total
        FROM users
        LEFT JOIN trips
        ON users.id = trips.user_id
        AND trips.status = 'approved'
        WHERE users.role = 'user'
        AND users.approved = 1
        GROUP BY users.id
        ORDER BY total DESC
    """).fetchall()

    conn.close()

    return rows


# ============================================================
# POSTS
# ============================================================

def create_post(
    title,
    content,
    image_path,
    admin_id,
    pinned=False
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO posts
        (
            title,
            content,
            image_path,
            pinned,
            created_by,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        title,
        content,
        image_path,
        1 if pinned else 0,
        admin_id,
        now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_posts():

    conn = get_connection()

    posts = conn.execute("""
        SELECT *
        FROM posts
        ORDER BY pinned DESC, id DESC
    """).fetchall()

    conn.close()

    return posts


def delete_post(post_id):

    conn = get_connection()

    conn.execute(
        "DELETE FROM posts WHERE id = ?",
        (post_id,)
    )

    conn.commit()
    conn.close()


# ============================================================
# SETTINGS
# ============================================================

def get_setting(key, default=""):

    conn = get_connection()

    row = conn.execute("""
        SELECT value
        FROM settings
        WHERE key = ?
    """, (
        key,
    )).fetchone()

    conn.close()

    if row:
        return row["value"]

    return default


def set_setting(key, value):

    conn = get_connection()

    conn.execute("""
        INSERT INTO settings
        (
            key,
            value
        )
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (
        key,
        value
    ))

    conn.commit()
    conn.close()