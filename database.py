import sqlite3
import hashlib
from datetime import datetime
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
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            approved INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

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

    # Tạo admin mặc định
    admin = cur.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if not admin:
        cur.execute("""
            INSERT INTO users
            (username, password, full_name, role, approved, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "admin",
            hash_password("admin123"),
            "Administrator",
            "admin",
            1,
            now().isoformat()
        ))

    conn.commit()
    conn.close()


def create_user(username, password, full_name):
    conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO users
            (username, password, full_name, role, approved, created_at)
            VALUES (?, ?, ?, 'user', 0, ?)
        """, (
            username,
            hash_password(password),
            full_name,
            now().isoformat()
        ))

        conn.commit()
        return True, "Đăng ký thành công. Vui lòng chờ admin duyệt."

    except sqlite3.IntegrityError:
        return False, "Tên đăng nhập đã tồn tại."

    finally:
        conn.close()


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
        return None, "Tài khoản chưa được admin duyệt."

    return user, None


def get_user(user_id):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return user


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


def delete_user(user_id):
    conn = get_connection()

    conn.execute(
        "DELETE FROM trips WHERE user_id = ?",
        (user_id,)
    )

    conn.execute(
        "DELETE FROM users WHERE id = ? AND role != 'admin'",
        (user_id,)
    )

    conn.commit()
    conn.close()


def get_today_key():
    current = now()

    # Ngày hệ thống Taxi bắt đầu từ 02:00
    if current.hour < 2:
        from datetime import timedelta
        current = current - timedelta(days=1)

    return current.strftime("%Y-%m-%d")


def get_today_trip_count(user_id):
    conn = get_connection()

    trips = conn.execute("""
        SELECT created_at
        FROM trips
        WHERE user_id = ?
        AND status = 'approved'
    """, (user_id,)).fetchall()

    conn.close()

    count = 0

    for trip in trips:
        try:
            dt = datetime.fromisoformat(trip["created_at"])
            local_dt = dt.astimezone(TZ)

            current = local_dt

            if current.hour < 2:
                from datetime import timedelta
                current = current - timedelta(days=1)

            if current.strftime("%Y-%m-%d") == get_today_key():
                count += 1

        except Exception:
            continue

    return count


def add_trip(user_id, image_path, note):
    if get_today_trip_count(user_id) >= 50:
        return False, "Bạn đã đạt giới hạn 50 chuyến hôm nay."

    conn = get_connection()

    conn.execute("""
        INSERT INTO trips
        (user_id, image_path, note, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
    """, (
        user_id,
        image_path,
        note,
        now().isoformat()
    ))

    conn.commit()
    conn.close()

    return True, "Đã gửi chuyến. Chờ admin duyệt."


def get_pending_trips():
    conn = get_connection()

    trips = conn.execute("""
        SELECT
            trips.*,
            users.username,
            users.full_name
        FROM trips
        JOIN users ON users.id = trips.user_id
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
        return False, "Chuyến này đã được xử lý."

    # Kiểm tra lại giới hạn 50 chuyến
    if get_today_trip_count(trip["user_id"]) >= 50:
        conn.close()
        return False, "Tài xế đã đạt 50 chuyến hôm nay."

    conn.execute("""
        UPDATE trips
        SET status = 'approved',
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
        SET status = 'rejected',
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
    """, (user_id,)).fetchall()

    conn.close()
    return trips


def get_all_users():
    conn = get_connection()

    users = conn.execute("""
        SELECT *
        FROM users
        ORDER BY
            CASE WHEN role = 'admin' THEN 0 ELSE 1 END,
            id DESC
    """).fetchall()

    conn.close()
    return users


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