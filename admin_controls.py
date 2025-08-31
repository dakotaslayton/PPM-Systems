import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
from functools import partial

import responders_repo  # <- keep exactly this single module import
from auth import (
    OWNER_USERNAME,
    is_owner,
    is_admin,
    promote_to_admin,
    demote_from_admin,
    create_user,
    set_password,
)

SHIFT_KEYS = ["A", "B", "C", "D"]

USERS_FILE = "users.txt"
ADMINS_FILE = "admin_users.txt"


class AdminControlWindow(ctk.CTkToplevel):
    def __init__(self, username, return_to_dashboard):
        super().__init__()
        self.username = username
        self.return_to_dashboard = return_to_dashboard
        self.title("Admin Controls")

        # allow reset_password to use a bound var or prompt (User Management tab)
        self.new_pw_var = ctk.StringVar(value="")

        # Center window
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ww, wh = 700, 600
        x, y = (sw // 2) - (ww // 2), (sh // 2) - (wh // 2)
        self.geometry(f"{ww}x{wh}+{x}+{y}")

        # ------------------------- TabView: 1) Users 2) Responders -------------------------
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.user_tab = self.tabview.add("User Management")
        self.responder_tab = self.tabview.add("Responder Management")

        # ============================== USER MANAGEMENT ==============================
        self._build_user_management_tab(self.user_tab)

        # ============================= RESPONDER MANAGEMENT ==========================
        self._build_responder_management_tab(self.responder_tab)

        # initial state
        self.rm_active_shift = "A"
        self.refresh_lists()
        self._rm_refresh_for_shift(self.rm_active_shift)

    # =========================================================================================
    #                                   COMMON HELPERS
    # =========================================================================================
    def _can_manage_users(self) -> bool:
        return is_owner(self.username) or is_admin(self.username)

    def _init_textbox_center(self, tb):
        try:
            text = tb._textbox if hasattr(tb, "_textbox") else tb
            text.tag_configure("center", justify="center")
        except Exception as e:
            print("center init failed:", e)

    def _apply_textbox_center(self, tb):
        try:
            text = tb._textbox if hasattr(tb, "_textbox") else tb
            text.tag_add("center", "1.0", "end")
        except Exception as e:
            print("center apply failed:", e)

    def _set_readonly(self, tb, readonly: bool = True):
        try:
            text = tb._textbox if hasattr(tb, "_textbox") else tb
            if readonly:
                text.configure(state="disabled", insertofftime=0, cursor="arrow", takefocus=0)
            else:
                text.configure(state="normal", cursor="xterm")
        except Exception as e:
            print("set_readonly failed:", e)

    def back_to_dashboard(self):
        try:
            if self.return_to_dashboard:
                self.return_to_dashboard()
        finally:
            self.destroy()

    # =========================================================================================
    #                                   USER MANAGEMENT
    # =========================================================================================
    def _build_user_management_tab(self, root):
        # Title
        ctk.CTkLabel(root, text="Admin Panel", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)

        # --- Create user (no temp password) ---
        input_frame = ctk.CTkFrame(root)
        input_frame.pack(pady=5)

        self.username_entry = ctk.CTkEntry(input_frame, placeholder_text="Username")
        self.username_entry.grid(row=0, column=0, padx=5, pady=5)
        self.password_entry = ctk.CTkEntry(input_frame, placeholder_text="Password", show="*")
        self.password_entry.grid(row=0, column=1, padx=5, pady=5)
        self.first_entry = ctk.CTkEntry(input_frame, placeholder_text="First Name")
        self.first_entry.grid(row=1, column=0, padx=5, pady=5)
        self.last_entry = ctk.CTkEntry(input_frame, placeholder_text="Last Name")
        self.last_entry.grid(row=1, column=1, padx=5, pady=5)
        self.bosk_entry = ctk.CTkEntry(input_frame, placeholder_text="BOSK ID")
        self.bosk_entry.grid(row=2, column=0, padx=5, pady=5)

        ctk.CTkButton(root, text="Add User", command=self.add_user).pack(pady=5)

        # --- Lists row: centered 3 columns ---
        lists_frame = ctk.CTkFrame(root)
        lists_frame.pack(pady=10, fill="both", expand=True)
        for col in (0, 1, 2):
            lists_frame.grid_columnconfigure(col, weight=1, uniform="cols")
        lists_frame.grid_rowconfigure(1, weight=1)

        # Admins column
        self.admin_label = ctk.CTkLabel(lists_frame, text="Current Admins:")
        self.admin_label.grid(row=0, column=0, sticky="n")
        self.admin_box = ctk.CTkTextbox(lists_frame, width=280, height=200)
        self.admin_box.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # Users column
        self.user_label = ctk.CTkLabel(lists_frame, text="Current Users:")
        self.user_label.grid(row=0, column=1, sticky="n")
        self.user_box = ctk.CTkTextbox(lists_frame, width=280, height=200)
        self.user_box.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")
        self.user_box.bind("<Button-1>", self.load_user_info)
        self.user_box.bind("<Button-3>", self.show_context_menu)

        # Details column
        self.details_box = ctk.CTkTextbox(lists_frame, width=300, height=200)
        self.details_box.grid(row=1, column=2, padx=10, pady=5, sticky="nsew")

        # init centering for textboxes
        self._init_textbox_center(self.admin_box)
        self._init_textbox_center(self.user_box)
        self._init_textbox_center(self.details_box)

        # make boxes read-only (no caret / typing)
        self._set_readonly(self.admin_box, True)
        self._set_readonly(self.user_box, True)
        self._set_readonly(self.details_box, True)

        # Bottom actions
        btn_frame = ctk.CTkFrame(root)
        btn_frame.pack(pady=10)

        self.promote_btn = ctk.CTkButton(btn_frame, text="Promote to Admin", command=self.promote_user)
        self.promote_btn.grid(row=0, column=0, padx=5)

        if is_owner(self.username):
            self.demote_btn = ctk.CTkButton(btn_frame, text="Demote Admin", command=self.demote_user)
            self.demote_btn.grid(row=0, column=1, padx=5)

        back_btn = ctk.CTkButton(btn_frame, text="Return to Dashboard", command=self.back_to_dashboard)
        back_btn.grid(row=0, column=3, padx=5)

        # Context menu for edit/delete (owner + admins)
        self.selected_user = None
        self.context_menu = tk.Menu(root, tearoff=0)
        if self._can_manage_users():
            pass

    # ------------------------------- Data/UI (Users) --------------------------------
    def refresh_lists(self):
        # Admins (hide owner)
        self._set_readonly(self.admin_box, False)
        self.admin_box.delete("1.0", "end")
        try:
            with open(ADMINS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    name = line.strip()
                    if not name or name == OWNER_USERNAME:
                        continue
                    self.admin_box.insert("end", name + "\n")
        except FileNotFoundError:
            self.admin_box.insert("end", "(No admins found)\n")
        self._apply_textbox_center(self.admin_box)
        self._set_readonly(self.admin_box, True)

        # Users (hide owner)
        self._set_readonly(self.user_box, False)
        self.user_box.delete("1.0", "end")
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if parts and parts[0] and parts[0] != OWNER_USERNAME:
                        self.user_box.insert("end", parts[0] + "\n")
        except FileNotFoundError:
            self.user_box.insert("end", "(No users found)\n")
        self._apply_textbox_center(self.user_box)
        self._set_readonly(self.user_box, True)

    def load_user_info(self, event):
        self._set_readonly(self.details_box, False)
        self.details_box.delete("1.0", "end")
        try:
            line_index = self.user_box.index("@%d,%d" % (event.x, event.y))
            clicked_line = int(str(line_index).split(".")[0])
            selected = self.user_box.get(f"{clicked_line}.0", f"{clicked_line}.end").strip()
            self.selected_user = selected
            if not selected:
                self._set_readonly(self.details_box, True)
                return

            with open(USERS_FILE, "r", encoding="utf-8") as f:
                for raw in f:
                    user = raw.strip().split(",")
                    if len(user) < 5:
                        continue
                    if user[0] == selected:
                        uname, first, last, bosk = user[0], user[2], user[3], user[4]
                        admin_flag = is_admin(uname)
                        self.details_box.insert(
                            "end",
                            f"Username: {uname}\nFirst: {first}\nLast: {last}\nBOSK ID: {bosk}\nAdmin: {admin_flag}\n"
                        )
                        break
        except Exception as e:
            self.details_box.insert("end", f"Error loading user info: {e}")
        self._apply_textbox_center(self.details_box)
        self._set_readonly(self.details_box, True)

    # ------------------------------- Actions (Users) --------------------------------
    def add_user(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        first = self.first_entry.get().strip()
        last = self.last_entry.get().strip()
        bosk_id = self.bosk_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Add User", "Username and password are required.")
            return

        if os.path.exists(USERS_FILE) and username in open(USERS_FILE, "r", encoding="utf-8").read():
            messagebox.showerror("Add User", f"User '{username}' already exists.")
            return

        ok = create_user(username, password, first, last, bosk_id, False, False)
        if ok:
            self.username_entry.delete(0, "end")
            self.password_entry.delete(0, "end")
            self.first_entry.delete(0, "end")
            self.last_entry.delete(0, "end")
            self.bosk_entry.delete(0, "end")
            self.refresh_lists()
            messagebox.showinfo("Add User", f"User '{username}' created.")
        else:
            messagebox.showerror("Add User", "Could not create user (duplicate username?).")

    def promote_user(self):
        if self.selected_user and is_owner(self.username):
            promote_to_admin(self.selected_user)
            self.refresh_lists()

    def demote_user(self):
        if self.selected_user and is_owner(self.username):
            demote_from_admin(self.selected_user)
            self.refresh_lists()

    def reset_password(self):
        if not self.selected_user:
            messagebox.showerror("Set Password", "No user selected.")
            return

        new_pw = self.new_pw_var.get().strip()
        if not new_pw:
            dlg = ctk.CTkInputDialog(
                text=f"Enter a new password for {self.selected_user}",
                title="Set Password"
            )
            new_pw = (dlg.get_input() or "").strip()
            if not new_pw:
                return

        if set_password(self.selected_user, new_pw):
            self.new_pw_var.set("")
            messagebox.showinfo("Set Password", f"Password updated for {self.selected_user}.")
        else:
            messagebox.showerror("Set Password", f"Failed to update password for {self.selected_user}.")

    # ------- Custom context popup for Users (Edit/Delete) -------
    def show_context_menu(self, event):
        if not self._can_manage_users():
            return
        index = self.user_box.index(f"@{event.x},{event.y}")
        line_number = int(index.split(".")[0])
        username = self.user_box.get(f"{line_number}.0", f"{line_number}.end").strip()
        if not username or username in (OWNER_USERNAME, self.username):
            return
        self.selected_user = username

        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(fg_color="#1f1f1f")
        popup.geometry(f"+{event.x_root}+{event.y_root}")

        frame = ctk.CTkFrame(popup, corner_radius=8)
        frame.pack(padx=6, pady=6)

        def close_popup(*_):
            try:
                popup.destroy()
            except Exception:
                pass

        ctk.CTkButton(
            frame,
            text="Edit User",
            width=220,
            height=40,
            command=lambda: (close_popup(), self.edit_user_popup()),
        ).pack(padx=6, pady=6)
        ctk.CTkButton(
            frame,
            text="Delete User",
            width=220,
            height=40,
            fg_color="#8B0000",
            hover_color="#A00000",
            command=lambda: (close_popup(), self.delete_user()),
        ).pack(padx=6, pady=6)

        popup.bind("<FocusOut>", lambda e: close_popup())
        popup.after(1, popup.focus_force)

    def edit_user_popup(self):
        if not self._can_manage_users():
            return
        if not self.selected_user or self.selected_user in (OWNER_USERNAME,):
            return

        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = [line.strip().split(",") for line in f]
        row = next((u for u in users if u and u[0] == self.selected_user), None)
        if not row:
            return

        popup = ctk.CTkToplevel(self)
        popup.title(f"Edit User: {self.selected_user}")
        popup.geometry("420x320")

        labels = ["Username", "Password", "First Name", "Last Name", "BOSK ID"]
        entries = {}
        for i, label in enumerate(labels):
            ctk.CTkLabel(popup, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            ent = ctk.CTkEntry(popup, show="*" if label == "Password" else None)
            ent.grid(row=i, column=1, padx=10, pady=5)
            ent.insert(0, row[i] if i < len(row) else "")
            entries[label] = ent

    # =========================================================================================
    #                                 RESPONDER MANAGEMENT
    # =========================================================================================
    def _build_responder_management_tab(self, root):
        # Layout: left sidebar (shift tabs), center list, right details/editor
        root.grid_columnconfigure(0, weight=0)  # sidebar fixed
        root.grid_columnconfigure(1, weight=1, uniform="rmcols")
        root.grid_columnconfigure(2, weight=1, uniform="rmcols")
        root.grid_rowconfigure(1, weight=1)

        # Header
        ctk.CTkLabel(root, text="Responder Management", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, pady=(6, 10)
        )

        # Left: shift tabs/buttons
        sidebar = ctk.CTkFrame(root, width=160)
        sidebar.grid(row=1, column=0, padx=(0, 10), pady=6, sticky="ns")
        ctk.CTkLabel(sidebar, text="Shifts").pack(pady=(8, 6))

        # Buttons for A/B/C/D
        self.rm_active_shift = "A"
        for key in SHIFT_KEYS:
            ctk.CTkButton(
                sidebar,
                text=f"Shift {key}",
                command=partial(self._rm_switch_shift, key)
            ).pack(fill="x", padx=10, pady=4)

        # Middle: responders list (panel 1)
        mid_frame = ctk.CTkFrame(root)
        mid_frame.grid(row=1, column=1, padx=10, pady=6, sticky="nsew")
        mid_frame.grid_rowconfigure(1, weight=1)
        mid_frame.grid_columnconfigure(0, weight=1)

        # Dynamic header shows current shift
        self.rm_list_label = ctk.CTkLabel(mid_frame, text=f"Responders (Shift {self.rm_active_shift})")
        self.rm_list_label.grid(row=0, column=0, pady=(8, 4))

        # Monospaced for perfect vertical alignment
        self._rm_mono_font = ctk.CTkFont(family="Consolas", size=14)
        self.rm_list_box = ctk.CTkTextbox(mid_frame, width=360, font=self._rm_mono_font)
        self.rm_list_box.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        self._set_readonly(self.rm_list_box, True)
        self.rm_list_box.bind("<Button-1>", self._rm_pick_responder)
        self.rm_list_box.bind("<Button-3>", self._rm_context_menu)

        # Right: details/editor (panel 2)
        right_frame = ctk.CTkFrame(root)
        right_frame.grid(row=1, column=2, padx=(10, 0), pady=6, sticky="nsew")
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_frame, text="Details").grid(row=0, column=0, pady=(8, 4))
        self.rm_details_box = ctk.CTkTextbox(right_frame)
        self.rm_details_box.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        self._init_textbox_center(self.rm_details_box)
        self._set_readonly(self.rm_details_box, True)

        # Bottom bar (add/edit/delete)
        action_bar = ctk.CTkFrame(root)
        action_bar.grid(row=2, column=0, columnspan=3, pady=(6, 8))
        ctk.CTkButton(action_bar, text="Add Responder", command=self._rm_add_responder).grid(row=0, column=0, padx=6)
        ctk.CTkButton(
            action_bar, text="Delete Selected", fg_color="#8B0000", hover_color="#A00000",
            command=self._rm_delete_responder
        ).grid(row=0, column=2, padx=6)

        self.rm_selected_key = None  # "unit_code - name" line key

    def _rm_norm_key(self, k: str) -> str:
        """Normalize shift keys to single letter 'A'/'B'/'C'/'D'."""
        if not k:
            return ""
        k = str(k).strip().upper()
        if k.startswith("SHIFT_"):
            k = k[6:]
        return k if k in ("A", "B", "C", "D") else ""

    def _rm_code_sort_key(self, code: str):
        """B# first (by #), then other numeric codes, then lexicographic."""
        import re
        c = (code or "").strip().upper()
        if c.startswith("B"):
            m = re.match(r"^B(\d+)", c)
            n = int(m.group(1)) if m else 10_000_000
            return (0, n, c)
        m = re.match(r"^(\d+)", c)
        n = int(m.group(1)) if m else 10_000_000
        return (1, n, c)

    def _rm_sort_shift_list_detailed(self, rows):
        """Sort rows of (code, name, status, phone, email) using _rm_code_sort_key."""
        cleaned = []
        for r in rows or []:
            code = (r[0] if len(r) > 0 else "").strip()
            name = (r[1] if len(r) > 1 else "").strip()
            status = (r[2] if len(r) > 2 else "").strip()
            phone = (r[3] if len(r) > 3 else "").strip()
            email = (r[4] if len(r) > 4 else "").strip()
            if code and name:
                cleaned.append((code, name, status, phone, email))
        return sorted(cleaned, key=lambda r: self._rm_code_sort_key(r[0]))

    def _rm_read_rows(self, shift_key: str):
        """
        Return rows like [code, name, status, phone, email] for the selected shift
        from responders_repo.load_responders_detailed_by_shift().
        """
        key = self._rm_norm_key(shift_key) or "A"
        det = responders_repo.load_responders_detailed_by_shift()
        rows = []
        for row in det.get(key, []):
            code = (row[0] if len(row) > 0 else "").strip()
            name = (row[1] if len(row) > 1 else "").strip()
            status = (row[2] if len(row) > 2 else "").strip()
            phone = (row[3] if len(row) > 3 else "").strip()
            email = (row[4] if len(row) > 4 else "").strip()
            if code and name:
                rows.append([code, name, status, phone, email])
        return rows

    def _rm_write_rows(self, shift_key: str, rows):
        """
        Save rows (code, name, status, phone, email) for a shift to file.
        Sorted with B* first, then numeric.
        """
        key = self._rm_norm_key(shift_key) or "A"
        det = responders_repo.load_responders_detailed_by_shift()
        det[key] = self._rm_sort_shift_list_detailed(rows)
        responders_repo.save_responders_detailed_by_shift(det)

    def _rm_format_lines(self, rows):
        """Monospaced, vertically aligned: CODE(col-aligned) + ' - ' + Name."""
        codes = [r[0] for r in rows if r and len(r) > 1 and (r[0] or "").strip()]
        maxw = max((len(c) for c in codes), default=2)
        lines = []
        for r in rows:
            if not r or len(r) < 2:
                continue
            code = (r[0] or "").strip()
            name = (r[1] or "").strip()
            if not code or not name:
                continue
            lines.append(f"{code.ljust(maxw)} - {name}")
        return lines

    def _rm_refresh_for_shift(self, shift_key: str):
        key = self._rm_norm_key(shift_key) or "A"
        try:
            rows = self._rm_read_rows(key)
        except Exception as e:
            print(f"[ResponderMgmt] ERROR reading rows for {key}: {e}")
            rows = []

        # update header text to show current shift
        try:
            self.rm_list_label.configure(text=f"Responders (Shift {key})")
        except Exception:
            pass

        # format aligned lines
        lines = self._rm_format_lines(rows)

        # write list box
        self._set_readonly(self.rm_list_box, False)
        try:
            self.rm_list_box.delete("1.0", "end")
            if not lines:
                self.rm_list_box.insert("end", "(No responders)\n")
            else:
                self.rm_list_box.insert("end", "\n".join(lines) + "\n")
        finally:
            self._set_readonly(self.rm_list_box, True)

        # clear right-side details
        self._set_readonly(self.rm_details_box, False)
        self.rm_details_box.delete("1.0", "end")
        self._set_readonly(self.rm_details_box, True)

        self.rm_selected_key = None

    def _rm_pick_responder(self, event):
        idx = self.rm_list_box.index("@%d,%d" % (event.x, event.y))
        line = int(idx.split(".")[0])
        text = self.rm_list_box.get(f"{line}.0", f"{line}.end").strip()
        if not text or text.startswith("("):
            return
        self.rm_selected_key = text  # "code - name"

        code = text.split(" - ", 1)[0].strip()
        rows = self._rm_read_rows(self.rm_active_shift)
        row = next((r for r in rows if r[0] == code), None)

        self._set_readonly(self.rm_details_box, False)
        self.rm_details_box.delete("1.0", "end")
        if row:
            code, name, status, phone, email = row
            self.rm_details_box.insert(
                "end",
                f"Shift: {self.rm_active_shift}\n"
                f"Unit Code: {code}\n"
                f"Name: {name}\n"
                f"Status: {status}\n"
                f"Phone: {phone}\n"
                f"Email: {email}\n"
            )
        else:
            self.rm_details_box.insert("end", "Responder not found.")
        self._apply_textbox_center(self.rm_details_box)
        self._set_readonly(self.rm_details_box, True)

    def _rm_context_menu(self, event):
        if not self._can_manage_users():
            return
        idx = self.rm_list_box.index(f"@{event.x},{event.y}")
        line = int(idx.split(".")[0])
        text = self.rm_list_box.get(f"{line}.0", f"{line}.end").strip()
        if not text or text.startswith("("):
            return
        self.rm_selected_key = text

        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(fg_color="#1f1f1f")
        popup.geometry(f"+{event.x_root}+{event.y_root}")

        frame = ctk.CTkFrame(popup, corner_radius=8)
        frame.pack(padx=6, pady=6)

        def close_popup(*_):
            try:
                popup.destroy()
            except Exception:
                pass

        ctk.CTkButton(
            frame, text="Edit Responder", width=220, height=40,
            command=lambda: (close_popup(), self._rm_edit_responder()),
        ).pack(padx=6, pady=6)
        ctk.CTkButton(
            frame, text="Delete Responder", width=220, height=40,
            fg_color="#8B0000", hover_color="#A00000",
            command=lambda: (close_popup(), self._rm_delete_responder()),
        ).pack(padx=6, pady=6)

        popup.bind("<FocusOut>", lambda e: close_popup())
        popup.after(1, popup.focus_force)

    def _rm_add_responder(self):
        if not self._can_manage_users():
            messagebox.showerror("Permission denied", "You do not have permission to manage responders.")
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Add Responder")
        popup.geometry("460x360")

        ctk.CTkLabel(popup, text="Shift").grid(row=0, column=0, padx=10, pady=(10, 6), sticky="e")
        shift_var = ctk.StringVar(value=self._rm_norm_key(self.rm_active_shift) or "A")
        ctk.CTkOptionMenu(popup, values=["A", "B", "C", "D"], variable=shift_var).grid(
            row=0, column=1, padx=10, pady=(10, 6), sticky="w"
        )

        fields = ["Unit Code", "Name", "Status", "Phone", "Email"]
        ents = {}
        for i, label in enumerate(fields, start=1):
            ctk.CTkLabel(popup, text=label).grid(row=i, column=0, padx=10, pady=6, sticky="e")
            ent = ctk.CTkEntry(popup)
            ent.grid(row=i, column=1, padx=10, pady=6, sticky="w")
            ents[label] = ent

        def save_new():
            tgt_shift = self._rm_norm_key(shift_var.get()) or "A"
            code = ents["Unit Code"].get().strip()
            name = ents["Name"].get().strip()
            status = ents["Status"].get().strip()
            phone = ents["Phone"].get().strip()
            email = ents["Email"].get().strip()

            if not code or not name:
                messagebox.showerror("Add Responder", "Unit Code and Name are required.")
                return

            det = responders_repo.load_responders_detailed_by_shift()
            if any(c == code for (c, _, _, _, _) in det.get(tgt_shift, [])):
                messagebox.showerror("Add Responder", f"Unit Code '{code}' already exists in Shift {tgt_shift}.")
                return

            det.setdefault(tgt_shift, []).append((code, name, status, phone, email))
            det[tgt_shift] = self._rm_sort_shift_list_detailed(det[tgt_shift])
            responders_repo.save_responders_detailed_by_shift(det)

            popup.destroy()
            self.rm_active_shift = tgt_shift
            self._rm_refresh_for_shift(self.rm_active_shift)

        ctk.CTkButton(popup, text="Save", command=save_new).grid(row=len(fields) + 1, column=0, columnspan=2, pady=12)

    def _rm_edit_responder(self):
        if not self._can_manage_users():
            messagebox.showerror("Permission denied", "You do not have permission to manage responders.")
            return
        if not self.rm_selected_key:
            messagebox.showerror("Edit Responder", "No responder selected.")
            return

        orig_code = self.rm_selected_key.split(" - ", 1)[0].strip()
        cur_shift = self._rm_norm_key(self.rm_active_shift) or "A"
        rows = self._rm_read_rows(cur_shift)
        row = next((r for r in rows if r[0] == orig_code), None)
        if not row:
            messagebox.showerror("Edit Responder", "Responder not found.")
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Edit Responder")
        popup.geometry("480x380")

        ctk.CTkLabel(popup, text="Shift").grid(row=0, column=0, padx=10, pady=(10, 6), sticky="e")
        shift_var = ctk.StringVar(value=cur_shift)
        ctk.CTkOptionMenu(popup, values=["A", "B", "C", "D"], variable=shift_var).grid(
            row=0, column=1, padx=10, pady=(10, 6), sticky="w"
        )

        fields = ["Unit Code", "Name", "Status", "Phone", "Email"]
        ents = {}
        values = dict(zip(fields, row + [""] * max(0, len(fields) - len(row))))
        for i, label in enumerate(fields, start=1):
            ctk.CTkLabel(popup, text=label).grid(row=i, column=0, padx=10, pady=6, sticky="e")
            ent = ctk.CTkEntry(popup)
            ent.grid(row=i, column=1, padx=10, pady=6, sticky="w")
            ent.insert(0, values.get(label, ""))
            ents[label] = ent

        def save_edits():
            new_shift = self._rm_norm_key(shift_var.get()) or "A"
            new_code = ents["Unit Code"].get().strip()
            name = ents["Name"].get().strip()
            status = ents["Status"].get().strip()
            phone = ents["Phone"].get().strip()
            email = ents["Email"].get().strip()

            if not new_code or not name:
                messagebox.showerror("Edit Responder", "Unit Code and Name are required.")
                return

            det = responders_repo.load_responders_detailed_by_shift()

            if new_shift != cur_shift:
                if any(c == new_code for (c, _, _, _, _) in det.get(new_shift, [])):
                    messagebox.showerror("Edit Responder", f"Unit Code '{new_code}' already exists in Shift {new_shift}.")
                    return
                det[cur_shift] = [(c, n, s, p, e) for (c, n, s, p, e) in det.get(cur_shift, []) if c != orig_code]
                det.setdefault(new_shift, []).append((new_code, name, status, phone, email))
                det[new_shift] = self._rm_sort_shift_list_detailed(det[new_shift])
            else:
                lst = []
                for (c, n, s, p, e) in det.get(cur_shift, []):
                    if c == orig_code:
                        lst.append((new_code, name, status, phone, email))
                    else:
                        lst.append((c, n, s, p, e))
                if new_code != orig_code and any(c == new_code for (c, _, _, _, _) in lst if c != orig_code):
                    messagebox.showerror("Edit Responder", f"Unit Code '{new_code}' already exists in Shift {cur_shift}.")
                    return
                det[cur_shift] = self._rm_sort_shift_list_detailed(lst)

            responders_repo.save_responders_detailed_by_shift(det)
            popup.destroy()
            self.rm_active_shift = new_shift
            self._rm_refresh_for_shift(self.rm_active_shift)

        ctk.CTkButton(popup, text="Save Changes", command=save_edits).grid(row=len(fields) + 1, column=0, columnspan=2, pady=12)

    def _rm_delete_responder(self):
        if not self._can_manage_users():
            messagebox.showerror("Permission denied", "You do not have permission to manage responders.")
            return
        if not self.rm_selected_key:
            messagebox.showerror("Delete Responder", "No responder selected.")
            return

        code = self.rm_selected_key.split(" - ", 1)[0].strip()
        if not messagebox.askyesno(
            "Delete Responder",
            f"Delete '{self.rm_selected_key}' from Shift {self.rm_active_shift}?"
        ):
            return

        # Remove from file and refresh
        cur_shift = self._rm_norm_key(self.rm_active_shift) or "A"
        det = responders_repo.load_responders_detailed_by_shift()
        det[cur_shift] = [(c, n, s, p, e) for (c, n, s, p, e) in det.get(cur_shift, []) if c != code]
        responders_repo.save_responders_detailed_by_shift(det)

        self.rm_selected_key = None
        self._rm_refresh_for_shift(self.rm_active_shift)

    def _rm_switch_shift(self, shift_key: str):
        self.rm_active_shift = self._rm_norm_key(shift_key) or "A"
        self._rm_refresh_for_shift(self.rm_active_shift)

    def delete_user(self):
        if not self._can_manage_users():
            messagebox.showerror("Permission denied", "You do not have permission to manage users.")
            return
        if not self.selected_user or self.selected_user in (OWNER_USERNAME,):
            return
        if self.selected_user == self.username:
            messagebox.showerror("Delete User", "You cannot delete your own account while logged in.")
            return

        if not messagebox.askyesno(
            "Delete User",
            f"Are you sure you want to delete '{self.selected_user}'?\nThis cannot be undone.",
        ):
            return

        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                for line in lines:
                    if not line.startswith(self.selected_user + ","):
                        f.write(line)

        if os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(ADMINS_FILE, "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() != self.selected_user:
                        f.write(line)

        self.selected
