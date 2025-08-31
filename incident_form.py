import customtkinter as ctk
import sqlite3
from datetime import datetime

DB_FILE = "ppm.db"

class IncidentReportForm(ctk.CTkToplevel):
    def __init__(self, parent, call_id=None, prefill_data=None, username=""):
        super().__init__(parent)
        self.call_id = call_id
        self.username = username
        self.prefill_data = prefill_data or {}

        self.title("Incident Report Form")
        self.geometry("700x500")
        self.configure(padx=20, pady=20)

        ctk.CTkLabel(self, text="Incident Report", font=("Arial", 18, "bold")).pack(pady=10)

        self.notes = ctk.CTkTextbox(self, wrap="word", width=660, height=300)
        self.notes.pack(pady=10)

        # Pre-fill data from linked call if available
        if self.prefill_data:
            note = f"Caller: {self.prefill_data.get('caller')}\n"
            note += f"Location: {self.prefill_data.get('location')}\n"
            note += f"Nature: {self.prefill_data.get('nature')}\n"
            note += f"Units: {self.prefill_data.get('unit')}\n"
            note += f"Notes from Dispatch:\n{self.prefill_data.get('notes')}\n\nResponder Notes:\n"
            self.notes.insert("1.0", note)

        ctk.CTkButton(self, text="Submit Incident Report", command=self.save_incident).pack(pady=10)
        ctk.CTkButton(self, text="Close", command=self.destroy).pack()

    def save_incident(self):
        incident_text = self.notes.get("1.0", "end").strip()
        if not incident_text:
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS incident_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER,
                username TEXT,
                timestamp TEXT,
                report TEXT
            )
        ''')
        c.execute("INSERT INTO incident_reports (call_id, username, timestamp, report) VALUES (?, ?, ?, ?)",
                  (self.call_id, self.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), incident_text))
        conn.commit()
        conn.close()
        self.destroy()
