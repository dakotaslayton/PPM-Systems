import os
import json
from datetime import datetime
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from filelock import FileLock

# =========================
# Files & constants
# =========================
RUN_LOG_FILE = "run_log.txt"        # Canonical log for runs
RUN_LOG_LOCK = f"{RUN_LOG_FILE}.lock"
USERS_FILE = "users.txt"            # username,password,first,last,bosk_id,is_temp,is_admin
RESPONDER_USERS_FILE = "responder_users.json"  # {"41": ["dakota"], "42": ["alex","jordan"]}
OWNER_BOSK_IDS = {"OWNER-001"}      # <-- update to your real owner BOSK ID(s)


# =========================
# Auth helpers
# =========================
def _load_users_from_file(path: str = USERS_FILE) -> dict:
    """
    Returns dict:
      users[username_lower] = {
        'username': str, 'password': str, 'first': str, 'last': str,
        'bosk_id': str, 'is_temp': bool, 'is_admin': bool
      }
    """
    users = {}
    if not os.path.exists(path):
        return users
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            # username,password,first,last,bosk_id,is_temp,is_admin
            if len(parts) < 7:
                # tolerate short lines
                parts += [""] * (7 - len(parts))
            username, password, first, last, bosk_id, is_temp, is_admin = parts[:7]
            users[username.lower()] = {
                "username": username,
                "password": password,
                "first": first,
                "last": last,
                "bosk_id": (bosk_id or "").upper(),
                "is_temp": (str(is_temp).strip().upper() in ("1", "TRUE", "YES", "Y")),
                "is_admin": (str(is_admin).strip().upper() in ("1", "TRUE", "YES", "Y")),
            }
    return users


def verify_credentials(username: str, password: str) -> tuple[bool, bool]:
    """
    Returns (is_valid, is_admin)
    """
    if not username or not password:
        return (False, False)
    users = _load_users_from_file()
    rec = users.get(username.lower())
    if not rec:
        return (False, False)
    if rec["password"] != password:
        return (False, False)
    return (True, bool(rec["is_admin"]))


def is_owner(username: str) -> bool:
    rec = _load_users_from_file().get((username or "").lower())
    if not rec:
        return False
    return rec.get("bosk_id", "").upper() in OWNER_BOSK_IDS


def _load_responder_users_map() -> dict:
    """
    Load responder->usernames mapping.
    Normalizes usernames to lowercase strings and keys to str.
    Example file:
      { "41": ["dakota"], "42": ["alex","jordan"] }
    """
    if not os.path.exists(RESPONDER_USERS_FILE):
        return {}
    try:
        with open(RESPONDER_USERS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}
    mapping: dict[str, list[str]] = {}
    for k, v in raw.items():
        key = str(k).strip()
        if not key:
            continue
        if isinstance(v, str):
            usernames = [v.strip().lower()] if v.strip() else []
        elif isinstance(v, list):
            usernames = [str(x).strip().lower() for x in v if str(x).strip()]
        else:
            usernames = []
        mapping[key] = usernames
    return mapping


def get_user_responder_ids(username: str) -> set[str]:
    """Reverse-lookup: which responder IDs map to this username (lowercased)"""
    username_l = (username or "").strip().lower()
    if not username_l:
        return set()
    mapping = _load_responder_users_map()
    out = {rid for rid, users in mapping.items() if username_l in users}
    return out


# =========================
# Run log helpers
# =========================
def save_run_to_text(run_data: dict, statuses: dict) -> None:
    """
    Appends a new run block to run_log.txt
    Format is designed to be human-readable and easily parsed.

    Expected fields in run_data:
      run_number, caller, location, nature, assigned (comma-separated), notes, timestamp (optional)
    """
    os.makedirs(os.path.dirname(RUN_LOG_FILE) or ".", exist_ok=True)
    timestamp = run_data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    block = [
        "=== RUN START ===",
        f"RunNumber: {run_data.get('run_number','')}",
        f"Caller: {run_data.get('caller','')}",
        f"Location: {run_data.get('location','')}",
        f"Nature: {run_data.get('nature','')}",
        f"Assigned: {run_data.get('assigned','')}",
        f"Timestamp: {timestamp}",
        "Notes:",
        (run_data.get("notes") or "").strip(),
        "Statuses:"
    ]

    # statuses: { unit: {status, timestamp} }
    for unit, st in (statuses or {}).items():
        block.append(f"{unit}|{st.get('status','')}|{st.get('timestamp','')}")

    block += [
        "Addendums:",   # keep this literal; we'll append addendums after this line
        "=== RUN END ===",
        ""
    ]

    with FileLock(RUN_LOG_LOCK, timeout=5):
        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(block) + "\n")


def parse_runs_from_log():
    """
    Returns a list of dicts for each run block.
    """
    runs = []
    if not os.path.exists(RUN_LOG_FILE):
        return runs

    with open(RUN_LOG_FILE, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f.readlines()]

    cur = None
    section = None
    for ln in lines:
        if ln == "=== RUN START ===":
            cur = {"notes": "", "statuses": [], "addendums": []}
            section = None
            continue
        if ln == "=== RUN END ===":
            if cur:
                runs.append(cur)
            cur = None
            section = None
            continue
        if cur is None:
            continue

        if ln.startswith("RunNumber: "):
            cur["run_number"] = ln.split("RunNumber: ", 1)[1]
        elif ln.startswith("Caller: "):
            cur["caller"] = ln.split("Caller: ", 1)[1]
        elif ln.startswith("Location: "):
            cur["location"] = ln.split("Location: ", 1)[1]
        elif ln.startswith("Nature: "):
            cur["nature"] = ln.split("Nature: ", 1)[1]
        elif ln.startswith("Assigned: "):
            cur["assigned"] = ln.split("Assigned: ", 1)[1]
        elif ln.startswith("Timestamp: "):
            cur["timestamp"] = ln.split("Timestamp: ", 1)[1]
        elif ln == "Notes:":
            section = "notes"
        elif ln == "Statuses:":
            section = "statuses"
        elif ln == "Addendums:":
            section = "addendums"
        else:
            if section == "notes":
                cur["notes"] += (ln + "\n")
            elif section == "statuses":
                # Format: UNIT|STATUS|TS
                parts = ln.split("|")
                if len(parts) >= 3:
                    cur["statuses"].append({"unit": parts[0], "status": parts[1], "timestamp": parts[2]})
            elif section == "addendums":
                if ln.strip():
                    cur["addendums"].append(ln)

    return runs


def append_addendum(run_number: str, author: str, text: str) -> None:
    """
    Appends an addendum line at the end of the target run block (after 'Addendums:').
    To keep it simple, we rewrite the file.
    """
    runs = parse_runs_from_log()
    if not runs:
        raise RuntimeError("No runs found.")

    found = False
    for r in runs:
        if r.get("run_number") == run_number:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r.setdefault("addendums", [])
            r["addendums"].append(f"[{ts}] {author}: {text}")
            found = True
            break
    if not found:
        raise RuntimeError(f"Run not found: {run_number}")

    # Rewrite file
    out = []
    for r in runs:
        out += [
            "=== RUN START ===",
            f"RunNumber: {r.get('run_number','')}",
            f"Caller: {r.get('caller','')}",
            f"Location: {r.get('location','')}",
            f"Nature: {r.get('nature','')}",
            f"Assigned: {r.get('assigned','')}",
            f"Timestamp: {r.get('timestamp','')}",
            "Notes:",
            (r.get("notes") or "").rstrip("\n"),
            "Statuses:"
        ]
        for st in (r.get("statuses") or []):
            out.append(f"{st.get('unit','')}|{st.get('status','')}|{st.get('timestamp','')}")
        out += ["Addendums:"]
        for ad in (r.get("addendums") or []):
            out.append(ad)
        out += ["=== RUN END ===", ""]

    with FileLock(RUN_LOG_LOCK, timeout=5):
        with open(RUN_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")


# =========================
# UI: Credentials dialog
# =========================
class CredentialsDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Authenticate")
        self.resizable(False, False)
        self.grab_set()
        self.username = None
        self.is_admin = False
        self.result_ok = False

        # Center the dialog relative to screen
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ww, wh = 360, 170
        x, y = (sw // 2) - (ww // 2), (sh // 2) - (wh // 2)
        self.geometry(f"{ww}x{wh}+{x}+{y}")

        frm = ctk.CTkFrame(self)
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frm, text="Username").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.user_entry = ctk.CTkEntry(frm, width=240)
        self.user_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        ctk.CTkLabel(frm, text="Password").grid(row=1, column=0, sticky="w")
        self.pass_entry = ctk.CTkEntry(frm, show="•", width=240)
        self.pass_entry.grid(row=1, column=1, sticky="ew")

        btns = ctk.CTkFrame(frm)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ctk.CTkButton(btns, text="Cancel", command=self._cancel).pack(side="right", padx=(0, 8))
        ctk.CTkButton(btns, text="Sign In", command=self._ok).pack(side="right")

        frm.grid_columnconfigure(1, weight=1)
        self.user_entry.focus_set()
        self.bind("<Return>", lambda _e: self._ok())

    def _ok(self):
        u = self.user_entry.get().strip()
        p = self.pass_entry.get().strip()
        valid, is_admin_flag = verify_credentials(u, p)
        if not valid:
            messagebox.showerror("Authentication", "Invalid username or password.", parent=self)
            return
        self.username = u
        self.is_admin = bool(is_admin_flag)
        self.result_ok = True
        self.destroy()

    def _cancel(self):
        self.result_ok = False
        self.destroy()


# =========================
# UI: Run Reports
# =========================
class RunReportsWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("CAD Logs")
        self.geometry("1300x760")

        # On-top behavior similar to your CAD windows
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(500, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

        # Prompt for credentials ONCE at window open
        cred = CredentialsDialog(self)
        self.wait_window(cred)
        if not cred.result_ok:
            # close if not authenticated
            self.destroy()
            return
        self.username = cred.username or ""
        self.is_admin = bool(cred.is_admin)
        self.is_owner = is_owner(self.username)
        # (Admins or Owner see everything)

        # Top: header + search bar
        top = ctk.CTkFrame(self)
        top.pack(side="top", fill="x", padx=10, pady=(10, 0))

        hdr = ctk.CTkLabel(
            top,
            text=f"Signed in as: {self.username}  ({'Owner' if self.is_owner else ('Admin' if self.is_admin else 'Responder')})",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        hdr.pack(side="left", padx=(0, 10))

        self.search_entry = ctk.CTkEntry(top, placeholder_text="Search runs (keywords, responder/unit, comments, statuses, etc.)")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(10, 6))
        ctk.CTkButton(top, text="Search", command=self._on_search).pack(side="left")
        ctk.CTkButton(top, text="Clear", command=self._on_clear).pack(side="left", padx=(6, 0))
        self.search_entry.bind("<Return>", lambda _e: self._on_search())

        # Main split
        main = ctk.CTkFrame(self)
        main.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        # Left: list of runs
        left = ctk.CTkFrame(main)
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))

        self.listbox = tk.Listbox(left, width=45, font=("Consolas", 11))
        self.listbox.pack(fill="both", expand=True)

        # Right: details + addendum
        right = ctk.CTkFrame(main)
        right.pack(side="right", fill="both", expand=True)

        self.details = tk.Text(right, wrap="word", font=("Arial", 12), state="normal")
        self.details.pack(fill="both", expand=True)

        addendum_row = ctk.CTkFrame(right)
        addendum_row.pack(fill="x", pady=(8, 0))
        self.addendum_entry = ctk.CTkEntry(addendum_row, placeholder_text="Add addendum…")
        self.addendum_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(addendum_row, text="Append", command=self.on_addendum).pack(side="left")

        # Bottom controls
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(bottom, text="Refresh", command=self.refresh).pack(side="right", padx=4)
        ctk.CTkButton(bottom, text="Open", command=self.open_selected).pack(side="right", padx=4)

        # Data
        self.all_runs = []
        self.filtered_runs = []
        self.current_run_number = None

        self.refresh()

    # -------------------------
    # Search/filter logic
    # -------------------------
    def _normalize(self, s: str) -> str:
        return (s or "").strip()

    def _contains(self, hay: str, needle: str) -> bool:
        return needle in (hay or "").lower()

    def _run_matches(self, r: dict, q: str) -> bool:
        if not q:
            return True
        q = q.lower().strip()
        # fields
        fields = [
            r.get("run_number", ""),
            r.get("caller", ""),
            r.get("location", ""),
            r.get("nature", ""),
            r.get("assigned", ""),
            r.get("notes", ""),
        ]
        if any(self._contains(f.lower(), q) for f in fields):
            return True
        # statuses: unit, status, timestamp
        for st in (r.get("statuses") or []):
            if (self._contains(st.get("unit", "").lower(), q) or
                self._contains(st.get("status", "").lower(), q) or
                self._contains(st.get("timestamp", "").lower(), q)):
                return True
        # addendums
        for ad in (r.get("addendums") or []):
            if self._contains(ad.lower(), q):
                return True
        return False

    def _filter_runs_by_query(self, runs: list[dict], query: str) -> list[dict]:
        return [r for r in runs if self._run_matches(r, query)]

    # -------------------------
    # Access control
    # -------------------------
    @staticmethod
    def _tokenize_assigned(assigned_str: str) -> tuple[set[str], set[str]]:
        """
        Returns (tokens_all_lower, responder_id_tokens)
        - tokens are split on commas
        - responder_id_tokens are numeric-like strings (e.g., "41")
        """
        tokens = set()
        ids = set()
        for raw in (assigned_str or "").replace(";", ",").split(","):
            tok = raw.strip()
            if not tok:
                continue
            tokens.add(tok.lower())
            if tok.isdigit():
                ids.add(tok)
        return tokens, ids

    def _user_has_access_to_run(self, r: dict) -> bool:
        """
        Access rules:
          - Owner or Admin: full access
          - Otherwise: access if the RUN's Assigned list contains:
              * the username (case-insensitive)
              * OR any responder ID that maps to this username in responder_users.json
        """
        if self.is_admin or self.is_owner:
            return True

        assigned = r.get("assigned", "") or ""
        tokens_all, id_tokens = self._tokenize_assigned(assigned)

        # Username listed directly in Assigned
        if (self.username or "").strip().lower() in tokens_all:
            return True

        # Responder mapping
        my_ids = get_user_responder_ids(self.username)
        return len(my_ids & id_tokens) > 0

    def _apply_access_filter(self, runs: list[dict]) -> list[dict]:
        return [r for r in runs if self._user_has_access_to_run(r)]

    # -------------------------
    # UI actions
    # -------------------------
    def _on_search(self):
        q = self.search_entry.get().strip()
        self._populate_list(self._filter_runs_by_query(self.filtered_runs, q))

    def _on_clear(self):
        self.search_entry.delete(0, "end")
        self._populate_list(self.filtered_runs)

    def refresh(self):
        self.all_runs = parse_runs_from_log()
        # Apply access control first
        self.filtered_runs = self._apply_access_filter(self.all_runs)
        # Populate list
        self._populate_list(self.filtered_runs)

    def _populate_list(self, runs: list[dict]):
        self.listbox.delete(0, "end")
        for r in runs:
            rn = r.get("run_number", "Run ?")
            ts = r.get("timestamp", "")
            self.listbox.insert("end", f"{rn}  —  {ts}")

    def _get_selected_run(self) -> dict | None:
        sel = self.listbox.curselection()
        if not sel:
            return None
        label = self.listbox.get(sel[0])
        run_number = label.split("—")[0].strip()
        for r in self.filtered_runs:
            if r.get("run_number") == run_number:
                return r
        return None

    def open_selected(self):
        r = self._get_selected_run()
        if not r:
            return

        # Safety check (should already be filtered)
        if not self._user_has_access_to_run(r):
            messagebox.showwarning(
                "Access Denied",
                "You are not assigned to this run and are not an admin/owner.",
                parent=self,
            )
            return

        self.show_run_details(r)

    def show_run_details(self, r):
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", f"Run Number: {r.get('run_number','')}\n")
        self.details.insert("end", f"Timestamp: {r.get('timestamp','')}\n")
        self.details.insert("end", f"Caller: {r.get('caller','')}\n")
        self.details.insert("end", f"Location: {r.get('location','')}\n")
        self.details.insert("end", f"Nature: {r.get('nature','')}\n")
        self.details.insert("end", f"Assigned: {r.get('assigned','')}\n\n")
        self.details.insert("end", "Notes:\n")
        self.details.insert("end", (r.get("notes") or "").strip() + "\n\n")
        self.details.insert("end", "Statuses:\n")
        for st in (r.get("statuses") or []):
            self.details.insert("end", f"  - {st.get('unit','')}: {st.get('status','')} ({st.get('timestamp','')})\n")
        self.details.insert("end", "\nAddendums:\n")
        for ad in (r.get("addendums") or []):
            self.details.insert("end", f"  {ad}\n")
        self.details.config(state="disabled")

        # Store current selection
        self.current_run_number = r.get("run_number")

    def on_addendum(self):
        txt = self.addendum_entry.get().strip()
        if not txt:
            return
        rn = getattr(self, "current_run_number", None)
        if not rn:
            messagebox.showwarning("Addendum", "Open a run first.")
            return
        try:
            append_addendum(rn, getattr(self, "username", "User"), txt)
            self.addendum_entry.delete(0, "end")
            # Refresh & reselect updated run
            self.refresh()
            # find the updated run now present in filtered list
            for idx in range(self.listbox.size()):
                label = self.listbox.get(idx)
                if label.split("—")[0].strip() == rn:
                    self.listbox.selection_clear(0, "end")
                    self.listbox.selection_set(idx)
                    self.listbox.activate(idx)
                    break
            # show details from fresh data
            r = next((x for x in self.filtered_runs if x.get("run_number") == rn), None)
            if r:
                self.show_run_details(r)
        except Exception as e:
            messagebox.showerror("Addendum Error", f"Could not append addendum:\n{e}")


# =========================
# If you want to quickly test the window:
# =========================
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.withdraw()
    RunReportsWindow(root)
    root.mainloop()
