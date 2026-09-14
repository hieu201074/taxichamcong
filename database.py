"""Supabase database backend for Taxi Cầu Vồng.
Keeps the same public functions used by the current app.py.
Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets.
"""
import hashlib
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    import streamlit as st
except Exception:
    st = None

try:
    from supabase import create_client
except Exception:
    create_client = None

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
TRIP_LIMIT = 300

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
    "admin": {"name": "Administrator", "description": "Toàn quyền hệ thống", "permissions": list(DEFAULT_PERMISSIONS)},
    "manager": {"name": "Manager", "description": "Quản lý tài xế, chuyến và bài đăng", "permissions": [
        "view_dashboard", "submit_trip", "view_history", "view_leaderboard", "view_posts",
        "manage_users", "approve_users", "approve_trips", "manage_posts", "view_duty", "manage_duty"]},
    "driver": {"name": "Taxi Driver", "description": "Tài khoản tài xế", "permissions": [
        "view_dashboard", "submit_trip", "view_history", "view_leaderboard", "view_posts"]},
    "user": {"name": "Taxi Driver", "description": "Role cũ, tương đương tài xế", "permissions": [
        "view_dashboard", "submit_trip", "view_history", "view_leaderboard", "view_posts"]},
}

DEFAULT_SETTINGS = {
    "site_title": "TAXI CẦU VỒNG",
    "site_subtitle": "HỆ THỐNG CHẤM CÔNG",
    "home_text": "Hệ thống quản lý tài xế Taxi Cầu Vồng",
    "contact": "Liên hệ quản lý Taxi để được hỗ trợ.",
}


def now():
    return datetime.now(TZ)


def _secret(name, default=""):
    if st is not None:
        try:
            value = st.secrets.get(name, None)
            if value is not None:
                return str(value)
        except Exception:
            pass
    return os.getenv(name, default)


_SB = None


def _get_supabase():
    if create_client is None:
        raise RuntimeError("Thiếu thư viện supabase. Thêm 'supabase' vào requirements.txt rồi redeploy.")
    url = _secret("SUPABASE_URL", "").strip()
    key = _secret("SUPABASE_SERVICE_ROLE_KEY", "").strip() or _secret("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("Chưa cấu hình Supabase. Thêm SUPABASE_URL và SUPABASE_SERVICE_ROLE_KEY vào Streamlit Secrets.")
    return create_client(url, key)


def get_connection():
    global _SB
    if _SB is None:
        _SB = _get_supabase()
    return _SB


def _data(response):
    return getattr(response, "data", None) or []


def _one(response):
    data = _data(response)
    return data[0] if data else None


def _select(table, select="*", filters=None, order=None, limit=None):
    q = get_connection().table(table).select(select)
    for col, value in (filters or {}).items():
        q = q.is_(col, "null") if value is None else q.eq(col, value)
    for col, desc in (order or []):
        q = q.order(col, desc=desc)
    if limit is not None:
        q = q.limit(limit)
    return _data(q.execute())


def _insert(table, row):
    return _one(get_connection().table(table).insert(row).execute())


def _update(table, values, filters):
    q = get_connection().table(table).update(values)
    for col, value in filters.items():
        q = q.eq(col, value)
    return _data(q.execute())


def _delete(table, filters):
    q = get_connection().table(table).delete()
    for col, value in filters.items():
        q = q.eq(col, value)
    return _data(q.execute())


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def verify_password(password, stored_password):
    if stored_password is None:
        return False
    stored_password = str(stored_password)
    return hash_password(password) == stored_password or str(password) == stored_password


def _check_schema():
    for table in ("users", "trips", "posts", "settings", "roles", "role_permissions", "permissions", "site_media"):
        get_connection().table(table).select("*").limit(1).execute()


def _seed_roles():
    sb = get_connection()
    existing_permissions = {r["permission_key"] for r in _select("permissions", "permission_key")}
    missing = [{"permission_key": k, "name": v} for k, v in DEFAULT_PERMISSIONS.items() if k not in existing_permissions]
    if missing:
        sb.table("permissions").insert(missing).execute()

    roles = {r["role_key"]: r for r in _select("roles", "id,role_key,name,description,created_at")}
    for key, data in DEFAULT_ROLES.items():
        if key not in roles:
            row = _insert("roles", {"role_key": key, "name": data["name"], "description": data["description"], "created_at": now().isoformat()})
            if row:
                roles[key] = row
    for key, data in DEFAULT_ROLES.items():
        role = roles.get(key)
        if not role:
            continue
        current = {r["permission_key"] for r in _select("role_permissions", "permission_key", {"role_id": role["id"]})}
        missing = [{"role_id": role["id"], "permission_key": p} for p in data["permissions"] if p not in current]
        if missing:
            sb.table("role_permissions").insert(missing).execute()


def _seed_settings():
    existing = {r["key"] for r in _select("settings", "key")}
    missing = [{"key": k, "value": v} for k, v in DEFAULT_SETTINGS.items() if k not in existing]
    if missing:
        get_connection().table("settings").insert(missing).execute()


def init_db():
    _check_schema()
    _seed_roles()
    _seed_settings()

    admin_username = (_secret("TAXI_ADMIN_USERNAME", "admin") or "admin").strip()
    admin_password = _secret("TAXI_ADMIN_PASSWORD", "")
    admin_name = (_secret("TAXI_ADMIN_NAME", "Quản trị viên Taxi Cầu Vồng") or "Quản trị viên Taxi Cầu Vồng").strip()
    if not admin_password:
        return

    sb = get_connection()
    password_hash = hash_password(admin_password)
    admin = _one(sb.table("users").select("id").eq("username", admin_username).limit(1).execute())
    if admin:
        _update("users", {"role": "admin", "approved": True, "active": True}, {"id": admin["id"]})
        return

    existing_admin = _one(sb.table("users").select("id").eq("role", "admin").order("id", desc=False).limit(1).execute())
    if existing_admin:
        _update("users", {
            "username": admin_username, "password": password_hash, "full_name": admin_name,
            "role": "admin", "approved": True, "active": True, "must_change_password": False,
        }, {"id": existing_admin["id"]})
    else:
        _insert("users", {
            "username": admin_username, "password": password_hash, "full_name": admin_name,
            "role": "admin", "approved": True, "duty": False, "active": True,
            "must_change_password": False, "created_at": now().isoformat(),
        })


def login_user(username, password):
    user = _one(get_connection().table("users").select("*").eq("username", str(username).strip()).limit(1).execute())
    if not user or not verify_password(password, user.get("password")):
        return None, "Sai tài khoản hoặc mật khẩu."
    if not user.get("active", True):
        return None, "Tài khoản đã bị khóa."
    if not user.get("approved", False):
        return None, "Tài khoản chưa được Admin duyệt."
    return dict(user), None


def get_user(user_id):
    return _one(get_connection().table("users").select("*").eq("id", user_id).limit(1).execute())


def get_all_users():
    rows = _select("users", order=[("id", True)])
    priority = {"admin": 0, "manager": 1}
    rows.sort(key=lambda r: (priority.get(r.get("role"), 2), -int(r.get("id") or 0)))
    return rows


def get_pending_users():
    return _select("users", filters={"approved": False}, order=[("id", True)])


def create_user(username, password, full_name, role="driver", approved=False, avatar="", created_by=None):
    username, full_name, role = str(username or "").strip(), str(full_name or "").strip(), str(role or "driver").strip()
    if not username or not password or not full_name:
        return False, "Vui lòng nhập đầy đủ thông tin."
    if len(username) < 3:
        return False, "Tên tài khoản phải có ít nhất 3 ký tự."
    if len(str(password)) < 4:
        return False, "Mật khẩu phải có ít nhất 4 ký tự."
    if not _one(get_connection().table("roles").select("id").eq("role_key", role).limit(1).execute()):
        return False, "Role không tồn tại."
    if _one(get_connection().table("users").select("id").eq("username", username).limit(1).execute()):
        return False, "Tên đăng nhập đã tồn tại."
    try:
        _insert("users", {
            "username": username, "password": hash_password(password), "full_name": full_name,
            "role": role, "approved": bool(approved), "duty": False, "active": True,
            "avatar": avatar or "", "created_by": created_by, "must_change_password": True,
            "created_at": now().isoformat(),
        })
        return True, "Đã tạo tài khoản."
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            return False, "Tên đăng nhập đã tồn tại."
        raise


def create_admin_account(username, password, full_name, created_by=None, avatar=""):
    return create_user(username, password, full_name, role="admin", approved=True, avatar=avatar, created_by=created_by)


def approve_user(user_id):
    _update("users", {"approved": True}, {"id": user_id})


def reject_user(user_id):
    user = get_user(user_id)
    if user and user.get("username") != "admin":
        _delete("users", {"id": user_id})


def delete_user(user_id):
    user = get_user(user_id)
    if not user or user.get("username") == "admin" or user.get("role") == "admin":
        return False, "Không thể xóa Admin gốc."
    _delete("trips", {"user_id": user_id})
    _delete("users", {"id": user_id})
    return True, "Đã xóa tài khoản."


def update_user(user_id, full_name=None, role=None, approved=None, active=None, avatar=None):
    values = {}
    if full_name is not None: values["full_name"] = str(full_name).strip()
    if role is not None:
        role = str(role).strip()
        if not _one(get_connection().table("roles").select("id").eq("role_key", role).limit(1).execute()):
            return False, "Role không tồn tại."
        values["role"] = role
    if approved is not None: values["approved"] = bool(approved)
    if active is not None: values["active"] = bool(active)
    if avatar is not None: values["avatar"] = avatar
    if not values: return False, "Không có thay đổi."
    _update("users", values, {"id": user_id})
    return True, "Đã cập nhật tài khoản."


def change_password(user_id, *args):
    if len(args) == 1: old_password, new_password = None, args[0]
    elif len(args) == 2: old_password, new_password = args
    else: return False, "Tham số đổi mật khẩu không hợp lệ."
    if not new_password or len(str(new_password)) < 4:
        return False, "Mật khẩu phải có ít nhất 4 ký tự."
    if old_password is not None:
        row = get_user(user_id)
        if not row or not verify_password(old_password, row.get("password")):
            return False, "Mật khẩu hiện tại không đúng."
    _update("users", {"password": hash_password(new_password), "must_change_password": False}, {"id": user_id})
    return True, "Đã đổi mật khẩu."


def set_duty(user_id, duty):
    _update("users", {"duty": bool(duty)}, {"id": user_id})


def get_online_drivers():
    return _data(get_connection().table("users").select("*").in_("role", ["user", "driver"]).eq("approved", True).eq("active", True).eq("duty", True).order("full_name").execute())


def get_today_key():
    current = now()
    if current.hour < 2: current -= timedelta(days=1)
    return current.strftime("%Y-%m-%d")


def _taxi_day_for_iso(value):
    try:
        if not value: return None
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=TZ)
        dt = dt.astimezone(TZ)
        if dt.hour < 2: dt -= timedelta(days=1)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def get_today_trip_count(user_id):
    rows = _select("trips", "created_at", {"user_id": user_id, "status": "approved"})
    key = get_today_key()
    return sum(1 for r in rows if _taxi_day_for_iso(r.get("created_at")) == key)


get_trip_count = get_today_trip_count


def get_total_approved_trips(user_id):
    return len(_select("trips", "id", {"user_id": user_id, "status": "approved"}))


def add_trip(user_id, image_path, note=""):
    if get_today_trip_count(user_id) >= TRIP_LIMIT:
        return False, f"Bạn đã đạt tối đa {TRIP_LIMIT} chuyến hôm nay."
    _insert("trips", {"user_id": user_id, "image_path": image_path, "note": note or "", "status": "pending", "created_at": now().isoformat()})
    return True, "Đã gửi chuyến, chờ Admin duyệt."


def _trip_dict(row):
    data = dict(row); data["image"] = data.get("image_path", ""); return data


def get_user_trips(user_id):
    return [_trip_dict(r) for r in _select("trips", filters={"user_id": user_id}, order=[("id", True)])]


def get_all_trips():
    trips = _select("trips", order=[("id", True)])
    users = _select("users", "id,username,full_name")
    user_map = {u["id"]: u for u in users}
    result = []
    for trip in trips:
        data = _trip_dict(trip); user = user_map.get(trip.get("user_id"), {})
        data["username"] = user.get("username", ""); data["full_name"] = user.get("full_name", ""); result.append(data)
    return result


def get_pending_trips():
    return [x for x in get_all_trips() if x.get("status") == "pending"]


def approve_trip(trip_id, admin_id=None):
    trip = _one(get_connection().table("trips").select("*").eq("id", trip_id).limit(1).execute())
    if not trip: return False, "Không tìm thấy chuyến."
    if trip.get("status") != "pending": return False, "Chuyến đã được xử lý."
    if get_today_trip_count(trip["user_id"]) >= TRIP_LIMIT: return False, f"Tài xế đã đạt {TRIP_LIMIT} chuyến hôm nay."
    _update("trips", {"status": "approved", "approved_at": now().isoformat(), "approved_by": admin_id}, {"id": trip_id})
    return True, "Đã duyệt chuyến."


def reject_trip(trip_id, admin_id=None):
    trip = _one(get_connection().table("trips").select("id,status").eq("id", trip_id).limit(1).execute())
    if not trip or trip.get("status") != "pending": return False, "Chuyến đã được xử lý."
    _update("trips", {"status": "rejected", "approved_at": now().isoformat(), "approved_by": admin_id}, {"id": trip_id})
    return True, "Đã từ chối chuyến."


def get_leaderboard():
    users = [u for u in _select("users", "id,full_name,duty,role,approved,active") if u.get("role") in ("user", "driver") and u.get("approved") and u.get("active")]
    trips = _select("trips", "user_id,status", {"status": "approved"})
    counts = {}
    for t in trips: counts[t.get("user_id")] = counts.get(t.get("user_id"), 0) + 1
    result = [{"id": u["id"], "name": u.get("full_name", ""), "trips": counts.get(u["id"], 0), "duty": u.get("duty", False)} for u in users]
    result.sort(key=lambda x: (-int(x["trips"]), str(x["name"]).lower()))
    return result


def create_post(title, content, image_path="", admin_id=None, pinned=False):
    _insert("posts", {"title": str(title or "").strip(), "content": content or "", "image_path": image_path or "", "pinned": bool(pinned), "created_by": admin_id, "created_at": now().isoformat()})


def _post_dict(row):
    data = dict(row); data["image"] = data.get("image_path", ""); return data


def get_posts():
    return [_post_dict(r) for r in _select("posts", order=[("pinned", True), ("id", True)])]


def delete_post(post_id):
    _delete("posts", {"id": post_id})


def toggle_pin(post_id, current):
    _update("posts", {"pinned": not bool(current)}, {"id": post_id})


def get_setting(key, default=""):
    row = _one(get_connection().table("settings").select("value").eq("key", key).limit(1).execute())
    return row.get("value", default) if row else default


def set_setting(key, value):
    get_connection().table("settings").upsert({"key": key, "value": value}, on_conflict="key").execute()


def get_roles():
    roles = _select("roles", order=[("id", False)])
    permissions = _select("role_permissions", "role_id,permission_key")
    grouped = {}
    for p in permissions: grouped.setdefault(p["role_id"], []).append(p["permission_key"])
    result = []
    for role in roles:
        item = dict(role); item["permissions"] = sorted(grouped.get(role["id"], [])); result.append(item)
    return result


def get_role(role_key):
    role = _one(get_connection().table("roles").select("*").eq("role_key", role_key).limit(1).execute())
    if not role: return None
    perms = _select("role_permissions", "permission_key", {"role_id": role["id"]})
    item = dict(role); item["permissions"] = [p["permission_key"] for p in perms]; return item


def get_permissions():
    return _select("permissions", order=[("permission_key", False)])


def create_role(role_key, name, description, permissions):
    role_key = str(role_key or "").strip().lower().replace(" ", "_"); name = str(name or "").strip(); description = str(description or "").strip()
    if not role_key or not name: return False, "Vui lòng nhập role và tên hiển thị."
    if not role_key.replace("_", "").isalnum(): return False, "Role chỉ được dùng chữ, số và dấu _."
    if _one(get_connection().table("roles").select("id").eq("role_key", role_key).limit(1).execute()): return False, "Role đã tồn tại."
    role = _insert("roles", {"role_key": role_key, "name": name, "description": description, "created_at": now().isoformat()})
    if not role: return False, "Không tạo được role."
    rows = [{"role_id": role["id"], "permission_key": p} for p in permissions]
    if rows: get_connection().table("role_permissions").insert(rows).execute()
    return True, "Đã tạo role."


def update_role_permissions(role_key, permissions):
    role = _one(get_connection().table("roles").select("id").eq("role_key", role_key).limit(1).execute())
    if not role: return False, "Không tìm thấy role."
    _delete("role_permissions", {"role_id": role["id"]})
    rows = [{"role_id": role["id"], "permission_key": p} for p in permissions]
    if rows: get_connection().table("role_permissions").insert(rows).execute()
    return True, "Đã cập nhật quyền."


def rename_role(role_key, name, description):
    if role_key == "admin": return False, "Không đổi tên role admin gốc."
    _update("roles", {"name": str(name or "").strip(), "description": str(description or "").strip()}, {"role_key": role_key})
    return True, "Đã cập nhật role."


def delete_role(role_key):
    if role_key in DEFAULT_ROLES: return False, "Không thể xóa role mặc định."
    role = _one(get_connection().table("roles").select("id").eq("role_key", role_key).limit(1).execute())
    if not role: return False, "Không tìm thấy role."
    if _select("users", "id", {"role": role_key}): return False, "Role đang được tài khoản sử dụng."
    _delete("role_permissions", {"role_id": role["id"]}); _delete("roles", {"id": role["id"]})
    return True, "Đã xóa role."


def user_has_permission(user_or_id, permission_key):
    user = get_user(user_or_id) if isinstance(user_or_id, int) else user_or_id
    if not user or not user.get("active", True): return False
    if user.get("role") == "admin": return True
    role = _one(get_connection().table("roles").select("id").eq("role_key", user.get("role")).limit(1).execute())
    if not role: return False
    return bool(_one(get_connection().table("role_permissions").select("permission_key").eq("role_id", role["id"]).eq("permission_key", permission_key).limit(1).execute()))


def get_media(media_key, default=""):
    row = _one(get_connection().table("site_media").select("path").eq("media_key", media_key).limit(1).execute())
    return row.get("path", default) if row else default


def set_media(media_key, path, alt_text=""):
    get_connection().table("site_media").upsert({"media_key": media_key, "path": path or "", "alt_text": alt_text or "", "updated_at": now().isoformat()}, on_conflict="media_key").execute()


def get_all_media():
    return _select("site_media", order=[("media_key", False)])
