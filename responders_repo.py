# responders_repo.py
import os

RESPONDERS_FILE = "responders.txt"

def _norm_shift_key(s: str) -> str:
    s = (s or "").strip().upper()
    if s.startswith("SHIFT_"):
        s = s[6:]
    return s if s in ("A", "B", "C", "D") else ""

def _parse_line_fields(line: str):
    """
    Parse a responder line into 5 fields:
      code, name, status, phone, email
    Extra fields are ignored; missing fields are padded with "".
    """
    parts = [p.strip() for p in (line or "").split(",")]
    while len(parts) < 5:
        parts.append("")
    return parts[:5]

def load_responders_detailed_by_shift():
    shifts = {"A": [], "B": [], "C": [], "D": []}
    cur = None
    try:
        with open(RESPONDERS_FILE, "r", encoding="utf-8-sig") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                if (line.startswith("[") and line.endswith("]")) or line.endswith(":"):
                    header = line.strip("[]: \t")
                    nk = _norm_shift_key(header)
                    cur = nk if nk else None
                    continue
                if cur:
                    parts = [p.strip() for p in line.split(",")]
                    while len(parts) < 5:
                        parts.append("")
                    code, name, status, phone, email = parts[:5]
                    if code and name:
                        shifts[cur].append((code, name, status, phone, email))
    except FileNotFoundError:
        return shifts
    except Exception:
        return shifts
    return shifts


def save_responders_detailed_by_shift(data):
    """
    Writes responders with 5 fields per line under [A]/[B]/[C]/[D] sections.
    data: {"A":[(code, name, status, phone, email), ...], ...}
    """
    with open(RESPONDERS_FILE, "w", encoding="utf-8") as f:
        for key in ("A", "B", "C", "D"):
            f.write(f"[{key}]\n")
            for row in data.get(key, []):
                code = (row[0] if len(row) > 0 else "").strip()
                name = (row[1] if len(row) > 1 else "").strip()
                status = (row[2] if len(row) > 2 else "").strip()
                phone = (row[3] if len(row) > 3 else "").strip()
                email = (row[4] if len(row) > 4 else "").strip()
                if code and name:
                    f.write(f"{code},{name},{status},{phone},{email}\n")
            f.write("\n")


# ---------- Simple API (for call_form.py) ----------

def load_responders_by_shift():
    """
    Returns only (code, name) pairs for each shift,
    hiding status/phone/email from callers like call_form.py.
    """
    det = load_responders_detailed_by_shift()
    return {k: [(c, n) for (c, n, s, p, e) in v] for k, v in det.items()}

def save_responders_by_shift(simple):
    """
    Simple saver that only persists code+name and blanks the others.
    Avoid using this from Admin Controls if you want to keep details.
    """
    det = {"A": [], "B": [], "C": [], "D": []}
    for key in ("A", "B", "C", "D"):
        for c, n in simple.get(key, []):
            det[key].append((c, n, "", "", ""))
    save_responders_detailed_by_shift(det)

def list_all_responders_flat():
    """
    Returns a flat list like ["B1 Bill Mullins", "11 Clifford Hicks", ...]
    using only (code, name).
    """
    data = load_responders_by_shift()
    out = []
    for items in data.values():
        for code, name in items:
            out.append(f"{code} {name}")
    return out
