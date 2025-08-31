# call_form.py
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from datetime import datetime
import smtplib
from email.message import EmailMessage
import csv
import json
import os
import time
from filelock import FileLock
import random

# Optional (weather tab)
import requests
from bs4 import BeautifulSoup

from run_reports import RunReportsWindow, save_run_to_text
from incident_reports import IncidentReportForm
import database  # noqa: F401

# ==============================
# Shift Log helpers & constants
# ==============================
import io  # keep at top-level

SHIFT_LOG_DIR = "shift_logs"
os.makedirs(SHIFT_LOG_DIR, exist_ok=True)

def current_shift_name(self=None):
    """
    Returns active shift name string like 'SHIFT_A'.
    If self.active_shift is set by set_default_responder_shift(), use it.
    Fallback to 'SHIFT_A'.
    """
    if self is not None and hasattr(self, "active_shift") and self.active_shift:
        return f"SHIFT_{self.active_shift}"
    return "SHIFT_A"

def today_stamp():
    return datetime.now().strftime("%Y-%m-%d")

def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def shift_current_log_path(shift=None):
    s = shift or current_shift_name()
    return os.path.join(SHIFT_LOG_DIR, f"{today_stamp()}_{s}_current.txt")

def shift_archive_log_path(shift, suffix=""):
    base = f"{today_stamp()}_{shift}_summary"
    if suffix:
        base += f"_{suffix}"
    return os.path.join(SHIFT_LOG_DIR, base + ".txt")

def typing_state_path():
    return os.path.join(SHIFT_LOG_DIR, "typing_state.json")


# ==============================
# Existing helpers
# ==============================
def load_random_quote():
    try:
        with open("inspirational_quotes.txt", "r", encoding="utf-8") as f:
            quotes = [line.strip() for line in f if line.strip()]
        return random.choice(quotes) if quotes else "Be your best self."
    except FileNotFoundError:
        return "Be your best self."

def save_run_to_log(run_data, statuses):
    log_path = "run_log.txt"
    lock_path = f"{log_path}.lock"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    block = [
        "=== RUN START ===",
        f"RunNumber: {run_data['run_number']}",
        f"Caller: {run_data['caller']}",
        f"Location: {run_data['location']}",
        f"Nature: {run_data['nature']}",
        f"Assigned: {run_data['assigned']}",
        f"Timestamp: {timestamp}",
        "Notes:",
        run_data["notes"].strip(),
        "Statuses:"
    ]

    for unit, status in statuses.items():
        block.append(f"{unit}|{status['status']}|{status['timestamp']}")

    block += [
        "Addendums:",
        "=== RUN END ===",
        ""
    ]

    with FileLock(lock_path, timeout=5):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(block) + "\n")


# ==============================
# Configuration and data
# ==============================
status_colors = {
    "--": "gray",
    "DISPATCHED": "dark goldenrod",
    "ENROUTE": "orange",
    "ON SCENE": "red",
    "TRANSPORTING": "blue",
    "AVAILABLE": "green",
    "UNAVAILABLE": "black",
}
apparatus_units = [
    ("E1", "Engine 1"), ("E2", "Engine 2"),
    ("M1", "Medic 1"), ("M2", "Medic 2"),
    ("TWR", "Tower"), ("SQRT", "Squirt"),
]
status_tags = ["Ready", "Needs Maintenance", "Out of Service"]
tag_colors = {"Ready": "green", "Needs Maintenance": "red", "Out of Service": "black"}
staging_locations = [
    "SERT headquarters", "Combined waste", "Main security", "Secondary security",
    "Electrode", "Cell assembly", "Formation", "Module",
    "17 Anode Rib", "17 Cathode Rib",
    "53 Anode Rib", "53 Cathode Rib",
    "73 Anode Rib", "73 Cathode Rib",
    "BOSK Medical",
]
contact_list = [
    ("Jeremy Goodman", "270-312-4252"), ("Matt Mesaros", "440-336-0514"),
    ("Mark Haley", "734-674-7420"), ("Martha Delgado", "270-268-6546"),
    ("Ben Gassman", "931-691-7915"), ("Hardin Co. Control", "270-737-5669"),
    ("BOSK Medical", "901-499-9569"),
    ("JCI", [
        ("Logan", "T-F 6a-4p", "502-551-4252"),
        ("Chad Mixon", "Sat-M 5:30a-6p", "502-724-2796"),
        ("Joe Reed", "2:30p-12a","270-740-7617"),
        ("John Ahern", "T-F 10p-8a", "407-668-6232"),
        ("Billy Smith", "Sat-M 5:30p-6a", "270-740-9711")
    ]),
    ("Security", "270-763-3019"), ("Maintenance", "931-954-8054"),
    ("SBM Daytime", "248-807-1144")
]
ALERT_CONTACTS = {"Shift Supervisor"}
responder_shifts = {
    "A": [
        ("B1", "Bill Mullins"), ("11", "Clifford Hicks"), ("12", "Chris Allen"),
        ("13", "Rodney Rodgers"), ("14", "Mark Newman"), ("15", "Tiffany Grasch"),
        ("16", "Amber Johnson"), ("17", "Troy Williams"), ("18", "Karen Rae")
    ],
    "B": [
        ("B2", "Daniel Highbaugh"), ("21", "Thomas Walling"), ("22", "Dennis Walling"),
        ("23", "Wade Mullins"), ("24", "Tracy Senovitz"), ("25", "Trevor Atcher"),
        ("26", "Christian Reynolds"), ("27", "William Mahuron"), ("28", "Jayden Cruse")
    ],
    "C": [
        ("B3", "Kevin Jevning"), ("31", "Lewis O'Brien"), ("32", "Tim McClure"),
        ("33", "Jordan Claggett"), ("34", "Frank Williams"), ("35", "David Johnson"),
        ("36", "Jamie Slayton"), ("37", "Steven Johnson"), ("38", "Greg Van Meter")
    ],
    "D": [
        ("B4", "Shane Carpenter"), ("41", "Chris Ross"), ("42", "Kelsey Blick"),
        ("43", "Dakota Slayton"), ("44", "Brendan Hartigan"), ("45", "Patrick Montague"),
        ("46", "Chasity Davis"), ("47", "Scott Harper"), ("48", "Cody McFalda")
    ],
}
all_responders = [f"{u} {n}" for shift in responder_shifts.values() for u, n in shift]
APPARATUS_STATE_FILE = "apparatus_state.json"

def send_email_alert(subject: str, body: str) -> None:
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = "sender@example.com"
        msg["To"] = ["recipient@example.com"]
        msg.set_content(body)
        with smtplib.SMTP("smtp.example.com", 587) as smtp:
            smtp.starttls()
            smtp.login("your_username", "your_password")
            smtp.send_message(msg)
    except Exception:
        pass


# ==============================
# Main application class
# ==============================
class CallForm(ctk.CTk):
    def __init__(self, username: str, return_to_dashboard):
        super().__init__()
        self.username = username
        self.return_to_dashboard = return_to_dashboard
        self.geometry("1200x800")
        self.title("Call Entry")

        # Global/static state
        self.persistent_dynamic_responders = {}  # global memory of chosen dynamic names (by slot index)
        self.run_unit_assignments = {}           # run_number -> set(apparatus units)
        self.global_statuses = {u: "AVAILABLE" for shift in responder_shifts.values() for u, _ in shift}
        self.globally_unavailable = set()        # units forced UNAVAILABLE, persists across runs until cleared
        self.last_status_updates = {}            # (run, unit) -> (status, ts) for dedupe
        self.global_apparatus = {
            unit: {
                "runstatus": "AVAILABLE",            # baseline (we do NOT propagate per-run changes globally)
                "opstatus": "Ready",                 # persists globally
                "lastusedby": "Last Used By",
                "staging": staging_locations[0],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            } for unit, _ in apparatus_units
        }

        # UI frame
        self.main_tabview = ctk.CTkTabview(self)
        self.main_tabview.pack(fill="both", expand=True)

        # === SHIFT LOG TAB ===
        self.shift_tab = self.main_tabview.add("Shift Log")
        self.create_shift_log_tab()

        # === WEATHER TAB (between Shift Log and Runs) ===
        self.weather_tab = self.main_tabview.add("Weather")
        self.create_weather_tab()

        # === Regular CAD UI state ===
        self.run_tabs = {}
        self.status_memory = {}     # per-run, per-shift, per-slot memory
        self.unit_active_runs = {}  # unit -> set(run_number)
        self.load_apparatus_state()

        # First run tab
        self.create_run_tab()
        self.after(0, lambda: self.state("zoomed"))

        # Footer (deduplicated)
        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.pack(side="bottom", fill="x")

        ctk.CTkLabel(
            self.footer_frame,
            text=f"👤 {self.username} (Logged In)",
            font=("Arial", 15, "bold")
        ).pack(side="left", padx=10)

        quote = load_random_quote()
        ctk.CTkLabel(
            self.footer_frame,
            text=quote,
            font=("Arial", 15, "italic")
        ).pack(side="right", padx=10)

    # ==============================
    # Shift Log Tab
    # ==============================
    def create_shift_log_tab(self):
        """Create the shift log tab interface"""
        shift_header = ctk.CTkFrame(self.shift_tab)
        shift_header.pack(fill="x", padx=10, pady=(10, 6))

        # Left side - typing indicator
        left_frame = ctk.CTkFrame(shift_header)
        left_frame.pack(side="left", fill="x", expand=True)

        self.typing_label_var = tk.StringVar(value="No one is typing…")
        self.typing_label = ctk.CTkLabel(left_frame, textvariable=self.typing_label_var)
        self.typing_label.pack(side="left", padx=8)

        # Right side - end shift button
        ctk.CTkButton(
            shift_header,
            text="End Shift (Archive)",
            fg_color="#cc3333",
            hover_color="#a52828",
            command=lambda: self.end_shift_archive()
        ).pack(side="right", padx=4)

        # Live log view
        self.shift_view = tk.Text(
            self.shift_tab, height=18, wrap="word",
            state="disabled", bg="black", fg="white", insertbackground="white"
        )
        self.shift_view.pack(fill="both", expand=True, padx=10, pady=6)

        # Prepare tags for styling
        self.shift_view.tag_configure("attention", foreground="red", justify="center")
        self.shift_view.tag_configure("center", justify="center")

        # Input row
        input_row = ctk.CTkFrame(self.shift_tab)
        input_row.pack(fill="x", padx=10, pady=(6, 10))
        ctk.CTkLabel(input_row, text="Add Note:").pack(side="left", padx=(0, 6))
        self.shift_entry = ctk.CTkEntry(input_row, width=800)
        self.shift_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(input_row, text="Send", command=self.shift_send_note).pack(side="left", padx=6)

        # --- Check controls (centered) ---
        wt_row = ctk.CTkFrame(self.shift_tab)
        wt_row.pack(fill="x", padx=10, pady=(0, 10))

        wt_inner = ctk.CTkFrame(wt_row)
        wt_inner.pack(anchor="center")

        ctk.CTkLabel(wt_inner, text="Responder(s)").grid(row=0, column=0, padx=(0, 6), pady=4, sticky="e")
        self.wt_resp_entry = ctk.CTkEntry(wt_inner, width=320, placeholder_text="E1, M1, 21… or names")
        self.wt_resp_entry.grid(row=0, column=1, padx=(0, 14), pady=4, sticky="w")

        ctk.CTkLabel(wt_inner, text="Check").grid(row=0, column=2, padx=(0, 6), pady=4, sticky="e")
        self.wt_desc_entry = ctk.CTkEntry(wt_inner, width=360, placeholder_text="Area / checklist (e.g., Electrode)")
        self.wt_desc_entry.grid(row=0, column=3, padx=(0, 14), pady=4, sticky="w")

        # Buttons side-by-side
        self.wt_complete_btn = ctk.CTkButton(
            wt_inner, text="Completed",
            fg_color="#1f6aa5",
            command=self.walkthrough_completed
        )
        self.wt_complete_btn.grid(row=0, column=4, padx=(0, 8), pady=4, sticky="w")

        self.wt_attention_btn = ctk.CTkButton(
            wt_inner, text="⚠️ Needs Attention",
            fg_color="#FF4444", hover_color="#CC0000",
            command=self.shift_mark_attention
        )
        self.wt_attention_btn.grid(row=0, column=5, padx=(0, 0), pady=4, sticky="w")

        # Typing indicator emit (throttled)
        def _typing_event(_evt=None):
            self.update_typing_state(is_typing=True)
        self.shift_entry.bind("<KeyPress>", _typing_event)
        self.shift_entry.bind("<KeyRelease>", _typing_event)

        # Polling timers for shared files (store ids so we can cancel on destroy)
        self._shift_last_size = 0
        self._last_typing_emit = 0
        self._shift_poll_id = self.after(700, self.poll_shift_log)
        self._typing_poll_id = self.after(700, self.poll_typing_state)


    def shift_mark_attention(self):
        """Log a centered, bold 'Needs Attention' line with highlighted background in the Shift Log."""
        desc = (self.wt_desc_entry.get() or "").strip()
        resp = (self.wt_resp_entry.get() or "").strip()
        text = f"{self.username}: ***NEEDS ATTENTION***"
        if desc:
            text += f" — {desc}"
        if resp:
            text += f" — Responders: {resp}"
        self.shift_append_line(text)
        # Clear inputs
        self.wt_desc_entry.delete(0, "end")
        self.wt_resp_entry.delete(0, "end")
        # Force a quick refresh so styling appears immediately
        self.poll_shift_log()

    def poll_shift_log(self) -> None:
        try:
            path = shift_current_log_path(current_shift_name(self))
            size = os.path.getsize(path) if os.path.exists(path) else 0
            if size != self._shift_last_size:
                text = self.shift_read_all()
                self.shift_view.config(state="normal")
                self.shift_view.delete("1.0", "end")
                self.shift_view.insert("end", text)

                # Configure tags for styling
                self.shift_view.tag_configure("attention", foreground="red", background="yellow", justify="center", font=("Arial", 24, "bold"))
                
                # Tag all '***NEEDS ATTENTION***' lines
                idx = "1.0"
                while True:
                    pos = self.shift_view.search("***NEEDS ATTENTION***", idx, tk.END)
                    if not pos:
                        break
                    line_start = pos.split(".")[0] + ".0"
                    line_end = pos.split(".")[0] + ".end"
                    self.shift_view.tag_add("attention", line_start, line_end)
                    idx = line_end

                self.shift_view.config(state="disabled")
                self.shift_view.see("end")
                self._shift_last_size = size
        except Exception:
            pass
        finally:
            if getattr(self, "_destroying", False):
                return
            try:
                self._shift_poll_id = self.after(700, self.poll_shift_log)
            except Exception:
                pass


    # ==============================
    # Weather Tab
    # ==============================
    def create_weather_tab(self):
        weather_frame = ctk.CTkScrollableFrame(self.weather_tab)
        weather_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(weather_frame, text="Perry County Weather Information",
                     font=("Arial", 20, "bold")).pack(pady=10)

        self.weather_content = ctk.CTkFrame(weather_frame)
        self.weather_content.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkButton(weather_frame, text="Refresh Weather",
                      command=self.update_weather).pack(pady=10)

        # Initial load + auto refresh
        self.update_weather()
        self.after(1800000, self.auto_update_weather)  # 30 min

    def update_weather(self):
        """Fetch and display weather from perryweather.com (best-effort; safe if bs4/requests missing)."""
        # Clear existing
        for w in self.weather_content.winfo_children():
            w.destroy()
        try:
            response = requests.get("http://perryweather.com", timeout=5)
            if response.status_code == 200:
                try:
                    soup = BeautifulSoup(response.text, "html.parser")
                    text = soup.get_text()
                except Exception:
                    text = response.text
                box = tk.Text(self.weather_content, height=25, wrap="word", bg="white", fg="black")
                box.pack(fill="both", expand=True, padx=5, pady=5)
                box.insert("1.0", "Perry County Weather Information\n\n")
                # Keep it short
                box.insert("end", text[:2500])
                box.config(state="disabled")
            else:
                ctk.CTkLabel(self.weather_content, text="Unable to fetch weather data (HTTP error).",
                             text_color="red").pack(pady=20)
        except Exception as e:
            ctk.CTkLabel(self.weather_content, text=f"Weather service unavailable: {e}",
                         text_color="red").pack(pady=20)

    def auto_update_weather(self):
        self.update_weather()
        self.after(1800000, self.auto_update_weather)

    # ==============================
    # Run Tab
    # ==============================
    def on_call_received(self, run_number: str) -> None:
        self.append_note(run_number, "Call Received")

    def create_run_tab(self) -> None:
        run_number = f"Run {str(datetime.now().timestamp())[-6:].replace('.', '')}"
        run_frame = self.main_tabview.add(run_number)
        self.main_tabview.set(run_number)

        # Per-run state
        self.run_tabs[run_number] = {
            "fields": {},
            "notes": None,
            "responder_widgets": {},         # unit -> (var, menu)
            "responder_widget_shift": {},    # unit -> shift_key
            "dropdowns": {},                 # idx -> dict(name/status vars/menus/shift)
            "apparatus": {},                 # unit -> vars/menus
            "assigned_units": [],            # responders
        }

        # Root layout
        outer = ctk.CTkFrame(run_frame)
        outer.pack(fill="both", expand=True)
        for i in range(7):
            outer.grid_columnconfigure(i, weight=1)
        outer.grid_columnconfigure(7, weight=0, minsize=240)
        outer.grid_rowconfigure(3, weight=1)

        # Navbar (renamed buttons)
        nav = ctk.CTkFrame(outer)
        nav.grid(row=0, column=0, columnspan=8, sticky="ew", padx=5, pady=4)
        nav_buttons = [
            ("Return to Dashboard", self.confirm_exit),
            ("Dispatch Logs", self.open_run_reports),
            ("Run Reports", self.open_incident_reports),
            ("New Run", self.create_run_tab),
            ("Close Run", lambda rn=run_number: self.confirm_close_run(rn)),
            ("Sign Out", self.confirm_sign_out),
            ("Export Run", lambda rn=run_number: self.export_to_csv(rn)),
            ("Preview Run", lambda rn=run_number: self.show_run_summary(rn)),
        ]

        nav_container = ctk.CTkFrame(nav)
        nav_container.pack(anchor="center")
        for text, cmd in nav_buttons:
            ctk.CTkButton(nav_container, text=text, command=cmd).pack(side="left", padx=5)

        # Timestamp buttons
        ts_frame = ctk.CTkFrame(outer)
        ts_frame.grid(row=1, column=0, columnspan=8, sticky="ew", padx=5, pady=4)
        ts_container = ctk.CTkFrame(ts_frame)
        ts_container.pack(anchor="center")

        ctk.CTkButton(
            ts_container,
            text="Call Received",
            command=lambda rn=run_number: self.on_call_received(rn)
        ).pack(side="left", padx=4)

        for label, st in [
            ("Dispatched", "DISPATCHED"),
            ("Enroute", "ENROUTE"),
            ("On Scene", "ON SCENE"),
            ("Transporting", "TRANSPORTING"),
            ("Available", "AVAILABLE"),
        ]:
            ctk.CTkButton(
                ts_container,
                text=label,
                command=lambda s=st, rn=run_number: self.update_assigned_units_status(rn, s)
            ).pack(side="left", padx=4)

        # Input fields
        input_frame = ctk.CTkFrame(outer)
        input_frame.grid(row=2, column=0, columnspan=8, sticky="n", pady=(5, 0))
        input_container = ctk.CTkFrame(input_frame)
        input_container.pack(anchor="center")

        fields = ["caller", "location", "nature", "assigned"]
        entries = []
        for i, field in enumerate(fields):
            ctk.CTkLabel(input_container, text=field.capitalize()).grid(row=0, column=2 * i, padx=5, pady=2, sticky="e")
            ent = ctk.CTkEntry(input_container, width=150)
            ent.grid(row=0, column=2 * i + 1, padx=5, pady=2, sticky="w")
            self.run_tabs[run_number]["fields"][field] = ent
            entries.append(ent)

        # Enter-to-append / assign
        for idx, field in enumerate(fields):
            ent = entries[idx]

            def bind_fn(event, f=field, i=idx, entry_widget=ent, rn=run_number):
                # Ensure current shift is set
                if not self.run_tabs[rn].get("current_shift"):
                    tv = self.run_tabs[rn].get("tabview") if "tabview" in self.run_tabs[rn] else None
                    self.set_default_responder_shift(tv, rn)

                value = entry_widget.get().strip()
                if not value:
                    return "break"

                if f != "assigned":
                    # NO timestamp for caller/location/nature in NOTES
                    self.append_note(rn, f"{f.capitalize()}: {value}", skip_timestamp=True)
                    # Move focus to next entry safely
                    if i + 1 < len(entries):
                        self.after(0, entries[i + 1].focus_set)
                    return "break"

                # --- f == "assigned" ---
                # Parse both responders and apparatus FROM THIS LINE ONLY
                items = [v.strip() for v in value.split(",") if v.strip()]
                responder_units, apparatus_units_list = [], []
                apparatus_codes = {u for u, _ in apparatus_units}

                for item in items:
                    unit_code = item.split()[0].upper()
                    if unit_code in apparatus_codes:
                        apparatus_units_list.append(unit_code)
                    else:
                        responder_units.append(unit_code)

                # Reset links so ONLY this Assigned line defines current teams
                if not hasattr(self, "apparatus_responder_links"):
                    self.apparatus_responder_links = {}
                self.apparatus_responder_links[rn] = {
                    app: responder_units.copy() for app in apparatus_units_list
                }

                # Save responders for this run
                self.run_tabs[rn]["assigned_units"] = responder_units
                # Keep only CURRENT apparatus for this run
                self.run_unit_assignments[rn] = set(apparatus_units_list)

                # One clean Assigned line in notes
                all_assigned = apparatus_units_list + responder_units
                if all_assigned:
                    units_str = ", ".join(all_assigned)
                    self.append_note(rn, f"Assigned: {units_str}", skip_timestamp=True)

                # Prime initial DISPATCHED (no per-unit spam)
                for unit in responder_units:
                    self.unit_active_runs.setdefault(unit, set()).add(rn)
                    self.status_change(rn, unit, "DISPATCHED", log=False)
                    self._update_dynamic_matching_unit(rn, unit, "DISPATCHED")

                for unit in apparatus_units_list:
                    self.log_apparatus_runstatus(rn, unit, "DISPATCHED", propagate_global=False, log=False)

                # Clear and jump to Notes (use after() to ensure focus sticks)
                entry_widget.delete(0, "end")
                notes_widget = self.run_tabs[rn]["notes"]
                self.after(0, notes_widget.focus_set)

                # Optionally start a new timestamp prompt on Notes line
                now_str = datetime.now().strftime("%H:%M:%S")
                current = notes_widget.get("1.0", "end-1c")
                if current and not current.endswith("\n"):
                    notes_widget.insert("end", "\n")
                notes_widget.insert("end", f"[{now_str}] ")

                return "break"

            ent.bind("<Return>", bind_fn)

        # Notes panel (left)
        grid = ctk.CTkFrame(outer)
        grid.grid(row=3, column=0, columnspan=7, sticky="nsew", padx=5, pady=5)
        for r in range(40):
            grid.grid_rowconfigure(r, weight=1)
        for c in range(7):
            grid.grid_columnconfigure(c, weight=1)

        notes_frame = ctk.CTkFrame(grid)
        notes_frame.grid(row=0, column=0, rowspan=10, columnspan=3, sticky="nsew", padx=5)
        scroll = tk.Scrollbar(notes_frame)
        scroll.pack(side="right", fill="y")
        notes = tk.Text(
            notes_frame, width=40, height=20, wrap="word",
            bg="black", fg="white", insertbackground="white",
            yscrollcommand=scroll.set
        )
        notes.pack(side="left", fill="both", expand=True)
        scroll.config(command=notes.yview)
        self.run_tabs[run_number]["notes"] = notes

        def notes_return(event, rn=run_number):
            # Keep timestamps in RUN notes (only Shift Log is un-timestamped)
            now_str = datetime.now().strftime("%H:%M:%S")
            self.run_tabs[rn]["notes"].insert("end", f"\n[{now_str}] ")
            return "break"
        notes.bind("<Return>", notes_return)

        # Contacts (right; scrollable)
        contact_frame = ctk.CTkScrollableFrame(outer, width=240)
        contact_frame.grid(row=3, column=7, sticky="ns", padx=5, pady=5)

        for name, phone in contact_list:
            if name == "JCI" and isinstance(phone, list):
                dropdown_var = tk.StringVar(value="-- Select JCI Contact --")
                contact_options = [f"{n} ({shift}, {p})" for n, shift, p in phone]

                def on_jci_select(selection, rn=run_number):
                    self.append_note(rn, f"Contacted JCI - {selection}")
                ctk.CTkOptionMenu(
                    contact_frame, variable=dropdown_var, values=contact_options,
                    command=on_jci_select, fg_color="#1f6aa5", text_color="white"
                ).pack(pady=1, padx=1, fill="x")
            else:
                def cb(n=name, p=phone, rn=run_number):
                    return lambda: self.contact_action(rn, n, p)
                ctk.CTkButton(contact_frame, text=f"{name}\n{phone}", command=cb()).pack(pady=1, padx=1, fill="x")

        ctk.CTkButton(
            contact_frame, text="Needs Addressed", fg_color="#8B0000",
            command=lambda rn=run_number: self.needs_addressed(rn)
        ).pack(pady=10, padx=1, fill="x")

        # Responder area (shift tabs)
        responder_area = ctk.CTkFrame(grid)
        responder_area.grid(row=0, column=3, rowspan=10, columnspan=4, sticky="nsew")
        tabview = ctk.CTkTabview(responder_area)
        tabview.pack(fill="both", expand=True)
        self.run_tabs[run_number]["tabview"] = tabview

        self.responder_shifts = responder_shifts
        dynamic_counter = 0
        for shift_key, roster in responder_shifts.items():
            tab_name = f"Shift {shift_key}"
            tab_frame = tabview.add(tab_name)

            frame = ctk.CTkFrame(tab_frame)
            frame.pack(fill="both", expand=True, padx=2, pady=2)
            for col in range(4):
                frame.grid_columnconfigure(col, weight=1)

            dynamic_slots = 9
            max_rows = max(len(roster), dynamic_slots)
            for row_idx in range(max_rows):
                # Static responders
                if row_idx < len(roster):
                    unit, name = roster[row_idx]
                    ctk.CTkLabel(frame, text=f"{unit} {name}").grid(row=row_idx, column=0, sticky="w", padx=3)
                    status_var = tk.StringVar()
                    status_menu = ctk.CTkOptionMenu(
                        frame,
                        variable=status_var,
                        values=list(status_colors.keys()),
                        command=lambda s, u=unit, sh=shift_key: self.status_change(run_number, u, s, sh, log=True, log_source="dropdown"),
                    )
                    status_menu.grid(row=row_idx, column=1, padx=3)
                    self.bind_status_color(status_var, status_menu)
                    self.run_tabs[run_number]["responder_widgets"][unit] = (status_var, status_menu)
                    self.run_tabs[run_number]["responder_widget_shift"][unit] = shift_key

                # Dynamic responder slots
                if row_idx < dynamic_slots:
                    name_var = tk.StringVar(value="Responder")
                    name_menu = ctk.CTkOptionMenu(
                        frame,
                        variable=name_var,
                        values=["Responder"] + all_responders,
                        command=lambda fullname, idx=dynamic_counter: self.dynamic_responder_selected(run_number, fullname, idx),
                    )
                    name_menu.grid(row=row_idx, column=2, padx=3)

                    # Apply persistent dynamic responder selections
                    if dynamic_counter in self.persistent_dynamic_responders:
                        persistent_name = self.persistent_dynamic_responders[dynamic_counter]
                        name_var.set(persistent_name)
                        name_menu.set(persistent_name)

                    dyn_status_var = tk.StringVar(value="--")
                    dyn_status_menu = ctk.CTkOptionMenu(
                        frame,
                        variable=dyn_status_var,
                        values=list(status_colors.keys()),
                        command=lambda s, idx=dynamic_counter: self.dynamic_status_change(run_number, idx, s, log=True),
                    )
                    dyn_status_menu.grid(row=row_idx, column=3, padx=3)
                    dyn_status_menu.configure(fg_color=status_colors.get("--"))
                    self.bind_status_color(dyn_status_var, dyn_status_menu)

                    self.run_tabs[run_number]["dropdowns"][dynamic_counter] = {
                        "name_widget": name_menu,
                        "status_widget": dyn_status_menu,
                        "status_var": dyn_status_var,
                        "name_var": name_var,
                        "shift": shift_key,
                    }
                    dynamic_counter += 1

        # Ensure correct shift selected and defaults set
        self.set_default_responder_shift(tabview, run_number)
        self.apply_global_statuses_to_tab(run_number)

        # Apparatus (with header labels)
        header_row = 10
        ctk.CTkLabel(grid, text="Apparatus").grid(row=header_row, column=0, sticky="w", padx=3)
        ctk.CTkLabel(grid, text="Op status").grid(row=header_row, column=1, sticky="w", padx=3)
        ctk.CTkLabel(grid, text="Run status").grid(row=header_row, column=2, sticky="w", padx=3)
        ctk.CTkLabel(grid, text="Staging").grid(row=header_row, column=3, sticky="w", padx=3)
        ctk.CTkLabel(grid, text="Last used by").grid(row=header_row, column=4, sticky="w", padx=3)
        ctk.CTkLabel(grid, text="Timestamp").grid(row=header_row, column=5, sticky="w", padx=3)

        apparatus_start_row = header_row + 1
        for j, (unit, name) in enumerate(apparatus_units):
            row = apparatus_start_row + j
            app_data = {
                "runstatus": tk.StringVar(value=self.global_apparatus[unit]["runstatus"]),
                "staging": tk.StringVar(value=self.global_apparatus[unit]["staging"]),
                "opstatus": tk.StringVar(value=self.global_apparatus[unit]["opstatus"]),
                "lastusedby": tk.StringVar(value=self.global_apparatus[unit]["lastusedby"]),
                "timestamp": tk.StringVar(value=self.global_apparatus[unit]["timestamp"]),
            }

            self.run_tabs[run_number]["apparatus"][unit] = app_data
            ctk.CTkLabel(grid, text=f"{unit} {name}").grid(row=row, column=0, sticky="w", padx=3)

            op_menu = ctk.CTkOptionMenu(
                grid, variable=app_data["opstatus"], values=status_tags,
                command=lambda s, u=unit: self.log_apparatus_opstatus(run_number, u, s)
            )
            op_menu.grid(row=row, column=1, padx=3)
            op_menu.configure(fg_color=tag_colors.get(app_data["opstatus"].get(), "gray"))
            app_data["op_menu"] = op_menu

            rs_var = app_data["runstatus"]
            rs_menu = ctk.CTkOptionMenu(
                grid,
                variable=rs_var,
                values=list(status_colors.keys()),
                command=lambda s, u=unit: self.log_apparatus_runstatus(run_number, u, s, propagate_global=False)
            )
            rs_menu.grid(row=row, column=2, padx=3)
            rs_menu.configure(fg_color=status_colors.get(rs_var.get(), "gray"))
            self.bind_status_color(rs_var, rs_menu)
            app_data["runstatus_menu"] = rs_menu

            staging_menu = ctk.CTkOptionMenu(
                grid, variable=app_data["staging"], values=staging_locations,
                command=lambda s, u=unit: self.log_apparatus_staging(run_number, u, s)
            )
            staging_menu.grid(row=row, column=3, padx=3)

            lastused_menu = ctk.CTkOptionMenu(
                grid, variable=app_data["lastusedby"], values=all_responders,
                command=lambda responder, u=unit: self.update_lastused_timestamp(run_number, u, responder)
            )
            lastused_menu.grid(row=row, column=4, padx=3)

            # Timestamp display (read-only)
            ts_entry = ctk.CTkEntry(grid, width=160)
            ts_entry.insert(0, app_data["timestamp"].get())
            ts_entry.configure(state="disabled")
            app_data["timestamp_entry"] = ts_entry
            ts_entry.grid(row=row, column=5, padx=3, sticky="w")

    def apply_global_statuses_to_tab(self, run_number: str) -> None:
        """When a new tab opens, mirror the current global responder/app statuses in its UI."""
        run = self.run_tabs.get(run_number, {})
        # Responders
        for unit, (var, menu) in run.get("responder_widgets", {}).items():
            g = self.global_statuses.get(unit, "AVAILABLE")
            var.set(g)
            try:
                menu.configure(fg_color=status_colors.get(g, "gray"))
            except Exception:
                pass
        # Apparatus
        for unit_upper, app_data in run.get("apparatus", {}).items():
            g = self.global_apparatus.get(unit_upper, {}).get("runstatus", "AVAILABLE")
            app_data["runstatus"].set(g)
            try:
                app_data["runstatus_menu"].configure(fg_color=status_colors.get(g, "gray"))
            except Exception:
                pass

    def set_global_apparatus_status(self, unit: str, status: str) -> None:
        """
        Set an apparatus RUN status globally and reflect in ALL open run tabs.
        (Used by Assigned/toolbar actions; no per-run log spam here.)
        """
        unit = unit.upper()
        if unit not in self.global_apparatus:
            return
        self.global_apparatus[unit]["runstatus"] = status
        # Reflect in every open tab’s apparatus widgets
        for rn, run in self.run_tabs.items():
            app = run.get("apparatus", {}).get(unit)
            if not app:
                continue
            app["runstatus"].set(status)
            try:
                app["runstatus_menu"].configure(fg_color=status_colors.get(status, "gray"))
            except Exception:
                pass

    def set_default_responder_shift(self, tabview, run_number):
        """Pick the active shift from the day/time & set up per-shift memory for this run."""
        now = datetime.now()
        week = now.isocalendar()[1]
        is_odd = (week % 2) == 1
        day_idx = now.weekday()  # 0=Mon
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        schedule = {
            "odd": {
                "Mon": {"day": "C", "night": "D"},
                "Tue": {"day": "C", "night": "D"},
                "Wed": {"day": "A", "night": "B"},
                "Thu": {"day": "A", "night": "B"},
                "Fri": {"day": "C", "night": "D"},
                "Sat": {"day": "C", "night": "D"},
                "Sun": {"day": "C", "night": "D"},
            },
            "even": {
                "Mon": {"day": "A", "night": "B"},
                "Tue": {"day": "A", "night": "B"},
                "Wed": {"day": "C", "night": "D"},
                "Thu": {"day": "C", "night": "D"},
                "Fri": {"day": "A", "night": "B"},
                "Sat": {"day": "A", "night": "B"},
                "Sun": {"day": "A", "night": "B"},
            },
        }
        sched = schedule["odd" if is_odd else "even"]

        hour = now.hour
        if hour < 6:
            ref_day = day_names[(day_idx - 1) % 7]
            current_shift = sched[ref_day]["night"]
        elif 6 <= hour < 18:
            ref_day = day_names[day_idx]
            current_shift = sched[ref_day]["day"]
        else:
            ref_day = day_names[day_idx]
            current_shift = sched[ref_day]["night"]

        self.run_tabs.setdefault(run_number, {})
        self.run_tabs[run_number]["current_shift"] = current_shift
        self.active_shift = current_shift

        try:
            if tabview is not None:
                tabview.set(f"Shift {current_shift}")
        except Exception:
            pass

        # Initialize per-run/per-shift memory
        for shift_key, members in getattr(self, "responder_shifts", {}).items():
            for unit, _ in members:
                k = f"{unit}_{run_number}_{shift_key}"
                self.status_memory[k] = "AVAILABLE" if shift_key == current_shift else "--"

        # Apply to visible widgets
        self.refresh_status_badges(run_number)

    def refresh_status_badges(self, run_number):
        rw = self.run_tabs.get(run_number, {})
        widgets = rw.get("responder_widgets", {})
        widget_shift_map = rw.get("responder_widget_shift", {})
        # static
        for unit, (var, menu) in widgets.items():
            shift_key = widget_shift_map.get(unit)
            if not shift_key:
                continue
            k = f"{unit}_{run_number}_{shift_key}"
            want = self.status_memory.get(k, "--")
            # If globally UNAVAILABLE, override display
            if unit in self.globally_unavailable or self.global_statuses.get(unit) == "UNAVAILABLE":
                want = "UNAVAILABLE"
            var.set(want)
            try:
                menu.configure(fg_color=status_colors.get(want, "gray"))
            except Exception:
                pass
        # dynamic
        for slot_idx, slot in rw.get("dropdowns", {}).items():
            shift_key = slot.get("shift")
            k = f"dyn{slot_idx}_{run_number}_{shift_key}"
            want = self.status_memory.get(k, "--")
            slot["status_var"].set(want)
            try:
                slot["status_widget"].configure(fg_color=status_colors.get(want, "gray"))
            except Exception:
                pass

    # ==============================
    # Shift Log actions (no timestamps)
    # ==============================
    def walkthrough_completed(self):
        resp = (self.wt_resp_entry.get() or "").strip()
        desc = (self.wt_desc_entry.get() or "").strip()
        if not resp or not desc:
            messagebox.showwarning("Check", "Please fill in both Responder(s) and Check before completing.")
            return
        line = f"{self.username}: Check COMPLETED — {desc} — Responders: {resp}"
        self.shift_append_line(line)
        self.wt_resp_entry.delete(0, "end")
        self.wt_desc_entry.delete(0, "end")

    def shift_append_line(self, line: str) -> None:
        path = shift_current_log_path(current_shift_name(self))
        lock = FileLock(path + ".lock")
        with lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line.rstrip("\n") + "\n")

    def shift_read_all(self) -> str:
        path = shift_current_log_path(current_shift_name(self))
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def toggle_needs_attention(self):
        # Simple toggle that logs a centered red line on the Shift Log
        self.needs_attention_active = not self.needs_attention_active
        if self.needs_attention_active:
            self.shift_mark_attention()
        # (You can add flashing UI later if you want.)

    def update_lastused_timestamp(self, run_number: str, unit: str, responder: str):
        unit_upper = unit.upper()
        # Update global copy
        self.global_apparatus[unit_upper]["lastusedby"] = responder
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.global_apparatus[unit_upper]["timestamp"] = ts
        # Reflect in all open tabs
        for rn, data in self.run_tabs.items():
            app = data.get("apparatus", {}).get(unit_upper)
            if app:
                app["lastusedby"].set(responder)
                app["timestamp"].set(ts)
                try:
                    app["timestamp_entry"].configure(state="normal")
                    app["timestamp_entry"].delete(0, "end")
                    app["timestamp_entry"].insert(0, ts)
                    app["timestamp_entry"].configure(state="disabled")
                except Exception:
                    pass
        self.save_apparatus_state()
        self.append_note(run_number, f"{unit_upper} last used by set to {responder}")

    def shift_send_note(self) -> None:
        msg = self.shift_entry.get().strip()
        if not msg:
            return
        line = f"{self.username}: {msg}"  # NO timestamp
        self.shift_append_line(line)
        self.shift_entry.delete(0, "end")
        self.update_typing_state(is_typing=False)

    def read_typing_state(self) -> dict:
        path = typing_state_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def write_typing_state(self, state: dict) -> None:
        path = typing_state_path()
        lock = FileLock(path + ".lock")
        with lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f)

    def update_typing_state(self, is_typing: bool) -> None:
        now_ts = time.time()
        if is_typing and (now_ts - self._last_typing_emit) < 1:
            return  # throttle ~1/sec
        self._last_typing_emit = now_ts

        state = self.read_typing_state()
        s = current_shift_name(self)
        state.setdefault("shifts", {}).setdefault(s, {})
        state["shifts"][s][self.username] = {
            "typing": bool(is_typing),
            "ts": now_stamp()
        }
        self.write_typing_state(state)

    def destroy(self):
    # prevent background callbacks from firing after the app closes
        self._destroying = True
        for attr in ("_shift_poll_id", "_typing_poll_id"):
            try:
                pid = getattr(self, attr, None)
                if pid:
                    self.after_cancel(pid)
            except Exception:
                pass
        try:
            super().destroy()
        except Exception:
            pass


    def poll_typing_state(self) -> None:
        try:
            state = self.read_typing_state()
            s = current_shift_name(self)
            typers = []
            if state and "shifts" in state and s in state["shifts"]:
                for user, info in state["shifts"][s].items():
                    if info.get("typing"):
                        typers.append(user)
            if typers:
                self.typing_label_var.set(f"{', '.join(typers)} {'is' if len(typers)==1 else 'are'} typing…")
            else:
                self.typing_label_var.set("No one is typing…")
        except Exception:
            pass
        finally:
            if getattr(self, "_destroying", False):
                return
            try:
                self._typing_poll_id = self.after(700, self.poll_typing_state)
            except Exception:
                pass


    def set_global_responder_status(self, unit: str, status: str) -> None:
        """Set a responder's status globally and reflect in ALL open run tabs (static + dynamic)."""
        unit = unit.upper()
        self.global_statuses[unit] = status

        # Maintain the global UNAVAILABLE latch so new tabs also reflect it
        if status == "UNAVAILABLE":
            self.globally_unavailable.add(unit)
        else:
            self.globally_unavailable.discard(unit)

        # --- Static responder widgets ---
        for rn, run in self.run_tabs.items():
            widgets = run.get("responder_widgets", {})
            widget_shift_map = run.get("responder_widget_shift", {})
            if unit in widgets:
                var, menu = widgets[unit]
                var.set(status)
                try:
                    menu.configure(fg_color=status_colors.get(status, "gray"))
                except Exception:
                    pass
                shift_key = widget_shift_map.get(unit)
                if shift_key:
                    mem_key = f"{unit}_{rn}_{shift_key}"
                    self.status_memory[mem_key] = status

        # --- Dynamic responder slots ---
        for rn, run in self.run_tabs.items():
            for idx, slot in run.get("dropdowns", {}).items():
                name_val = slot["name_var"].get()
                if name_val and name_val != "Responder" and name_val.split()[0].upper() == unit:
                    slot["status_var"].set(status)
                    try:
                        slot["status_widget"].configure(fg_color=status_colors.get(status, "gray"))
                    except Exception:
                        pass
                    # keep per-run memory aligned
                    shift_key = slot.get("shift")
                    if shift_key:
                        mem_key = f"dyn{idx}_{rn}_{shift_key}"
                        self.status_memory[mem_key] = status

    def end_shift_archive(self) -> None:
        s = current_shift_name(self)
        src = shift_current_log_path(s)
        if not os.path.exists(src):
            messagebox.showinfo("End Shift", "No current shift log to archive.")
            return

        # Closing line (no timestamp)
        self.shift_append_line(f"{self.username}: Shift ended; archiving.")

        with open(src, "r", encoding="utf-8") as f:
            content = f.read()

        header = (
            f"PPM Shift Summary\n"
            f"Date: {today_stamp()}\n"
            f"Shift: {s}\n"
            f"Archived by: {self.username}\n"
            + "=" * 60 + "\n\n"
        )
        summary_text = header + content

        out = shift_archive_log_path(s)
        n = 1
        while os.path.exists(out):
            out = shift_archive_log_path(s, suffix=str(n))
            n += 1

        with open(out, "w", encoding="utf-8") as f:
            f.write(summary_text)

        try:
            os.remove(src)
        except OSError:
            pass

        messagebox.showinfo("End Shift", f"Shift archived:\n{os.path.basename(out)}")

    # ==============================
    # Status changes (per-run vs global)
    # ==============================
    def append_note(self, run_number: str, text: str, skip_timestamp: bool = False) -> None:
        """Append to RUN notes; optional timestamp suppression (used for caller/location/nature)."""
        notes_widget = self.run_tabs[run_number]["notes"]
        current_text = notes_widget.get("1.0", "end-1c")

        # If last line is just a timestamp prompt, remove it to keep lines tidy
        if current_text:
            last_line = current_text.split("\n")[-1]
            if (last_line.startswith("[") and "]" in last_line
                    and last_line.count("]") == 1
                    and last_line.split("]")[1].strip() == ""):
                chars_to_delete = len(last_line) + 1
                notes_widget.delete(f"end-{chars_to_delete}c", "end-1c")

        if not skip_timestamp:
            ts = datetime.now().strftime("%H:%M:%S")
            new_current = notes_widget.get("1.0", "end-1c")
            if new_current and not new_current.endswith("\n"):
                notes_widget.insert("end", "\n")
            notes_widget.insert("end", f"[{ts}] {text}\n")
        else:
            # No timestamp
            new_current = notes_widget.get("1.0", "end-1c")
            if new_current and not new_current.endswith("\n"):
                notes_widget.insert("end", "\n")
            notes_widget.insert("end", text + "\n")

        notes_widget.see("end")

    def bind_status_color(self, var: tk.StringVar, widget: ctk.CTkOptionMenu) -> None:
        def update_color(*_):
            widget.configure(fg_color=status_colors.get(var.get(), "gray"))
        var.trace_add("write", update_color)

    def status_change(self, run_number, unit, new_status, shift_key=None, log=False, log_source=""):
        """
        STATIC responder status change.
        Now GLOBAL for all statuses (UNAVAILABLE still logs to Shift Log).
        """
        rw = self.run_tabs.get(run_number, {})
        if not shift_key:
            shift_key = rw.get("responder_widget_shift", {}).get(unit) or rw.get("current_shift")
        if not shift_key:
            return

        # UNAVAILABLE → latch globally + shift log
        if new_status == "UNAVAILABLE":
            self.set_global_responder_status(unit, "UNAVAILABLE")
            self.shift_append_line(f"{self.username}: {unit} marked UNAVAILABLE")
            return

        # If clearing from UNAVAILABLE to something else, unlock globally first
        if unit in self.globally_unavailable and new_status != "UNAVAILABLE":
            self.globally_unavailable.discard(unit)

        # GLOBAL propagate for all other statuses
        self.set_global_responder_status(unit, new_status)

        # Per-run memory (kept for the current run's shift snapshot)
        mem_key = f"{unit}_{run_number}_{shift_key}"
        prev_status = self.status_memory.get(mem_key, None)
        self.status_memory[mem_key] = new_status

        # Update THIS run's widget (already touched by set_global_responder_status, but safe)
        widgets = rw.get("responder_widgets", {})
        widget_shift_map = rw.get("responder_widget_shift", {})
        if unit in widgets and widget_shift_map.get(unit) == shift_key:
            var, menu = widgets[unit]
            var.set(new_status)
            try:
                menu.configure(fg_color=status_colors.get(new_status, "gray"))
            except Exception:
                pass

        # Optional run-note dedupe
        if log and prev_status != new_status and not getattr(self, '_updating_from_assignment', False):
            key = (run_number, unit)
            last = self.last_status_updates.get(key)
            now_ts = time.time()
            if not last or last[0] != new_status or (now_ts - last[1]) > 1.0:
                via = " (dropdown)" if log_source == "dropdown" else ""
                self.append_note(run_number, f"{unit} set to {new_status}{via}" if via else f"{unit} is {new_status}")
                self.last_status_updates[key] = (new_status, now_ts)
                self.last_status_updates[key] = (new_status, now_ts)

    def dynamic_status_change(self, run_number, slot_idx, new_status, log=False):
        """
        DYNAMIC responder status change.
        Now GLOBAL for all statuses (UNAVAILABLE still logs to Shift Log).
        """
        run_meta = self.run_tabs.get(run_number, {})
        slot = run_meta.get("dropdowns", {}).get(slot_idx)
        if not slot:
            return

        slot_shift = slot.get("shift")
        if not slot_shift:
            return

        name_val = slot["name_var"].get() or ""
        unit_code = name_val.split()[0].upper() if name_val and name_val != "Responder" else None

        # UNAVAILABLE → latch globally + shift log
        if new_status == "UNAVAILABLE":
            if unit_code:
                self.set_global_responder_status(unit_code, "UNAVAILABLE")
                self.shift_append_line(f"{self.username}: {unit_code} marked UNAVAILABLE")
            slot["status_var"].set("UNAVAILABLE")
            try:
                slot["status_widget"].configure(fg_color=status_colors.get("UNAVAILABLE", "gray"))
            except Exception:
                pass
            return

        # If clearing a previously latched UNAVAILABLE
        if unit_code and (unit_code in self.globally_unavailable) and new_status != "UNAVAILABLE":
            self.globally_unavailable.discard(unit_code)

        # GLOBAL propagate for all other statuses
        if unit_code:
            self.set_global_responder_status(unit_code, new_status)

        # Keep per-run memory for this slot
        mem_key = f"dyn{slot_idx}_{run_number}_{slot_shift}"
        prev_status = self.status_memory.get(mem_key, slot["status_var"].get())
        self.status_memory[mem_key] = new_status

        slot["status_var"].set(new_status)
        try:
            slot["status_widget"].configure(fg_color=status_colors.get(new_status, "gray"))
        except Exception:
            pass

        if log and prev_status != new_status and not getattr(self, '_updating_from_assignment', False):
            key = (run_number, f"DYN{slot_idx}")
            last = self.last_status_updates.get(key)
            now_ts = time.time()
            if not last or last[0] != new_status or (now_ts - last[1]) > 1.0:
                code = unit_code if unit_code else f"DYN{slot_idx}"
                self.append_note(run_number, f"{code} set to {new_status} (dropdown)")
                self.last_status_updates[key] = (new_status, now_ts)

    def _update_dynamic_matching_unit(self, run_number: str, unit_code: str, status: str) -> None:
        run = self.run_tabs.get(run_number, {})
        current_shift = run.get("current_shift")
        if not current_shift:
            return
        dropdowns = run.get("dropdowns", {})
        for idx, slot in dropdowns.items():
            name_val = slot["name_var"].get()
            if not name_val or name_val == "Responder":
                continue
            if slot.get("shift") != current_shift:
                continue
            if name_val.split()[0].upper() == unit_code:
                self._updating_from_assignment = True
                self.dynamic_status_change(run_number, idx, status, log=False)
                self._updating_from_assignment = False
                break

    def refresh_unit_everywhere(self, unit):
        """
        Reflect a unit's GLOBAL status in ALL runs' static widgets.
        Used for UNAVAILABLE and for submission resets.
        """
        status = self.global_statuses.get(unit, "AVAILABLE")
        for rn, run in self.run_tabs.items():
            widgets = run.get("responder_widgets", {})
            widget_shift_map = run.get("responder_widget_shift", {})
            if unit in widgets:
                var, menu = widgets[unit]
                var.set(status)
                try:
                    menu.configure(fg_color=status_colors.get(status, "gray"))
                except Exception:
                    pass
                shift_key = widget_shift_map.get(unit)
                if shift_key:
                    mem_key = f"{unit}_{rn}_{shift_key}"
                    self.status_memory[mem_key] = status

    def dynamic_responder_selected(self, run_number: str, full_name: str, index: int) -> None:
        """Persist dynamic name selection across runs and auto-set to AVAILABLE."""
        run = self.run_tabs.get(run_number, {})
        slot = run.get("dropdowns", {}).get(index)
        if not slot:
            return

        if full_name and full_name != "Responder":
            self.persistent_dynamic_responders[index] = full_name
            # Auto-set to AVAILABLE when selected
            unit_code = full_name.split()[0].upper()
            self.set_global_responder_status(unit_code, "AVAILABLE")
            slot["status_var"].set("AVAILABLE")
            try:
                slot["status_widget"].configure(fg_color=status_colors.get("AVAILABLE", "gray"))
            except Exception:
                pass
        else:
            self.persistent_dynamic_responders.pop(index, None)

        for rn, run_data in self.run_tabs.items():
            slot_data = run_data.get("dropdowns", {}).get(index)
            if slot_data:
                slot_data["name_var"].set(full_name)
                if not full_name or full_name == "Responder":
                    slot_data["status_var"].set("--")
                else:
                    # Set to AVAILABLE in all tabs
                    slot_data["status_var"].set("AVAILABLE")
                try:
                    current_status = slot_data["status_var"].get()
                    slot_data["status_widget"].configure(fg_color=status_colors.get(current_status, "gray"))
                except Exception:
                    pass

        if full_name and full_name != "Responder":
            self.append_note(run_number, f"Responder added: {full_name}", skip_timestamp=True)

    def log_apparatus_runstatus(self, run_number: str, unit: str, status: str, propagate_global: bool = False, log: bool = True) -> None:
        """
        Update apparatus RUN status.
        - Updates this run's UI state.
        - Logs ONE grouped line that includes the apparatus + its linked responders.
        """
        unit_upper = unit.upper()
        rn_data = self.run_tabs.get(run_number, {})
        app_data = rn_data.get("apparatus", {}).get(unit_upper)
        if not app_data:
            return

        prev = app_data["runstatus"].get()
        app_data["runstatus"].set(status)
        try:
            app_data["runstatus_menu"].configure(fg_color=status_colors.get(status, "gray"))
        except Exception:
            pass

        # If status actually changed, propagate to linked responders and log ONCE, grouped.
        if prev != status:
            self.update_responders_from_apparatus(run_number, unit_upper, status)

    def update_apparatus_from_responder(self, run_number: str, unit: str, status: str):
        """Update linked apparatus when responder status changes"""
        if not hasattr(self, 'apparatus_responder_links'):
            return

        links = self.apparatus_responder_links.get(run_number, {})
        for app_unit, resp_units in links.items():
            if unit.upper() in [u.upper() for u in resp_units]:
                self.log_apparatus_runstatus(
                    run_number,
                    app_unit,
                    status,
                    propagate_global=False,
                    log=False
                )

    def update_responders_from_apparatus(self, run_number: str, app_unit: str, status: str):
        """
        When an apparatus status changes, set the same status for ONLY its linked responders
        (for this run) and log a SINGLE grouped line:

          [HH:MM:SS] 44, 45, E2 has been updated to dispatched.
          [HH:MM:SS] 42, 48, M2 are ON SCENE.

        No cross-team carryover.
        """
        # Figure out who is linked to this apparatus on this run
        linked_resp = []
        if hasattr(self, "apparatus_responder_links"):
            links = self.apparatus_responder_links.get(run_number, {})
            linked_resp = links.get(app_unit.upper(), []) or []

        # Update responder globals silently (no per-unit log spam)
        for unit in linked_resp:
            self.set_global_responder_status(unit.upper(), status)

        # Build the grouped unit list (responders + apparatus)
        grouped_units = [u.upper() for u in linked_resp] + [app_unit.upper()]

        if not grouped_units:
            return  # nothing to log

        units_str = ", ".join(grouped_units)
        if status == "DISPATCHED":
            line = f"{units_str} has been updated to dispatched."
        else:
            verb = "are" if len(grouped_units) > 1 else "is"
            line = f"{units_str} {verb} {status}."

        self.append_note(run_number, line)

    def update_linked_units_status(self, run_number: str, triggering_units: list, new_status: str):
        """
        When a responder change should move its linked apparatus, update ONLY that apparatus
        and log a SINGLE grouped line for just that team.
        """
        if not hasattr(self, "apparatus_responder_links"):
            return

        links = self.apparatus_responder_links.get(run_number, {})
        # Which apparatus are linked to ANY of the triggering responders?
        linked_apparatus = [
            app for app, resp_units in links.items()
            if any(u.upper() in {ru.upper() for ru in resp_units} for u in triggering_units)
        ]

        if not linked_apparatus:
            return

        # Apply status to each linked apparatus silently (UI update + no extra logs)
        for app in linked_apparatus:
            self.log_apparatus_runstatus(run_number, app, new_status, propagate_global=False, log=False)

        # Grouped sentence: responders + apparatus (ONLY this team)
        team = [u.upper() for u in triggering_units] + [a.upper() for a in linked_apparatus]
        units_str = ", ".join(team)
        if new_status == "DISPATCHED":
            line = f"{units_str} has been updated to dispatched."
        else:
            verb = "are" if len(team) > 1 else "is"
            line = f"{units_str} {verb} {new_status}."
        self.append_note(run_number, line)

    def log_apparatus_opstatus(self, run_number: str, unit: str, opstatus: str) -> None:
        unit_upper = unit.upper()
        # Update global persistent OP status immediately
        self.global_apparatus[unit_upper]["opstatus"] = opstatus
        # Reflect in ALL runs' UI
        for rn, data in self.run_tabs.items():
            app_data = data.get("apparatus", {}).get(unit_upper)
            if app_data:
                app_data["opstatus"].set(opstatus)
                try:
                    app_data["op_menu"].configure(fg_color=tag_colors.get(opstatus, "gray"))
                except Exception:
                    pass
        self.save_apparatus_state()
        self.append_note(run_number, f"{unit_upper} operational status set to {opstatus}")

    def log_apparatus_staging(self, run_number: str, unit: str, staging: str) -> None:
        """Update staging location for an apparatus globally, persist, and note it."""
        unit_upper = unit.upper()
        self.global_apparatus[unit_upper]["staging"] = staging
        for rn, data in self.run_tabs.items():
            app = data.get("apparatus", {}).get(unit_upper)
            if app:
                app["staging"].set(staging)
        self.save_apparatus_state()
        self.append_note(run_number, f"{unit_upper} staging set to {staging}")

    def update_assigned_units_status(self, run_number: str, status: str) -> None:
        """
        Update status ONLY for the team(s) named in the CURRENT Assigned field:
          - Responders listed there
          - Apparatus listed there
        No historical/carry-over apparatus.
        """
        if status is None:
            return

        run = self.run_tabs.get(run_number, {})
        if not run:
            return

        # Ensure current shift exists
        if not run.get("current_shift"):
            tv = run.get("tabview") if "tabview" in run else None
            if tv is not None:
                self.set_default_responder_shift(tv, run_number)

        # Parse CURRENT Assigned field
        field_text = ""
        try:
            field_text = run["fields"]["assigned"].get().strip()
        except Exception:
            pass

        apparatus_codes = {u for u, _ in apparatus_units}
        responders_now, apparatus_now = set(), set()
        if field_text:
            for part in field_text.split(","):
                code = part.strip().split()[0].upper()
                if not code:
                    continue
                if code in apparatus_codes:
                    apparatus_now.add(code)
                else:
                    responders_now.add(code)
        else:
            # Fallback to last-saved responders; no apparatus if none currently listed
            responders_now = set(u.upper() for u in run.get("assigned_units", []))
            apparatus_now = set()  # <- prevents old apparatus bleed-over

        if not responders_now and not apparatus_now:
            return

        grouped = []

        # Responders -> GLOBAL
        for unit in sorted(responders_now):
            self.set_global_responder_status(unit, status)
            grouped.append(unit)

        # Apparatus -> GLOBAL, but ONLY the ones currently in the field
        for unit in sorted(apparatus_now):
            self.set_global_apparatus_status(unit, status)
            grouped.append(unit)

        # Grouped log line
        if grouped:
            units_str = ", ".join(grouped)
            if status == "DISPATCHED":
                line = f"{units_str} has been updated to dispatched."
            else:
                verb = "are" if len(grouped) > 1 else "is"
                line = f"{units_str} {verb} {status}"
            if status == "UNAVAILABLE":
                self.shift_append_line(f"{self.username}: {line}")
            else:
                self.append_note(run_number, line)

    # ==============================
    # Submit / CSV / Preview
    # ==============================
    def validate_required_fields(self, run_number: str) -> bool:
        required = ["caller", "location", "nature"]
        missing = [
            f.capitalize()
            for f in required
            if not self.run_tabs[run_number]["fields"][f].get().strip()
        ]
        if missing:
            messagebox.showwarning(
                "Missing Fields",
                "Please complete the following before submitting:\n\n" + "\n".join(missing),
            )
        return not missing

    def submit_run(self, run_number: str) -> None:
        # Validate required fields
        if not self.validate_required_fields(run_number):
            return

        # --- optional: persist the run (best-effort, won't crash if helper differs/missing)
        try:
            fields = self.run_tabs[run_number]["fields"]
            notes_text = self.run_tabs[run_number]["notes"].get("1.0", "end").strip()
            run_data = {
                "run_number": run_number,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "caller": fields["caller"].get().strip(),
                "location": fields["location"].get().strip(),
                "nature": fields["nature"].get().strip(),
                "assigned_units": assigned_units,
                "notes": notes_text,
            }
            try:
                save_run_to_text(run_data)
            except Exception:
                try:
                    statuses = {}
                    apparatus_codes = {u for u, _ in apparatus_units}
                    assigned_line = run_data["assigned"]
                    items = [v.strip() for v in assigned_line.split(",") if v.strip()]
                    for item in items:
                        unit_code = item.split()[0].upper()
                        if not unit_code:
                            continue
                        statuses[unit_code] = {
                            "status": self.global_apparatus.get(unit_code, {}).get(
                                "runstatus", self.global_statuses.get(unit_code, "--")
                            ),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    save_run_to_log(run_data, statuses)
                except Exception:
                    pass
        except Exception:
            pass

        # --- Reset statuses for ONLY the team tied to this run ---
        apparatus_codes = {u for u, _ in apparatus_units}

        # (1) Parse current Assigned field live
        assigned_text = ""
        try:
            assigned_text = self.run_tabs[run_number]["fields"]["assigned"].get().strip()
        except Exception:
            pass

        responders_now, apparatus_now = set(), set()
        if assigned_text:
            for part in assigned_text.split(","):
                code = part.strip().split()[0].upper()
                if not code:
                    continue
                (apparatus_now if code in apparatus_codes else responders_now).add(code)

        # (2) Include saved responders for this run (if Enter was pressed earlier)
        for u in self.run_tabs[run_number].get("assigned_units", []):
            if u:
                responders_now.add(u.upper())

        # (3) Include any responders linked to apparatus for this run
        links = getattr(self, "apparatus_responder_links", {}).get(run_number, {})
        for app, resp_list in links.items():
            if app:
                apparatus_now.add(app.upper())
            for r in (resp_list or []):
                if r:
                    responders_now.add(r.upper())

        # (4) Include any responders that are marked active for this run
        #     (fixes cases where some members were dispatched earlier and not in the current field)
        try:
            for unit, runs in list(self.unit_active_runs.items()):
                if run_number in runs:
                    responders_now.add(unit.upper())
        except Exception:
            pass

        # helper: only reset a responder if this is their last active run
        def _is_last_active_run(unit_code: str) -> bool:
            runs = self.unit_active_runs.get(unit_code, set())
            return (runs == {run_number}) or (not runs)

        # Reset responders
        for unit in sorted(responders_now):
            if _is_last_active_run(unit):
                self.set_global_responder_status(unit, "AVAILABLE")
            # remove this run from active set either way
            try:
                self.unit_active_runs.get(unit, set()).discard(run_number)
                if not self.unit_active_runs.get(unit):
                    self.unit_active_runs.pop(unit, None)
            except Exception:
                pass

        # Reset apparatus for THIS run’s team only
        for unit in sorted(apparatus_now):
            self.set_global_apparatus_status(unit, "AVAILABLE")

        # Log a single grouped line (Run Notes) and also write to the Shift Log
        grouped = ", ".join(sorted(responders_now) + sorted(apparatus_now))
        if grouped:
            self.append_note(run_number, f"{grouped} set back to AVAILABLE (run submitted)")
            try:
                self.shift_append_line(f"{self.username}: {run_number} submitted. Reset to AVAILABLE: {grouped}")
            except Exception:
                pass
        else:
            try:
                self.shift_append_line(f"{self.username}: {run_number} submitted. (nothing to reset)")
            except Exception:
                pass

        # Clear per-run links/assignments so nothing carries over
        self.run_unit_assignments.pop(run_number, None)
        if hasattr(self, "apparatus_responder_links"):
            self.apparatus_responder_links.pop(run_number, None)

        # close the tab after submission
        try:
            messagebox.showinfo("Submitted", f"{run_number} submitted.")
        except Exception:
            pass
        self.close_run_tab(run_number)


    def show_run_summary(self, run_number: str) -> None:
        summary = tk.Toplevel(self)
        self._force_on_top(summary)
        summary.title("Run Summary")
        summary.geometry("600x700")
        summary.grab_set()

        outer_frame = ctk.CTkFrame(summary)
        outer_frame.pack(fill="both", expand=True, padx=10, pady=10)

        text = tk.Text(outer_frame, wrap="word", font=("Arial", 13), height=30)
        text.pack(fill="both", expand=True, pady=(0, 10))

        fields = self.run_tabs[run_number]["fields"]
        notes = self.run_tabs[run_number]["notes"].get("1.0", "end").strip()

        text.insert("end", f"📋 Run Summary for {run_number}\n\n")
        text.insert("end", f"📞 Caller: {fields['caller'].get()}\n")
        text.insert("end", f"📍 Location: {fields['location'].get()}\n")
        text.insert("end", f"🔥 Nature: {fields['nature'].get()}\n")
        text.insert("end", f"🚒 Assigned Units: {fields['assigned'].get()}\n\n")
        text.insert("end", "📝 Notes:\n" + notes + "\n\n")
        text.config(state="disabled")

        def submit_and_close():
            try:
                summary.destroy()
            except Exception:
                pass
            self.submit_run(run_number)

        ctk.CTkButton(
            outer_frame,
            text="✅ Confirm & Submit",
            command=submit_and_close
        ).pack(pady=(0, 5))

    def export_to_csv(self, run_number: str) -> None:
        filename = f"{run_number.replace(' ', '_')}.csv"
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Field", "Value"])
                for key, entry in self.run_tabs[run_number]["fields"].items():
                    writer.writerow([key, entry.get()])
                writer.writerow([])
                writer.writerow(["Notes"])
                writer.writerow([self.run_tabs[run_number]["notes"].get("1.0", "end").strip()])
            messagebox.showinfo("Export", f"Run exported to {filename}.", parent=self)
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not export CSV:\n{exc}", parent=self)

    def _center_window(self, win):
        try:
            win.update_idletasks()
            ww = win.winfo_width() or win.winfo_reqwidth()
            wh = win.winfo_height() or win.winfo_reqheight()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = max(0, (sw - ww) // 2)
            y = max(0, (sh - wh) // 2)
            win.geometry(f"{ww}x{wh}+{x}+{y}")
        except Exception as e:
            print("center_window failed:", e)

    def _bring_to_front(self, win):
        """Try hard to put a Toplevel-like window in front of CallForm."""
        try:
            # make it a transient child of the CallForm window (if supported)
            try: win.transient(self)
            except Exception: pass

            # raise + focus
            try: win.lift()
            except Exception: pass
            try: win.focus_force()
            except Exception: pass

            # briefly set topmost so it jumps in front, then release
            try:
                win.attributes("-topmost", True)
                self.after(300, lambda: (win.attributes("-topmost", False)))
            except Exception:
                pass
        except Exception:
            pass


        # Re-assert a few times (Windows sometimes drops topmost on focus churn)
        def _nudge():
            try:
                win.lift()
                win.attributes("-topmost", True)
            except Exception:
                pass

        self.after(50, _nudge)
        self.after(250, _nudge)
        self.after(1000, _nudge)

        # If it loses focus, yank it back on top
        try:
            win.bind("<FocusOut>", lambda *_: _nudge())
        except Exception:
            pass

            def _close():
                try: win.grab_release()
                except Exception: pass
                try: win.destroy()
                except Exception: pass
            win.protocol("WM_DELETE_WINDOW", _close)
        except Exception as e:
            print("force_on_top failed:", e)




    # ==============================
    # Contacts / Alerts
    # ==============================
    def contact_action(self, run_number: str, name: str, phone: str) -> None:
        self.append_note(run_number, f"Contacted {name} ({phone})")
        if name in ALERT_CONTACTS:
            try:
                send_email_alert("Contacted", f"{name} was contacted.")
            except Exception:
                pass

    def needs_addressed(self, run_number: str) -> None:
        # Add to run notes with username
        self.append_note(run_number, f"⚠️ Needs to be reviewed (submitted by {self.username})")
        try:
            send_email_alert("Attention Needed", f"'{run_number}' needs to be reviewed by {self.username}.")
        except Exception:
            pass

    # ==============================
    # Persistence for apparatus meta
    # ==============================
    def save_apparatus_state(self) -> None:
        data = {}
        for unit, state in self.global_apparatus.items():
            data[unit] = {
                "opstatus": state.get("opstatus", "Ready"),
                "lastusedby": state.get("lastusedby", "Last Used By"),
                "staging": state.get("staging", staging_locations[0]),
                "timestamp": state.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                # runstatus not persisted across restarts by design
            }
        try:
            with open(APPARATUS_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def load_apparatus_state(self) -> None:
        if not os.path.exists(APPARATUS_STATE_FILE):
            return
        try:
            with open(APPARATUS_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for unit, state in data.items():
                unit_upper = unit.upper()
                if unit_upper in self.global_apparatus:
                    for key in ["opstatus", "lastusedby", "staging", "timestamp"]:
                        if key in state:
                            self.global_apparatus[unit_upper][key] = state[key]
        except Exception:
            pass

    def _bring_to_front(self, win):
        """Try hard to put a Toplevel-like window in front of CallForm."""
        try:
            # make it a transient child of the CallForm window (if supported)
            try: win.transient(self)
            except Exception: pass

            # raise + focus
            try: win.lift()
            except Exception: pass
            try: win.focus_force()
            except Exception: pass

            # briefly set topmost so it jumps in front, then release
            try:
                win.attributes("-topmost", True)
                self.after(300, lambda: (win.attributes("-topmost", False)))
            except Exception:
                pass
        except Exception:
            pass


    # ==============================
    # Navigation / Windows
    # ==============================
    def close_run_tab(self, run_number: str) -> None:
        try:
            self.main_tabview.delete(run_number)
            del self.run_tabs[run_number]
            if not self.run_tabs:
                self.create_run_tab()
        except Exception as e:
            messagebox.showerror("Tab Close Failed", f"Could not close run tab:\n{e}")

    def confirm_close_run(self, run_number: str) -> None:
        """Confirm and close a run tab without submitting"""
        if messagebox.askyesno("Close Run", f"Close {run_number} without submitting?\nAll data will be lost."):
            self.close_run_tab(run_number)

    def confirm_exit(self) -> None:
        if messagebox.askyesno("Exit", "Return to dashboard?"):
            try:
                self.destroy()
            except Exception:
                pass
            try:
                self.return_to_dashboard()
            except Exception:
                pass

    def confirm_sign_out(self) -> None:
        if messagebox.askyesno("Sign Out", "Are you sure you want to sign out?"):
            try:
                self.destroy()
            except Exception:
                pass
            try:
                import subprocess
                subprocess.Popen(["python", "main.py"])
            except Exception:
                pass

    def _force_on_top(self, win) -> None:
        """Raise a CTkToplevel/Tk window above CallForm and keep focus."""
        if not win or not hasattr(win, "winfo_exists") or not win.winfo_exists():
            return
        try:
            # Make child of CallForm so it stays above
            win.transient(self)
        except Exception:
            pass
        try:
            win.lift()
        except Exception:
            pass
        try:
            win.focus_force()
        except Exception:
            pass
        # Toggle topmost briefly so it pops in front
        try:
            win.attributes("-topmost", True)
            win.after(250, lambda: win.attributes("-topmost", False))
        except Exception:
            pass


    # "Dispatch Logs" (formerly Run Reports)
    def open_run_reports(self) -> None:
        try:
            try:
                win = RunReportsWindow(self, self.username)
            except TypeError:
                win = RunReportsWindow(self)
            # bring to front
            self._bring_to_front(win)
        except Exception as exc:
            messagebox.showerror("Dispatch Logs Error", f"Unable to open dispatch logs: {exc}", parent=self)

    # "Run Reports" (formerly Incident Reports)
    def open_incident_reports(self) -> None:
        try:
            try:
                win = IncidentReportForm(self, self.username)
            except TypeError:
                win = IncidentReportForm(self)
            self._force_on_top(win, center=True)
        except Exception as exc:
            messagebox.showerror("Run Reports Error", f"Unable to open run reports: {exc}", parent=self)

# --- Safety net: bind nav handlers if they were mis-indented ---
import types

if not hasattr(CallForm, "confirm_exit"):
    def _cf_confirm_exit(self):
        if messagebox.askyesno("Exit", "Return to dashboard?"):
            try: self.destroy()
            except Exception: pass
            try: self.return_to_dashboard()
            except Exception: pass
    CallForm.confirm_exit = _cf_confirm_exit

if not hasattr(CallForm, "confirm_sign_out"):
    def _cf_confirm_sign_out(self):
        if messagebox.askyesno("Sign Out", "Are you sure you want to sign out?"):
            try: self.destroy()
            except Exception: pass
            try:
                import subprocess
                subprocess.Popen(["python", "main.py"])
            except Exception:
                pass
    CallForm.confirm_sign_out = _cf_confirm_sign_out

if not hasattr(CallForm, "close_run_tab"):
    def _cf_close_run_tab(self, run_number: str):
        try:
            self.main_tabview.delete(run_number)
            del self.run_tabs[run_number]
            if not self.run_tabs:
                self.create_run_tab()
        except Exception as e:
            messagebox.showerror("Tab Close Failed", f"Could not close run tab:\n{e}")
    CallForm.close_run_tab = _cf_close_run_tab

if not hasattr(CallForm, "open_run_reports"):
    def _cf_open_run_reports(self):
        try:
            try: RunReportsWindow(self, self.username)
            except TypeError: RunReportsWindow(self)
        except Exception as exc:
            messagebox.showerror("Dispatch Logs Error", f"Unable to open dispatch logs: {exc}")
    CallForm.open_run_reports = _cf_open_run_reports

if not hasattr(CallForm, "open_incident_reports"):
    def _cf_open_incident_reports(self):
        try: IncidentReportForm(self)
        except Exception as exc:
            messagebox.showerror("Run Reports Error", f"Unable to open run reports: {exc}")
    CallForm.open_incident_reports = _cf_open_incident_reports
# --- end safety net ---


# ==============================
# Entry point
# ==============================
if __name__ == "__main__":
    app = CallForm(username="User", return_to_dashboard=lambda: print("Return to dashboard"))
    app.mainloop()

