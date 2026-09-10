import sqlite3
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DB_FILE = "taxi.db"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Quyền mặc định. Có thể tạo thêm role/quyền từ giao diện Admin.
DEFAULT_PERMISSIONS = {
    "view_dashboard": "Xem tổng quan",
    "submit_trip": "Gửi ảnh chuyến",
    "view_history": "Xem lịch sử chuyến",
    "view_leaderboard": "Xem BXH",
    "view_posts": "Xem thông báo",
    "manage_users": "Tạo/sửa/xóa tài khoản",
    "manage_roles": "Quản lý role & quyền",
    "approve_users": "Duyệt tài khoản",
    "approve_trips": "Duyệt chuyến",
    "manage_posts": "Quản lý bài đăng",
    "manage_website": "Chỉnh sửa website",
    "manage_media": "Quản lý ảnh/banner",
    "view_duty": "Xem tài xế ON DUTY",
    "manage_duty": "Quản lý trạng thái duty",
}

DEFAULT_ROLES = {
    "admin": {
        "name": "Quản trị viên Taxi Cầu Vồng",
        "description": "Toàn quyền hệ thống",
        "permissions": list(DEFAULT_PERMISSIONS.keys()),
    },
    "manager": {
        "name": "Quản lý Taxi Cầu Vồng",
        "description": "Quản lý tài xế, chuyến và bài đăng",
        "permissions": [
            "view_dashboard", "submit_trip", "view_history", "view_leaderboard",
            "view_posts", "manage_users", "approve_users", "approve_trips",
            "manage_posts", "view_duty", "manage_duty",
        ],
    },
    "driver": {
        "name": "Tài xế Taxi Cầu Vồng",
        "description": "Tài khoản tài xế",
        "permissions": [
            "view_dashboard", "submit_trip", "view_history",
            "view_leaderboard", "view_posts",
        ],
    },
    # Giữ tương thích tài khoản cũ có role=user.
    "user": {
        "name": "Tài xế Taxi Cầu Vồng",
        "description": "Role cũ, tương đương tài xế Taxi Cầu Vồng",
        "permissions": [
            "view_dashboard", "submit_trip", "view_history",
            "view_leaderboard", "view_posts",
        ],
    },
}


def now():
    return datetime.now(TZ)


def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_admin_credentials():
    """
    Lấy tài khoản Admin từ Streamlit Secrets trước, sau đó mới fallback
    sang Environment Variables. Không đặt username/password trong source code.
    """
    username = ""
    password = ""

    # Streamlit Cloud: Secrets nằm ngoài source code/GitHub.
    try:
        import streamlit as st
        username = str(st.secrets.get("TAXI_ADMIN_USERNAME", "")).strip()
        password = str(st.secrets.get("TAXI_ADMIN_PASSWORD", ""))
    except Exception:
        pass

    # Hosting khác: hỗ trợ Environment Variables.
    if not username:
        username = os.getenv("TAXI_ADMIN_USERNAME", "").strip()
    if not password:
        password = os.getenv("TAXI_ADMIN_PASSWORD", "")

    return username, password


def verify_password(password, stored_password):
    """Verify both current SHA-256 passwords and legacy plaintext records."""
    if stored_password is None:
        return False
    stored_password = str(stored_password)
    # New accounts use SHA-256.
    if hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_password:
        return True
    # Compatibility with old taxi.db files that stored plaintext passwords.
    return password == stored_password


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(conn, table, column, definition):
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_schema(conn):
    # USERS: tạo mới nếu chưa có, sau đó migrate database cũ.
    conn.execute("""
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
    for col, definition in [
        ("avatar", "TEXT DEFAULT ''"),
        ("active", "INTEGER DEFAULT 1"),
        ("created_by", "INTEGER"),
        ("must_change_password", "INTEGER DEFAULT 0"),
    ]:
        _add_column(conn, "users", col, definition)

    # TRIPS: tương thích cả schema image và image_path.
    conn.execute("""
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
    trip_cols = _columns(conn, "trips")
    if "image_path" not in trip_cols and "image" in trip_cols:
        _add_column(conn, "trips", "image_path", "TEXT")
        conn.execute("UPDATE trips SET image_path = COALESCE(image_path, image)")
    for col, definition in [
        ("note", "TEXT"),
        ("approved_at", "TEXT"),
        ("approved_by", "INTEGER"),
    ]:
        _add_column(conn, "trips", col, definition)

    # POSTS.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            pinned INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    post_cols = _columns(conn, "posts")
    if "image_path" not in post_cols and "image" in post_cols:
        _add_column(conn, "posts", "image_path", "TEXT")
        conn.execute("UPDATE posts SET image_path = COALESCE(image_path, image)")
    for col, definition in [
        ("created_by", "INTEGER"),
        ("pinned", "INTEGER DEFAULT 0"),
    ]:
        _add_column(conn, "posts", col, definition)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Role + permission.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL,
            permission_key TEXT NOT NULL,
            PRIMARY KEY(role_id, permission_key),
            FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE
        )
    """)

    # Danh sách quyền để UI quản lý.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            permission_key TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    # Media: logo/banner/avatar/site image.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_key TEXT UNIQUE NOT NULL,
            path TEXT,
            alt_text TEXT,
            updated_at TEXT NOT NULL
        )
    """)


def _seed_roles(conn):
    for key, data in DEFAULT_ROLES.items():
        conn.execute("""
            INSERT OR IGNORE INTO roles
            (role_key, name, description, created_at)
            VALUES (?, ?, ?, ?)
        """, (key, data["name"], data["description"], now().isoformat()))

    for key, name in DEFAULT_PERMISSIONS.items():
        conn.execute("""
            INSERT OR IGNORE INTO permissions(permission_key, name)
            VALUES (?, ?)
        """, (key, name))

    for role_key, data in DEFAULT_ROLES.items():
        role = conn.execute(
            "SELECT id FROM roles WHERE role_key = ?", (role_key,)
        ).fetchone()
        if not role:
            continue
        for perm in data["permissions"]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions(role_id, permission_key)
                VALUES (?, ?)
            """, (role["id"], perm))


def _seed_settings(conn):
    defaults = {
        "site_title": "TAXI CẦU VỒNG",
        "site_subtitle": "HỆ THỐNG QUẢN LÝ TAXI CẦU VỒNG",
        "home_text": "Hệ thống quản lý tài xế Taxi Cầu Vồng",
        "contact": "Liên hệ quản lý Taxi Cầu Vồng để được hỗ trợ.",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
            (key, value),
        )


def init_db():
    """Khởi tạo/migrate DB và đồng bộ tài khoản Admin từ Streamlit Secrets/ENV.

    Thiết kế này tránh lỗi UNIQUE/IntegrityError khi app khởi động nhiều lần:
    - Nếu username Secret đã có: cập nhật tài khoản đó thành Admin.
    - Nếu chưa có nhưng DB đã có một Admin: dùng Admin hiện có và cập nhật
      username/mật khẩu theo Secret.
    - Chỉ INSERT khi database chưa có bất kỳ Admin nào.
    """
    conn = get_connection()
    try:
        _ensure_schema(conn)
        _seed_roles(conn)
        _seed_settings(conn)

        admin_username, admin_password = _get_admin_credentials()

        if admin_username and admin_password:
            password_hash = hash_password(admin_password)

            # 1) Ưu tiên tài khoản có đúng username trong Secrets.
            admin = conn.execute(
                "SELECT id FROM users WHERE username = ? LIMIT 1",
                (admin_username,),
            ).fetchone()

            if admin:
                conn.execute("""
                    UPDATE users
                    SET password=?, full_name=?, role='admin', approved=1,
                        active=1, must_change_password=0
                    WHERE id=?
                """, (
                    password_hash,
                    "Quản trị viên Taxi Cầu Vồng",
                    admin["id"],
                ))
            else:
                # 2) Nếu DB cũ đã có Admin khác username, không INSERT thêm.
                #    Đổi chính Admin hiện có sang username/password từ Secrets.
                existing_admin = conn.execute(
                    "SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1"
                ).fetchone()

                if existing_admin:
                    # Xóa/đổi username cũ có thể đụng UNIQUE, nên kiểm tra
                    # username Secret đã được truy vấn ở bước 1.
                    conn.execute("""
                        UPDATE users
                        SET username=?, password=?, full_name=?, role='admin',
                            approved=1, active=1, must_change_password=0
                        WHERE id=?
                    """, (
                        admin_username,
                        password_hash,
                        "Quản trị viên Taxi Cầu Vồng",
                        existing_admin["id"],
                    ))
                else:
                    # 3) Database mới hoàn toàn: tạo Admin lần đầu.
                    # SAVEPOINT giúp xử lý IntegrityError mà không làm hỏng
                    # transaction khởi tạo schema.
                    conn.execute("SAVEPOINT create_admin")
                    try:
                        conn.execute("""
                            INSERT INTO users
                            (username,password,full_name,role,approved,duty,active,
                             must_change_password,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (
                            admin_username,
                            password_hash,
                            "Quản trị viên Taxi Cầu Vồng",
                            "admin",
                            1, 0, 1, 0,
                            now().isoformat(),
                        ))
                        conn.execute("RELEASE SAVEPOINT create_admin")
                    except sqlite3.IntegrityError:
                        conn.execute("ROLLBACK TO SAVEPOINT create_admin")
                        conn.execute("RELEASE SAVEPOINT create_admin")

                        # Một DB cũ có thể có ràng buộc UNIQUE/NOT NULL khác.
                        # Nếu lúc này xuất hiện Admin, dùng Admin đó thay vì
                        # để lỗi SQL làm app Streamlit dừng hẳn.
                        existing_admin = conn.execute(
                            "SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1"
                        ).fetchone()
                        if existing_admin:
                            conn.execute("""
                                UPDATE users
                                SET username=?, password=?, full_name=?,
                                    approved=1, active=1, must_change_password=0
                                WHERE id=?
                            """, (
                                admin_username,
                                password_hash,
                                "Quản trị viên Taxi Cầu Vồng",
                                existing_admin["id"],
                            ))
                        else:
                            raise RuntimeError(
                                "Không thể tạo tài khoản Admin từ Streamlit Secrets. "
                                "Database taxi.db hiện tại có cấu trúc/ràng buộc "
                                "không tương thích với bảng users. Hãy xóa taxi.db "
                                "cũ để tạo database mới hoặc gửi log chi tiết."
                            )

        conn.commit()
    finally:
        conn.close()


def _row_dict(row):
    return dict(row) if row else None


def login_user(username, password):
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    finally:
        conn.close()

    if not user or not verify_password(password, user["password"]):
        return None, "Sai tài khoản hoặc mật khẩu."
    if not user["active"]:
        return None, "Tài khoản đã bị khóa."
    if not user["approved"]:
        return None, "Tài khoản chưa được Admin duyệt."

    return _row_dict(user), None


def get_user(user_id):
    conn = get_connection()
    try:
        return _row_dict(conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone())
    finally:
        conn.close()


def get_all_users():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT *
            FROM users
            ORDER BY
                CASE role WHEN 'admin' THEN 0 WHEN 'manager' THEN 1 ELSE 2 END,
                id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pending_users():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM users
            WHERE approved = 0
            ORDER BY id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_user(username, password, full_name, role="driver",
                approved=False, avatar="", created_by=None):
    username = username.strip()
    full_name = full_name.strip()
    role = role.strip() or "driver"

    if not username or not password or not full_name:
        return False, "Vui lòng nhập đầy đủ thông tin."
    if len(username) < 3:
        return False, "Tên tài khoản phải có ít nhất 3 ký tự."
    if len(password) < 4:
        return False, "Mật khẩu phải có ít nhất 4 ký tự."

    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT id FROM roles WHERE role_key=?", (role,)
        ).fetchone()
        if not exists:
            return False, "Role không tồn tại."

        conn.execute("""
            INSERT INTO users
            (username,password,full_name,role,approved,duty,active,
             avatar,created_by,must_change_password,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            username, hash_password(password), full_name, role,
            1 if approved else 0, 0, 1, avatar or "",
            created_by, 1, now().isoformat(),
        ))
        conn.commit()
        return True, "Đã tạo tài khoản."
    except sqlite3.IntegrityError:
        return False, "Tên đăng nhập đã tồn tại."
    finally:
        conn.close()


def create_admin_account(username, password, full_name, created_by=None, avatar=""):
    return create_user(
        username, password, full_name,
        role="admin", approved=True,
        avatar=avatar, created_by=created_by
    )


def approve_user(user_id):
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET approved=1 WHERE id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def reject_user(user_id):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM users WHERE id=? AND username <> 'admin'",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT username FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if not row or row["username"] == "admin":
            return False, "Không thể xóa Admin gốc."

        conn.execute("DELETE FROM trips WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        return True, "Đã xóa tài khoản."
    finally:
        conn.close()


def update_user(user_id, full_name=None, role=None, approved=None,
                active=None, avatar=None):
    fields, values = [], []
    if full_name is not None:
        fields.append("full_name=?"); values.append(full_name.strip())
    if role is not None:
        fields.append("role=?"); values.append(role)
    if approved is not None:
        fields.append("approved=?"); values.append(1 if approved else 0)
    if active is not None:
        fields.append("active=?"); values.append(1 if active else 0)
    if avatar is not None:
        fields.append("avatar=?"); values.append(avatar)

    if not fields:
        return False, "Không có thay đổi."

    conn = get_connection()
    try:
        if role is not None and not conn.execute(
            "SELECT 1 FROM roles WHERE role_key=?", (role,)
        ).fetchone():
            return False, "Role không tồn tại."
        values.append(user_id)
        conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id=?",
            values,
        )
        conn.commit()
        return True, "Đã cập nhật tài khoản."
    finally:
        conn.close()


def change_password(user_id, *args):
    """Change password. Supports both (user_id, new_password) and
    (user_id, old_password, new_password) so old/new app.py versions work."""
    if len(args) == 1:
        old_password = None
        new_password = args[0]
    elif len(args) == 2:
        old_password, new_password = args
    else:
        return False, "Tham số đổi mật khẩu không hợp lệ."

    if not new_password or len(new_password) < 4:
        return False, "Mật khẩu phải có ít nhất 4 ký tự."

    conn = get_connection()
    try:
        if old_password is not None:
            row = conn.execute(
                "SELECT password FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if not row or not verify_password(old_password, row["password"]):
                return False, "Mật khẩu hiện tại không đúng."

        conn.execute("""
            UPDATE users
            SET password=?, must_change_password=0
            WHERE id=?
        """, (hash_password(new_password), user_id))
        conn.commit()
        return True, "Đã đổi mật khẩu."
    finally:
        conn.close()


def set_duty(user_id, duty):
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET duty=? WHERE id=?",
                     (1 if duty else 0, user_id))
        conn.commit()
    finally:
        conn.close()


def get_online_drivers():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM users
            WHERE role IN ('user','driver')
              AND approved=1
              AND active=1
              AND duty=1
            ORDER BY full_name ASC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_today_key():
    current = now()
    if current.hour < 2:
        current -= timedelta(days=1)
    return current.strftime("%Y-%m-%d")


def _taxi_day_for_iso(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        dt = dt.astimezone(TZ)
        if dt.hour < 2:
            dt -= timedelta(days=1)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def get_today_trip_count(user_id):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT created_at FROM trips
            WHERE user_id=? AND status='approved'
        """, (user_id,)).fetchall()
    finally:
        conn.close()

    key = get_today_key()
    return sum(1 for r in rows if _taxi_day_for_iso(r["created_at"]) == key)


# Alias tương thích app cũ.
get_trip_count = get_today_trip_count


def get_total_approved_trips(user_id):
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT COUNT(*) AS total FROM trips
            WHERE user_id=? AND status='approved'
        """, (user_id,)).fetchone()
        return row["total"] if row else 0
    finally:
        conn.close()


def add_trip(user_id, image_path, note=""):
    if get_today_trip_count(user_id) >= 50:
        return False, "Bạn đã đạt tối đa 50 chuyến hôm nay."

    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO trips
            (user_id,image_path,note,status,created_at)
            VALUES (?,?,?,'pending',?)
        """, (user_id, image_path, note, now().isoformat()))
        conn.commit()
        return True, "Đã gửi chuyến, chờ Admin duyệt."
    finally:
        conn.close()


def _trip_dict(row):
    data = dict(row)
    # Tương thích tên key của app cũ.
    data["image"] = data.get("image_path", "")
    return data


def get_user_trips(user_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trips WHERE user_id=? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [_trip_dict(r) for r in rows]
    finally:
        conn.close()


def get_all_trips():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT trips.*, users.username, users.full_name
            FROM trips
            JOIN users ON users.id=trips.user_id
            ORDER BY trips.id DESC
        """).fetchall()
        return [_trip_dict(r) for r in rows]
    finally:
        conn.close()


def get_pending_trips():
    return [x for x in get_all_trips() if x["status"] == "pending"]


def approve_trip(trip_id, admin_id=None):
    conn = get_connection()
    try:
        trip = conn.execute(
            "SELECT * FROM trips WHERE id=?", (trip_id,)
        ).fetchone()
        if not trip:
            return False, "Không tìm thấy chuyến."
        if trip["status"] != "pending":
            return False, "Chuyến đã được xử lý."
        if get_today_trip_count(trip["user_id"]) >= 50:
            return False, "Tài xế đã đạt 50 chuyến hôm nay."

        conn.execute("""
            UPDATE trips
            SET status='approved', approved_at=?, approved_by=?
            WHERE id=?
        """, (now().isoformat(), admin_id, trip_id))
        conn.commit()
        return True, "Đã duyệt chuyến."
    finally:
        conn.close()


def reject_trip(trip_id, admin_id=None):
    conn = get_connection()
    try:
        cur = conn.execute("""
            UPDATE trips
            SET status='rejected', approved_at=?, approved_by=?
            WHERE id=? AND status='pending'
        """, (now().isoformat(), admin_id, trip_id))
        conn.commit()
        return cur.rowcount > 0, "Đã từ chối chuyến." if cur.rowcount else "Chuyến đã được xử lý."
    finally:
        conn.close()


def get_leaderboard():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT users.id, users.username, users.full_name, users.duty,
                   COUNT(trips.id) AS total
            FROM users
            LEFT JOIN trips
              ON users.id=trips.user_id AND trips.status='approved'
            WHERE users.role IN ('user','driver')
              AND users.approved=1 AND users.active=1
            GROUP BY users.id
            ORDER BY total DESC, users.full_name ASC
        """).fetchall()
        return [
            {
                "id": r["id"],
                "name": r["full_name"],
                "username": r["username"],
                "trips": r["total"],
                "duty": r["duty"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def create_post(title, content, image_path="", admin_id=None, pinned=False):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO posts
            (title,content,image_path,pinned,created_by,created_at)
            VALUES (?,?,?,?,?,?)
        """, (
            title.strip(), content or "", image_path or "",
            1 if pinned else 0, admin_id, now().isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def _post_dict(row):
    data = dict(row)
    data["image"] = data.get("image_path", "")
    return data


def get_posts():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY pinned DESC, id DESC"
        ).fetchall()
        return [_post_dict(r) for r in rows]
    finally:
        conn.close()


def delete_post(post_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
        conn.commit()
    finally:
        conn.close()


def toggle_pin(post_id, current):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE posts SET pinned=? WHERE id=?",
            (0 if current else 1, post_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_setting(key, default=""):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key, value):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO settings(key,value)
            VALUES (?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        conn.commit()
    finally:
        conn.close()


# =========================
# ROLE & PERMISSION
# =========================

def get_roles():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM roles ORDER BY id"
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            perms = conn.execute("""
                SELECT permission_key FROM role_permissions
                WHERE role_id=? ORDER BY permission_key
            """, (row["id"],)).fetchall()
            item["permissions"] = [p["permission_key"] for p in perms]
            result.append(item)
        return result
    finally:
        conn.close()


def get_role(role_key):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM roles WHERE role_key=?", (role_key,)
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["permissions"] = [
            r["permission_key"]
            for r in conn.execute(
                "SELECT permission_key FROM role_permissions WHERE role_id=?",
                (row["id"],)
            ).fetchall()
        ]
        return item
    finally:
        conn.close()


def get_permissions():
    conn = get_connection()
    try:
        return [
            dict(r) for r in conn.execute(
                "SELECT * FROM permissions ORDER BY permission_key"
            ).fetchall()
        ]
    finally:
        conn.close()


def create_role(role_key, name, description, permissions):
    role_key = role_key.strip().lower().replace(" ", "_")
    if not role_key or not name.strip():
        return False, "Vui lòng nhập role và tên hiển thị."
    if not role_key.replace("_", "").isalnum():
        return False, "Role chỉ được dùng chữ, số và dấu _."

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO roles(role_key,name,description,created_at)
            VALUES (?,?,?,?)
        """, (role_key, name.strip(), description.strip(), now().isoformat()))
        role_id = cur.lastrowid
        for perm in permissions:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions(role_id,permission_key)
                VALUES (?,?)
            """, (role_id, perm))
        conn.commit()
        return True, "Đã tạo role."
    except sqlite3.IntegrityError:
        return False, "Role đã tồn tại."
    finally:
        conn.close()


def update_role_permissions(role_key, permissions):
    conn = get_connection()
    try:
        role = conn.execute(
            "SELECT id FROM roles WHERE role_key=?", (role_key,)
        ).fetchone()
        if not role:
            return False, "Không tìm thấy role."

        conn.execute(
            "DELETE FROM role_permissions WHERE role_id=?",
            (role["id"],),
        )
        for perm in permissions:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions(role_id,permission_key)
                VALUES (?,?)
            """, (role["id"], perm))
        conn.commit()
        return True, "Đã cập nhật quyền."
    finally:
        conn.close()


def rename_role(role_key, name, description):
    if role_key == "admin":
        return False, "Không đổi tên role admin gốc."
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE roles SET name=?, description=? WHERE role_key=?
        """, (name.strip(), description.strip(), role_key))
        conn.commit()
        return True, "Đã cập nhật role."
    finally:
        conn.close()


def delete_role(role_key):
    if role_key in DEFAULT_ROLES:
        return False, "Không thể xóa role mặc định."

    conn = get_connection()
    try:
        used = conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE role=?",
            (role_key,),
        ).fetchone()["n"]
        if used:
            return False, "Role đang được tài khoản sử dụng."

        conn.execute("DELETE FROM roles WHERE role_key=?", (role_key,))
        conn.commit()
        return True, "Đã xóa role."
    finally:
        conn.close()


def user_has_permission(user_or_id, permission_key):
    user = (
        get_user(user_or_id)
        if isinstance(user_or_id, int)
        else user_or_id
    )
    if not user or not user.get("active", 1):
        return False
    if user.get("role") == "admin":
        return True

    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT 1
            FROM role_permissions rp
            JOIN roles r ON r.id=rp.role_id
            WHERE r.role_key=? AND rp.permission_key=?
        """, (user["role"], permission_key)).fetchone()
        return bool(row)
    finally:
        conn.close()


# =========================
# MEDIA
# =========================

def get_media(media_key, default=""):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT path FROM site_media WHERE media_key=?",
            (media_key,),
        ).fetchone()
        return row["path"] if row and row["path"] else default
    finally:
        conn.close()


def set_media(media_key, path, alt_text=""):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO site_media(media_key,path,alt_text,updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(media_key)
            DO UPDATE SET path=excluded.path,
                          alt_text=excluded.alt_text,
                          updated_at=excluded.updated_at
        """, (media_key, path or "", alt_text or "", now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_all_media():
    conn = get_connection()
    try:
        return [
            dict(r) for r in conn.execute(
                "SELECT * FROM site_media ORDER BY media_key"
            ).fetchall()
        ]
    finally:
        conn.close()
