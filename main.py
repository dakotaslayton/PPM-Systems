import tkinter as tk
import customtkinter as ctk
from auth import validate_login, is_temp_password, mark_password_reset
from create_admin import initialize_admin
from dashboard import Dashboard
import os
from tkinter import messagebox

import customtkinter as ctk
from tkinter import messagebox
from database import load_users, reset_password

class ResetPasswordWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Reset Password")
        self.geometry("400x300")
        self.configure(fg_color="black")

        ctk.CTkLabel(self, text="Username", text_color="white").pack(pady=(20, 5))
        self.username_entry = ctk.CTkEntry(self)
        self.username_entry.pack()

        ctk.CTkLabel(self, text="New Password", text_color="white").pack(pady=(10, 5))
        self.new_pass1 = ctk.CTkEntry(self, show="*")
        self.new_pass1.pack()

        ctk.CTkLabel(self, text="Confirm Password", text_color="white").pack(pady=(10, 5))
        self.new_pass2 = ctk.CTkEntry(self, show="*")
        self.new_pass2.pack()

        ctk.CTkButton(self, text="Submit", command=self.reset_password).pack(pady=20)

    def reset_password(self):
        username = self.username_entry.get().strip()
        new1 = self.new_pass1.get().strip()
        new2 = self.new_pass2.get().strip()

        if not username or not new1 or not new2:
            messagebox.showwarning("Missing Info", "Please fill in all fields.")
            return

        if new1 != new2:
            messagebox.showerror("Mismatch", "Passwords do not match.")
            return

        try:
            users = load_users()
            bosk_id = None
            for key, user in users.items():
                if user["username"].lower() == username.lower():
                    bosk_id = key
                    break

            if not bosk_id:
                messagebox.showerror("Invalid User", f"Username '{username}' not found.")
                return

            reset_password(bosk_id, new1)
            messagebox.showinfo("Success", "Password reset successfully.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reset password:\n{e}")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

class LoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PPM Systems Login")

        # Set size and center window
        width = 450
        height = 400
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = int((screen_width / 2) - (width / 2))
        y = int((screen_height / 2) - (height / 2))
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)

        # Set background to full black
        ctk.set_appearance_mode("dark")

# Branding
        self.title_label_main = ctk.CTkLabel(
            root,
            text="Welcome to PPM Systems",
            font=ctk.CTkFont(size=25, weight="bold"),
            text_color="white"
        )
        self.title_label_main.pack(pady=(15, 0))

        self.title_label_sub = ctk.CTkLabel(
            root,
            text="A Product of Slayton Technologies",
            font=ctk.CTkFont(size=15),
            text_color="white"
        )
        self.title_label_sub.pack(pady=(5, 10))


        # Login entries
        self.username = ctk.CTkEntry(root, placeholder_text="Username", width=250)
        self.username.pack(pady=20)

        self.password = ctk.CTkEntry(root, placeholder_text="Password", show="*", width=250)
        self.password.pack(pady=10)
        self.password.bind("<Return>", lambda event: self.login())

        # Status label
        self.status_label = ctk.CTkLabel(root, text="", text_color="red")
        self.status_label.pack(pady=5)

        # Login button
        self.login_button = ctk.CTkButton(root, text="Login", command=self.login)
        self.login_button.pack(pady=20)
        self.reset_button = ctk.CTkButton(root, text="Reset Password", command=self.open_reset_password)
        self.reset_button.pack(pady=(0, 10))
    
    def open_reset_password(self):
        ResetPasswordWindow(self.root)
        print("🚨 Reset button clicked")


    def login(self):
        username = self.username.get().strip()
        password = self.password.get().strip()

        if not username or not password:
            self.status_label.configure(text="Please enter both username and password.")
            return

        # Handle valid login
        if validate_login(username, password):
            if is_temp_password(username):
                self.status_label.configure(text="Temp password. Please reset.", text_color="orange")
                return  # Stop here until password reset is handled

            self.root.withdraw()
            dashboard = Dashboard(username)
            dashboard.mainloop()
            return

        # Default: Invalid login
        self.status_label.configure(text="Invalid username or password.")

# TEMP TEST
import database
print("🧪 Manual test for BOSK ID 333")
print("user_exists:", database.user_exists("333"))

if __name__ == "__main__":
    try:
        root = ctk.CTk()
        app = LoginApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        with open("error.log", "w") as f:
            f.write(traceback.format_exc())
        print("An error occurred. Check error.log for details.")
