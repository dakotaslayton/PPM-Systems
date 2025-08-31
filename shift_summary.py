import os
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

SUMMARY_DIR = "shift_summaries"  # Make sure this folder exists

class ShiftSummaryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__()
        self.title("Shift Summary Logs")
        self.geometry("1000x600")
        self.parent = parent

        if not os.path.exists(SUMMARY_DIR):
            os.makedirs(SUMMARY_DIR)

        self.filtered_files = []

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_files)

        search_bar = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Search shift or date (e.g., A, 2025-08-03)")
        search_bar.pack(fill="x", padx=10, pady=(10, 0))

        self.file_listbox = tk.Listbox(self, width=30)
        self.file_listbox.pack(side="left", fill="y", padx=10, pady=10)
        self.file_listbox.bind("<<ListboxSelect>>", self.display_summary)

        self.text_area = tk.Text(self, wrap="word", bg="black", fg="white", font=("Arial", 12))
        self.text_area.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.load_files()

    def load_files(self):
        self.all_files = sorted([
            f for f in os.listdir(SUMMARY_DIR)
            if f.endswith(".txt")
        ])
        self.filter_files()

    def filter_files(self, *args):
        query = self.search_var.get().lower()
        self.file_listbox.delete(0, "end")
        self.filtered_files = []

        for fname in self.all_files:
            if query in fname.lower():
                self.file_listbox.insert("end", fname)
                self.filtered_files.append(fname)

    def display_summary(self, event=None):
        selection = self.file_listbox.curselection()
        if not selection:
            return

        selected_file = self.filtered_files[selection[0]]
        path = os.path.join(SUMMARY_DIR, selected_file)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.text_area.delete("1.0", "end")
            self.text_area.insert("end", content)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
