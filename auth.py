OWNER_USERNAME = "Dakota"
USERS_FILE = "users.txt"
ADMIN_FILE = "admin_users.txt"

# --------- Account & Login ---------

def validate_login(username, password):
    if not username.strip() or not password.strip():
        return False  # reject empty inputs

    try:
        with open(USERS_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 2:
                    continue  # skip malformed lines
                stored_user = parts[0].strip()
                stored_pass = parts[1].strip()
                if username.strip() == stored_user and password.strip() == stored_pass:
                    return True
        return False
    except FileNotFoundError:
        print("[auth.py] users.txt not found.")
        return False

def set_password(username: str, new_password: str) -> bool:
    """
    Directly set a user's password in users.txt and force is_temp=0.
    users.txt columns:
      0=username, 1=password, 2=first, 3=last, 4=bosk_id, 5=is_admin, 6=is_temp
    """
    if not (username and new_password):
        return False
    try:
        updated = False
        out = []
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            for raw in f:
                parts = raw.strip().split(",")
                while len(parts) < 7:
                    parts.append("0")
                if parts[0].strip() == username.strip():
                    parts[1] = new_password  # password
                    parts[6] = "0"           # is_temp OFF
                    updated = True
                out.append(",".join(p.strip() for p in parts) + "\n")
        if updated:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                f.writelines(out)
        return updated
    except FileNotFoundError:
        return False

def create_user(username, password, first="", last="", bosk_id="", is_admin=False, is_temp=True):
    try:
        with open(USERS_FILE, "a", encoding="utf-8") as file:
            # Force is_temp to 0 (we're removing the temp concept)
            line = f"{username},{password},{first},{last},{bosk_id},{int(is_admin)},{0}\n"
            file.write(line)
        if is_admin:
            promote_to_admin(username)
        return True
    except Exception as e:
        print(f"[auth.py] Error creating user: {e}")
        return False



def mark_password_reset(username):
    try:
        updated_lines = []
        with open(USERS_FILE, "r") as file:
            for line in file:
                parts = line.strip().split(",")
                if parts[0] == username:
                    if len(parts) < 7:
                        parts += ["0"] * (7 - len(parts))  # Ensure length
                    parts[6] = "0"  # is_temp = False
                updated_lines.append(",".join(parts) + "\n")
        with open(USERS_FILE, "w") as file:
            file.writelines(updated_lines)
    except Exception as e:
        print(f"[auth.py] Error marking password reset: {e}")


def is_temp_password(username):
    try:
        with open(USERS_FILE, "r") as file:
            for line in file:
                parts = line.strip().split(",")
                if parts[0] == username and len(parts) >= 7:
                    return bool(int(parts[6]))
    except Exception as e:
        print(f"[auth.py] Error checking temp password: {e}")
    return False


# --------- Admin + Owner ---------

def is_owner(username):
    return username.strip() == OWNER_USERNAME.strip()


def is_admin(username):
    try:
        with open(ADMIN_FILE, "r") as f:
            admins = [line.strip() for line in f.readlines()]
        return username.strip() in admins or is_owner(username)
    except FileNotFoundError:
        return is_owner(username)


def promote_to_admin(username):
    if not is_admin(username):
        try:
            with open(ADMIN_FILE, "a") as f:
                f.write(username.strip() + "\n")
        except Exception as e:
            print(f"[auth.py] Error promoting admin: {e}")


def demote_from_admin(username):
    if username.strip() == OWNER_USERNAME:
        return  # Never demote owner
    try:
        with open(ADMIN_FILE, "r") as f:
            lines = f.readlines()
        with open(ADMIN_FILE, "w") as f:
            for line in lines:
                if line.strip() != username.strip():
                    f.write(line)
    except Exception as e:
        print(f"[auth.py] Error demoting admin: {e}")
