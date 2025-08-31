import sqlite3
import json
import os

USER_FILE = "users.txt"

def load_users():
    users = {}
    with open(USER_FILE, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 7:
                username = parts[0].strip()
                password = parts[1].strip()
                first = parts[2].strip()
                last = parts[3].strip()
                bosk_id = parts[4].strip().upper()
                is_temp = parts[5].strip()
                is_admin = parts[6].strip()

                users[bosk_id] = {
                    "username": username,
                    "password": password,
                    "first": first,
                    "last": last,
                    "is_temp": is_temp,
                    "is_admin": is_admin
                }
    print("✅ database.py loaded!")

    print("🔍 Loaded BOSK IDs:", list(users.keys()))  # ← Add this line
    return users

def set_password_by_bosk_id(bosk_id: str, new_password: str) -> bool:
    """Admin: set a user's password using BOSK ID. Returns True if updated."""
    if not (bosk_id and new_password):
        return False
    key = bosk_id.strip().upper()
    users = load_users()
    if key not in users:
        return False

    users[key]["password"] = str(new_password)
    # kill temp concept
    users[key]["is_temp"] = "0"
    save_users(users)
    return True


def set_password_by_username(username: str, new_password: str) -> bool:
    """Admin: set a user's password by username. Returns True if updated."""
    if not (username and new_password):
        return False
    users = load_users()

    # find the matching BOSK key
    target_key = None
    for bosk_key, rec in users.items():
        if rec.get("username", "").strip().lower() == username.strip().lower():
            target_key = bosk_key
            break

    if not target_key:
        return False

    users[target_key]["password"] = str(new_password)
    users[target_key]["is_temp"] = "0"
    save_users(users)
    return True


def user_exists(bosk_id):
    bosk_id = bosk_id.strip().upper()
    users = load_users()
    return bosk_id in users

def reset_password(bosk_id, new_password):
    bosk_id = bosk_id.strip().upper()
    users = load_users()

    if bosk_id not in users:
        raise ValueError("User not found")

    print("🧪 BOSK ID entered:", bosk_id)
    print("🔍 Available BOSK IDs:", list(users.keys()))

    users[bosk_id]["password"] = new_password
    users[bosk_id]["is_temp"] = "0"

    save_users(users)
    print("✅ Password reset and saved.")


def save_users(users):
    with open(USER_FILE, "w") as f:
        for bosk_id, user in users.items():
            line = f"{user['username']},{user['password']},{user['first']},{user['last']},{bosk_id},{user['is_temp']},0\n"
            f.write(line)


# Admin checks
def is_owner(username):
    return username == "Dakota"

def is_admin(username):
    try:
        with open("admin_users.txt", "r") as file:
            admins = [line.strip() for line in file.readlines()]
        return username in admins or is_owner(username)
    except FileNotFoundError:
        return is_owner(username)

def can_access_admin(username: str) -> bool:
    """
    One place to decide if the Admin Controls button should appear.
    True for owner (Dakota) or any username listed in admin_users.txt.
    """
    return is_owner(username) or is_admin(username)


# Connect to DB
def connect():
    return sqlite3.connect("ppm.db")

# Setup DB tables
def setup_database():
    with connect() as conn:
        c = conn.cursor()

        # Run table
        c.execute('''CREATE TABLE IF NOT EXISTS runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_number TEXT,
                        caller TEXT,
                        location TEXT,
                        nature TEXT,
                        assigned TEXT,
                        notes TEXT,
                        timestamp TEXT,
                        locked INTEGER DEFAULT 0
                    )''')

        # Responder status table
        c.execute('''CREATE TABLE IF NOT EXISTS statuses (
                        run_id INTEGER,
                        unit TEXT,
                        status TEXT,
                        timestamp TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(id)
                    )''')

        # Addendum log
        c.execute('''CREATE TABLE IF NOT EXISTS addendums (
                        run_id INTEGER,
                        username TEXT,
                        notes TEXT,
                        timestamp TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(id)
                    )''')

        # Incident reports
        c.execute('''CREATE TABLE IF NOT EXISTS incidents (
                        run_id INTEGER PRIMARY KEY,
                        incident_notes TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(id)
                    )''')

        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        password TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        bosk_id TEXT,
                        is_temp INTEGER DEFAULT 1
                    )''')

# Save run to database
def save_users(users):
    """
    Persist users back to users.txt.
    - Preserves is_admin instead of hardcoding 0
    - Uppercases BOSK ID for consistency
    - Accepts both 'first'/'last' and 'first_name'/'last_name' keys
    """
    def _to_admin_str(v):
        # normalize truthy values -> "1", falsy -> "0"
        if isinstance(v, str):
            v = v.strip().lower()
            return "1" if v in ("1", "true", "yes", "y") else "0"
        return "1" if bool(v) else "0"

    with open(USER_FILE, "w", encoding="utf-8") as f:
        for bosk_id, user in users.items():
            username   = user.get("username", "").strip()
            password   = user.get("password", "").strip()
            first_name = (user.get("first") or user.get("first_name") or "").strip()
            last_name  = (user.get("last")  or user.get("last_name")  or "").strip()
            bosk       = (bosk_id or user.get("bosk_id") or "").strip().upper()
            is_temp    = str(user.get("is_temp", "1")).strip()
            is_admin   = _to_admin_str(user.get("is_admin", "0"))

            line = f"{username},{password},{first_name},{last_name},{bosk},{is_temp},{is_admin}\n"
            f.write(line)

# Save responder status
def save_status(run_id, unit, status, timestamp):
    conn = connect()
    c = conn.cursor()
    c.execute('''INSERT INTO statuses (run_id, unit, status, timestamp)
                 VALUES (?, ?, ?, ?)''',
              (run_id, unit, status, timestamp))
    conn.commit()
    conn.close()

# Admin role management
def promote_to_admin(username):
    try:
        with open("admin_users.txt", "a") as file:
            file.write(username + "\n")
    except Exception as e:
        print(f"Error promoting user: {e}")

def demote_from_admin(username):
    if username == "Dakota":
        return  # Prevent removing owner
    try:
        with open("admin_users.txt", "r") as file:
            lines = file.readlines()
        with open("admin_users.txt", "w") as file:
            for line in lines:
                if line.strip() != username:
                    file.write(line)
    except FileNotFoundError:
        pass

# Create user
def create_user(username, password, first="", last="", bosk_id="", is_temp=True):
    try:
        with connect() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password, first_name, last_name, bosk_id, is_temp) VALUES (?, ?, ?, ?, ?, ?)",
                      (username, password, first, last, bosk_id, int(is_temp)))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists

def add_user(username, password, first, last, bosk_id, is_admin=False, is_temp=True):
    users = load_users()
    key = (bosk_id or "").strip().upper()
    if key in users:
        return False  # Duplicate BOSK ID

    users[key] = {
        "username": username,
        "password": password,
        "first": first,
        "last": last,
        "is_temp": "1" if is_temp else "0",
        "is_admin": "1" if is_admin else "0",
    }
    save_users(users)
    return True
