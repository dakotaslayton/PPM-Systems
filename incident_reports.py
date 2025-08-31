import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from database import connect

class IncidentReportForm(ctk.CTkToplevel):
    def __init__(self, parent, run_data=None):
        super().__init__()
        self.title("Incident Reports")
        self.geometry("1000x600")
        self.parent = parent

        self.run_listbox = None
        self.run_data = run_data
        self.selected_run_id = None

        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.incident_text = tk.Text(self.right_frame, wrap="word", bg="black", fg="white")
        self.incident_text.pack(fill="both", expand=True, pady=(0, 10))

        self.save_button = ctk.CTkButton(self.right_frame, text="Save Incident Report", command=self.save_report)
        self.save_button.pack(pady=(0, 10))

        if run_data:
            self.load_from_file_data()
        else:
            self.run_listbox = tk.Listbox(self, width=30)
            self.run_listbox.pack(side="left", fill="y", padx=10, pady=10)
            self.run_listbox.bind("<<ListboxSelect>>", self.load_run_data)
            self.load_runs()

    def load_from_file_data(self):
        rd = self.run_data
        self.incident_text.insert("end", f"Run Number: {rd.get('RunNumber', '')}\n")
        self.incident_text.insert("end", f"Caller: {rd.get('Caller', '')}\n")
        self.incident_text.insert("end", f"Location: {rd.get('Location', '')}\n")
        self.incident_text.insert("end", f"Nature: {rd.get('Nature', '')}\n")
        self.incident_text.insert("end", f"Assigned Units: {rd.get('Assigned', '')}\n")
        self.incident_text.insert("end", f"Timestamp: {rd.get('Timestamp', '')}\n\n")

        self.incident_text.insert("end", "Run Notes:\n" + "\n".join(rd.get("Notes", [])) + "\n\n")

        if rd.get("Statuses"):
            self.incident_text.insert("end", "Responder Statuses:\n")
            for unit, status, ts in rd["Statuses"]:
                self.incident_text.insert("end", f"{unit}: {status} at {ts}\n")

        self.save_button.configure(state="disabled")

    def load_runs(self):
        self.run_listbox.delete(0, "end")
        with connect() as conn:
            c = conn.cursor()
            c.execute("SELECT id, run_number FROM runs ORDER BY id DESC")
            self.runs = c.fetchall()
            for run in self.runs:
                self.run_listbox.insert("end", run[1])

    def load_run_data(self, event=None):
        selected = self.run_listbox.curselection()
        if not selected:
            return

        index = selected[0]
        self.selected_run_id = self.runs[index][0]

        with connect() as conn:
            c = conn.cursor()
            c.execute("SELECT incident_notes FROM incidents WHERE run_id = ?", (self.selected_run_id,))
            result = c.fetchone()
            if result:
                self.incident_text.delete("1.0", "end")
                self.incident_text.insert("end", result[0])
                self.save_button.configure(state="disabled")
                return
            else:
                self.save_button.configure(state="normal")

            c.execute("SELECT * FROM runs WHERE id = ?", (self.selected_run_id,))
            run = c.fetchone()
            c.execute("SELECT unit, status, timestamp FROM statuses WHERE run_id = ?", (self.selected_run_id,))
            statuses = c.fetchall()

        self.incident_text.delete("1.0", "end")
        self.incident_text.insert("end", f"Run Number: {run[1]}\n")
        self.incident_text.insert("end", f"Caller: {run[2]}\n")
        self.incident_text.insert("end", f"Location: {run[3]}\n")
        self.incident_text.insert("end", f"Nature: {run[4]}\n")
        self.incident_text.insert("end", f"Assigned Units: {run[5]}\n")
        self.incident_text.insert("end", f"Timestamp: {run[7]}\n\n")

        self.incident_text.insert("end", "Run Notes:\n" + run[6] + "\n\n")
        if statuses:
            self.incident_text.insert("end", "Responder Statuses:\n")
            for unit, status, ts in statuses:
                self.incident_text.insert("end", f"{unit}: {status} at {ts}\n")

    def save_report(self):
        notes = self.incident_text.get("1.0", "end").strip()
        if not self.selected_run_id or not notes:
            messagebox.showwarning("Incomplete", "No run selected or notes are empty.")
            return

        with connect() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO incidents (run_id, incident_notes) VALUES (?, ?)", (self.selected_run_id, notes))
            conn.commit()

        messagebox.showinfo("Saved", "Incident report saved.")
        self.save_button.configure(state="disabled")
