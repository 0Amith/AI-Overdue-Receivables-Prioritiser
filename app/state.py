"""Durable state: promise-to-pay log, contact log, audit trail, uploaded register.

Kept in plain JSON/JSONL under state/ so every record is inspectable and the
audit file can be handed to the Finance Manager as evidence.
"""
from __future__ import annotations

import json
import threading
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
PROMISES = STATE_DIR / "promises.json"
CONTACTS = STATE_DIR / "contacts.json"
AUDIT = STATE_DIR / "audit.jsonl"
UPLOADED_REGISTER = STATE_DIR / "uploaded_register.csv"

OUTCOMES = ["no answer", "spoke to customer", "disputed", "part paid", "paid in full"]


class Store:
    def __init__(self, directory: Path | None = None) -> None:
        self._lock = threading.RLock()
        self.dir = Path(directory) if directory else STATE_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.promises_path = self.dir / "promises.json"
        self.contacts_path = self.dir / "contacts.json"
        self.audit_path = self.dir / "audit.jsonl"
        for path in (self.promises_path, self.contacts_path):
            if not path.exists():
                path.write_text("{}\n", encoding="utf-8")
        if not self.audit_path.exists():
            self.audit_path.write_text("", encoding="utf-8")

    # -- promises ------------------------------------------------------
    def promises(self) -> dict[str, dict]:
        with self._lock:
            try:
                return json.loads(self.promises_path.read_text(encoding="utf-8") or "{}")
            except (json.JSONDecodeError, OSError):
                return {}

    def set_promise(self, customer_id: str, promised_on: str, note: str = "") -> dict:
        try:
            when = date.fromisoformat(promised_on)
        except ValueError as exc:
            raise ValueError("promised date must be YYYY-MM-DD") from exc
        entry = {
            "promised_on": when.isoformat(),
            "note": note.strip()[:200],
            "logged_at": datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock:
            data = self.promises()
            data[customer_id] = entry
            self.promises_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return entry

    def clear_promise(self, customer_id: str) -> bool:
        with self._lock:
            data = self.promises()
            if customer_id not in data:
                return False
            data.pop(customer_id)
            self.promises_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return True

    # -- contacts ------------------------------------------------------
    def contacts(self) -> dict[str, dict]:
        with self._lock:
            try:
                return json.loads(self.contacts_path.read_text(encoding="utf-8") or "{}")
            except (json.JSONDecodeError, OSError):
                return {}

    def log_contact(self, customer_id: str, outcome: str, note: str = "") -> dict:
        outcome = (outcome or "").strip().lower()
        if outcome not in OUTCOMES:
            raise ValueError("unknown outcome")
        with self._lock:
            data = self.contacts()
            history = data.get(customer_id, {}).get("history", [])
            history.append({"outcome": outcome, "note": note.strip()[:200], "at": date.today().isoformat()})
            entry = {
                "outcome": outcome,
                "note": note.strip()[:200],
                "last_contact": date.today().isoformat(),
                "history": history[-12:],
            }
            data[customer_id] = entry
            self.contacts_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return entry

    def clear_contact(self, customer_id: str) -> bool:
        with self._lock:
            data = self.contacts()
            if customer_id not in data:
                return False
            data.pop(customer_id)
            self.contacts_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return True

    def disputed(self) -> set[str]:
        return {cid for cid, row in self.contacts().items() if row.get("outcome") == "disputed"}

    def contacted_since(self, cutoff: date) -> set[str]:
        out = set()
        for cid, row in self.contacts().items():
            try:
                if date.fromisoformat(str(row.get("last_contact", ""))) >= cutoff:
                    out.add(cid)
            except ValueError:
                continue
        return out

    # -- audit ---------------------------------------------------------
    def log(self, **fields) -> None:
        record = {"at": datetime.now().isoformat(timespec="seconds"), **fields}
        with self._lock:
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def audit(self, limit: int = 500) -> list[dict]:
        with self._lock:
            if not self.audit_path.exists():
                return []
            lines = self.audit_path.read_text(encoding="utf-8").splitlines()[-limit:]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def audit_csv(self) -> str:
        rows = ["timestamp,mode,question,intent,understood_by,answer_summary"]
        for r in self.audit(2000):
            q = str(r.get("question", "")).replace('"', "'")
            a = str(r.get("answer_summary", "")).replace('"', "'")
            rows.append(
                f'{r.get("at","")},{r.get("mode","")},"{q}","{r.get("intent","")}",'
                f'"{r.get("source","rules")}","{a}"'
            )
        return "\n".join(rows) + "\n"


STORE = Store()
