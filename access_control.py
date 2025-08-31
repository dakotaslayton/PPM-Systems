# access_control.py
from __future__ import annotations
import json
import os
from typing import Iterable, Dict, Any, List, Set

USERS_FILE = "users.txt"  # username,password,first,last,bosk_id,is_temp,is_admin
RESPONDER_USERS_FILE = "responder_users.json"  # {"41": ["dakota"], "42": ["alex","jordan"]}

# Configure your owner/admin logic here (kept consistent with prior messages)
OWNER_BOSK_IDS = {"OWNER-001"}  # update if needed

def _load_users() -> Dict[str, Dict[str, str]]:
    """
    Returns {username: {"username":..., "password":..., "first":..., "last":..., "bosk_id":..., "is_temp":..., "is_admin":...}}
    """
    users = {}
    if not os.path.exists(USERS_FILE):
        return users
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 7:
                # username,password,first,last,bosk_id,is_temp,is_admin
                continue
            username, password, first, last, bosk_id, is_temp, is_admin = parts[:7]
            users[username] = {
                "username": username,
                "password": password,
                "first": first,
                "last": last,
                "bosk_id": (bosk_id or "").upper(),
                "is_temp": is_temp,
                "is_admin": is_admin,
            }
    return users

def is_owner(username: str) -> bool:
    rec = _load_users().get(username)
    return bool(rec and rec.get("bosk_id", "").upper() in OWNER_BOSK_IDS)

def is_admin(username: str) -> bool:
    rec = _load_users().get(username)
    return bool(rec and str(rec.get("is_admin", "")).strip().lower() in {"1", "true", "yes"})

def load_responder_users_map() -> Dict[str, List[str]]:
    """
    Maps responder_id (e.g., "41") -> [usernames...]
    You maintain this json file to link responders to login usernames for the shift.
    """
    if not os.path.exists(RESPONDER_USERS_FILE):
        return {}
    with open(RESPONDER_USERS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            return {}
    # normalize keys to strings, values to list[str]
    norm: Dict[str, List[str]] = {}
    for k, v in data.items():
        key = str(k).strip()
        usernames = []
        if isinstance(v, str):
            usernames = [v.strip()]
        elif isinstance(v, list):
            usernames = [str(x).strip() for x in v if x]
        norm[key] = usernames
    return norm

def get_user_responder_ids(username: str) -> Set[str]:
    """
    Reverse-lookup: which responder IDs are linked to this username?
    """
    mapping = load_responder_users_map()
    linked: Set[str] = set()
    for resp_id, users in mapping.items():
        if username in users:
            linked.add(str(resp_id))
    return linked

def can_user_view_run(username: str, run_record: Dict[str, Any]) -> bool:
    """
    Owner/Admin -> always True.
    Otherwise: user can view if any of their responder IDs is in the run's assigned units.
    Expected run_record carries a list[str] at 'assigned_units' (e.g., ["41","E1","42"]).
    Only numeric-like IDs are considered "responders" here; apparatus like E1 don't grant access.
    """
    if is_owner(username) or is_admin(username):
        return True

    assigned: Iterable[str] = run_record.get("assigned_units") or run_record.get("assigned_responders") or []
    assigned_str: Set[str] = {str(x).strip() for x in assigned if str(x).strip()}

    # Heuristic: responders are numeric IDs (41, 42, etc.). Keep them as strings for matching.
    assigned_responder_ids = {x for x in assigned_str if x.isdigit()}

    user_ids = get_user_responder_ids(username)
    return len(assigned_responder_ids & user_ids) > 0

def filter_runs_for_user(username: str, runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in runs if can_user_view_run(username, r)]
