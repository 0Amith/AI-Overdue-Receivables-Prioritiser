"""Local web server for the ABC Traders receivables assistant.

Standard library only: `python run.py` and open the printed URL.
"""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import bot as bot_module
import engine
import exports
import llm as llm_module
from datetime import date as _date

from state import STORE, UPLOADED_REGISTER
import state as state_module

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DATASET_META = UPLOADED_REGISTER.with_suffix(".json")
IMPORT_LIMIT = 5000

STATE_LOCK = threading.RLock()


def _load_dataset_meta() -> dict:
    try:
        meta = json.loads(DATASET_META.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(meta, dict):
        return {}
    return meta


def _initial_register():
    """Prefer an uploaded register, so a replacement survives a restart."""
    if UPLOADED_REGISTER.exists():
        meta = _load_dataset_meta()
        when = None
        if meta.get("report_date"):
            try:
                when = _date.fromisoformat(meta["report_date"])
            except ValueError:
                when = None
        try:
            return engine.load_register(UPLOADED_REGISTER, mapping=meta.get("mapping"), report_date=when)
        except engine.RegisterError:
            engine.set_report_date(None)
    return engine.load_register()


BOT = bot_module.Bot(_initial_register(), STORE, use_llm=True)

PAGES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
    "/policy-check": "policy.html",
    "/policy.js": "policy.js",
}

REQUIRED_COLUMNS = {"Customer ID", "Invoice No.", "Due Date", "Amount (Rs)", "History Code"}  # legacy


class Handler(BaseHTTPRequestHandler):
    server_version = "ABCTradersBot/1.1"

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        pass

    # -- helpers -------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str, download: str | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _text(self, body: str, download: str | None = None, ctype: str = "text/plain; charset=utf-8") -> None:
        self._send(200, body.encode("utf-8"), ctype, download)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    # -- routes --------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/health":
            return self._json(200, {"ok": True, "customers": len(BOT.invoices)})
        if path == "/api/register":
            return self._json(200, {"rows": register_payload()})
        if path == "/api/dataset":
            meta = _load_dataset_meta()
            return self._json(
                200,
                {
                    "source": UPLOADED_REGISTER.name if UPLOADED_REGISTER.exists() else "shipped register",
                    "report_date": engine.REPORT_DATE.isoformat(),
                    "default_date": engine.DEFAULT_REPORT_DATE.isoformat(),
                    "customers": len(BOT.invoices),
                    "mapping": meta.get("mapping") or {},
                },
            )
        if path == "/api/status":
            return self._json(
                200,
                {"ai": llm_module.configured(), "model": llm_module.active_model() or (llm_module.MODELS[0] if llm_module.configured() else None)},
            )
        if path == "/api/summary":
            with STATE_LOCK:
                ranked = BOT.ranked("v2")
            return self._json(200, exports.summary(ranked))
        if path == "/api/worklist.csv":
            with STATE_LOCK:
                ranked = BOT.ranked("v2")
                csv_text = exports.worklist_csv(ranked, BOT.promises(), STORE.contacts())
            return self._text(csv_text, "abc-traders-worklist.csv", "text/csv; charset=utf-8")
        if path == "/api/pack":
            priority = (query.get("priority") or ["Critical"])[0]
            lang = (query.get("lang") or ["en"])[0]
            if priority not in exports.PRIORITIES:
                return self._json(400, {"error": "unknown priority"})
            with STATE_LOCK:
                ranked = BOT.ranked("v2")
                md = exports.reminder_pack(BOT, ranked, priority, lang, BOT.promises())
            return self._text(md, f"abc-traders-{priority.lower()}-reminders.md", "text/markdown; charset=utf-8")
        if path == "/api/audit.csv":
            return self._text(STORE.audit_csv(), "abc-traders-audit-log.csv", "text/csv; charset=utf-8")
        if path == "/api/aging.csv":
            with STATE_LOCK:
                csv_text = exports.aging_csv(BOT.ranked("v2"))
            return self._text(csv_text, "abc-traders-ageing.csv", "text/csv; charset=utf-8")
        if path == "/api/board.md":
            with STATE_LOCK:
                md = exports.board_pack(BOT.ranked("v2"), BOT.promises(), STORE.contacts())
            return self._text(md, "abc-traders-board-brief.md", "text/markdown; charset=utf-8")
        if path == "/api/contacts":
            return self._json(200, {"contacts": STORE.contacts(), "outcomes": state_module.OUTCOMES})
        if path == "/api/promises":
            return self._json(200, {"promises": STORE.promises()})
        if path == "/api/policy-check":
            return self._json(200, exports.policy_check())

        name = PAGES.get(path)
        if name is None:
            return self._send(404, b"Not found", "text/plain; charset=utf-8")
        file = WEB / name
        if not file.exists():
            return self._send(404, b"Missing asset", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        self._send(200, file.read_bytes(), ctype)

    def do_POST(self) -> None:  # noqa: N802
        global BOT
        path = urlparse(self.path).path

        if path == "/api/chat":
            payload = self._body()
            message = str(payload.get("message", ""))[:2000]
            mode = "v1" if payload.get("mode") == "v1" else "v2"
            with STATE_LOCK:
                reply = BOT.answer(message, mode)
            summary = re.sub(r"<[^>]+>", " ", reply.html)
            STORE.log(
                mode=mode,
                question=message,
                intent=reply.intent,
                answer_summary=re.sub(r"\s+", " ", summary).strip()[:200],
                source=reply.source,
            )
            return self._json(200, reply.as_dict())

        if path == "/api/promise":
            payload = self._body()
            cid = str(payload.get("customer_id", "")).strip().upper()
            with STATE_LOCK:
                if cid not in BOT.invoices:
                    return self._json(404, {"error": "unknown customer"})
                try:
                    if payload.get("clear"):
                        STORE.clear_promise(cid)
                        entry = None
                    else:
                        entry = STORE.set_promise(cid, str(payload.get("date", "")), str(payload.get("note", "")))
                except ValueError as exc:
                    return self._json(400, {"error": str(exc)})
            STORE.log(mode="v2", question=f"promise {cid}", intent="promise", answer_summary=str(entry))
            return self._json(200, {"ok": True, "promise": entry})

        if path == "/api/contact":
            payload = self._body()
            cid = str(payload.get("customer_id", "")).strip().upper()
            with STATE_LOCK:
                if cid not in BOT.invoices:
                    return self._json(404, {"error": "unknown customer"})
                try:
                    if payload.get("clear"):
                        STORE.clear_contact(cid)
                        entry = None
                    else:
                        entry = STORE.log_contact(cid, str(payload.get("outcome", "")), str(payload.get("note", "")))
                except ValueError as exc:
                    return self._json(400, {"error": str(exc)})
            STORE.log(mode="v2", question=f"contact {cid}", intent="contact", answer_summary=str(entry))
            return self._json(200, {"ok": True, "contact": entry})

        if path == "/api/register":
            return self._handle_upload()
        if path == "/api/dataset/preview":
            return self._handle_preview()
        if path == "/api/dataset/apply":
            return self._handle_dataset(apply=True)
        if path == "/api/dataset/reset":
            return self._handle_reset()
        return self._json(404, {"error": "unknown endpoint"})

    # -- dataset import -------------------------------------------------
    def _import_payload(self) -> tuple[str, dict, _date | None] | None:
        """Shared parsing for preview and apply: CSV text, mapping, as-on date."""
        payload = self._body()
        text = str(payload.get("csv") or "")
        if not text.strip():
            raw = self.rfile.read(0)
            del raw
        mapping = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else None
        when = None
        if payload.get("report_date"):
            try:
                when = _date.fromisoformat(str(payload["report_date"]))
            except ValueError:
                return None
        return text, (mapping or {}), when

    def _handle_preview(self) -> None:
        got = self._import_payload()
        if got is None:
            return self._json(400, {"error": "as-on date must be YYYY-MM-DD"})
        text, mapping, when = got
        if not text.strip():
            return self._json(400, {"error": "empty file"})
        info = engine.inspect_dataset(text, mapping or None)
        if info["rows"] > IMPORT_LIMIT:
            return self._json(400, {"error": f"too many rows (max {IMPORT_LIMIT})"})
        info["report_date"] = when.isoformat() if when else engine.REPORT_DATE.isoformat()
        if when:
            info["preview_days"] = _preview_days(text, mapping or None, when)
        return self._json(200, info)

    def _handle_dataset(self, apply: bool) -> None:
        global BOT
        got = self._import_payload()
        if got is None:
            return self._json(400, {"error": "as-on date must be YYYY-MM-DD"})
        text, mapping, when = got
        info = engine.inspect_dataset(text, mapping or None)
        if not info["ok"]:
            return self._json(400, {"error": "missing columns: " + ", ".join(info["missing"]), "info": info})
        if info["rows"] > IMPORT_LIMIT:
            return self._json(400, {"error": f"too many rows (max {IMPORT_LIMIT})"})

        with STATE_LOCK:
            try:
                invoices = engine.load_register(text=text, mapping=mapping or None, report_date=when)
            except engine.RegisterError as exc:
                return self._json(400, {"error": str(exc)})
            UPLOADED_REGISTER.parent.mkdir(parents=True, exist_ok=True)
            UPLOADED_REGISTER.write_text(text, encoding="utf-8")
            DATASET_META.write_text(
                json.dumps(
                    {
                        "report_date": engine.REPORT_DATE.isoformat(),
                        "mapping": {k: v for k, v in info["mapping"].items() if v},
                        "rows": info["rows"],
                        "customers": len(invoices),
                        "imported_at": _date.today().isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            BOT = bot_module.Bot(invoices, STORE, use_llm=True)
        STORE.log(
            mode="v2",
            question="dataset import",
            intent="import",
            answer_summary=f"{len(invoices)} customers, as on {engine.REPORT_DATE.isoformat()}",
        )
        return self._json(200, {"ok": True, "customers": len(invoices), "report_date": engine.REPORT_DATE.isoformat()})

    def _handle_reset(self) -> None:
        global BOT
        with STATE_LOCK:
            engine.set_report_date(None)
            for path in (UPLOADED_REGISTER, DATASET_META):
                if path.exists():
                    path.unlink()
            BOT = bot_module.Bot(engine.load_register(), STORE, use_llm=True)
            count = len(BOT.invoices)
        STORE.log(mode="v2", question="dataset reset", intent="import", answer_summary="shipped register")
        return self._json(200, {"ok": True, "customers": count, "report_date": engine.REPORT_DATE.isoformat()})

    # -- legacy raw upload ----------------------------------------------
    def _handle_upload(self) -> None:
        global BOT
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return self._json(400, {"error": "empty upload"})
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return self._json(400, {"error": "file must be UTF-8 CSV"})

        info = engine.inspect_dataset(text)
        if not info["ok"]:
            return self._json(400, {"error": "missing columns: " + ", ".join(info["missing"]), "info": info})
        if info["rows"] > IMPORT_LIMIT:
            return self._json(400, {"error": f"too many rows (max {IMPORT_LIMIT})"})

        UPLOADED_REGISTER.parent.mkdir(parents=True, exist_ok=True)
        UPLOADED_REGISTER.write_text(text, encoding="utf-8")
        with STATE_LOCK:
            BOT = bot_module.Bot(engine.load_register(text=text), STORE, use_llm=True)
            count = len(BOT.invoices)
        STORE.log(mode="v2", question="register upload", intent="upload", answer_summary=f"{count} rows")
        return self._json(200, {"ok": True, "customers": count})


def _preview_days(text: str, mapping: dict | None, when: _date) -> list[dict]:
    """A few rows scored at the proposed as-on date, so the preview shows the effect."""
    previous = engine.REPORT_DATE
    try:
        invoices = engine.load_register(text=text, mapping=mapping, report_date=when)
    except engine.RegisterError:
        return []
    finally:
        engine.set_report_date(previous)
    out = []
    for cid, inv in list(sorted(invoices.items()))[:5]:
        scored = engine.score_invoice(inv)
        out.append(
            {
                "customer_id": cid,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days": scored.days,
                "amount": inv.amount,
                "priority": scored.priority,
                "partial": scored.partial,
            }
        )
    return out


def register_payload() -> list[dict]:
    promises = STORE.promises()
    rows = []
    for cid, inv in sorted(BOT.invoices.items()):
        s = engine.score_invoice(inv)
        promise = promises.get(cid) or {}
        rows.append(
            {
                "customer_id": cid,
                "invoice_no": inv.invoice_no,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days": s.days,
                "amount": inv.amount,
                "amount_text": engine.inr(inv.amount),
                "history": inv.history,
                "score": s.score,
                "priority": s.priority,
                "action": s.action,
                "partial": s.partial,
                "missing": inv.missing_fields,
                "promised_on": promise.get("promised_on"),
            }
        )
    return rows


def find_port(preferred: int = 8000, tries: int = 25) -> int:
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("No free port in range")


def serve(port: int | None = None) -> tuple[ThreadingHTTPServer, int]:
    port = port or find_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port
