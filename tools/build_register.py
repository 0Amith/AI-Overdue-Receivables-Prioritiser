"""Builds knowledge/Receivables_Register.csv.

Fixed reporting date: 31 October 2026 (per project plan).
Every row is generated from a target "days overdue" so the dates can never
drift out of sync with the intended test cases.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

REPORT_DATE = date(2026, 10, 31)
OUT = Path(__file__).resolve().parent.parent / "knowledge" / "Receivables_Register.csv"

# (customer_id, days_overdue, amount, history_code, note)
# history_code: OnTime | SometimesLate | RepeatedlyLate
# None amount / None history are deliberate "missing data" rows.
ROWS = [
    # --- mandated boundary rows -------------------------------------------
    ("C001", 15, 185000, "SometimesLate", "BOUNDARY: exactly 15 days -> 1 point"),
    ("C002", 30, 240000, "RepeatedlyLate", "BOUNDARY: exactly 30 days -> 2 points, not 3"),
    ("C003", 60, 96000, "SometimesLate", "BOUNDARY: exactly 60 days -> 3 points, not 4"),
    ("C004", 45, 50000, "OnTime", "BOUNDARY: amount exactly Rs 50,000 -> 2 points"),
    ("C005", 40, 200000, "SometimesLate", "BOUNDARY: amount exactly Rs 2,00,000 -> 2 points"),
    # --- deliberate edge rows ---------------------------------------------
    ("C006", 62, 315000, "RepeatedlyLate", "BOUNDARY: 62 days -> 4 points"),
    ("C007", 12, 15000, "OnTime", "low score, small amount"),
    ("C008", 8, 120000, "OnTime", "small days, mid amount"),
    ("C009", 5, 265000, "OnTime", "small days, large amount"),
    ("C010", 21, 42000, "OnTime", "mid days, small amount"),
    # --- missing-data traps ------------------------------------------------
    ("C011", 33, 275000, "", "MISSING DATA: history code blank"),
    ("C012", 55, None, "RepeatedlyLate", "MISSING DATA: amount blank"),
    ("C013", 18, None, "", "MISSING DATA: amount and history both blank"),
    # --- not yet due -------------------------------------------------------
    ("C014", -15, 88000, "OnTime", "NOT YET DUE: due 15 Nov 2026"),
    # --- critical band (7-9) ----------------------------------------------
    ("C015", 95, 480000, "RepeatedlyLate", "critical"),
    ("C016", 78, 225000, "RepeatedlyLate", "critical"),
    ("C017", 66, 510000, "RepeatedlyLate", "critical"),
    ("C018", 120, 195000, "RepeatedlyLate", "critical"),
    ("C019", 88, 205000, "SometimesLate", "critical"),
    ("C020", 71, 520000, "SometimesLate", "critical"),
    # --- high band (5-6) ---------------------------------------------------
    ("C021", 34, 232000, "RepeatedlyLate", "high"),
    ("C022", 27, 410000, "RepeatedlyLate", "high"),
    ("C023", 50, 148000, "RepeatedlyLate", "high"),
    ("C024", 19, 495000, "SometimesLate", "high"),
    ("C025", 44, 230000, "SometimesLate", "high"),
    ("C026", 25, 118000, "SometimesLate", "high"),
    ("C027", 38, 305000, "OnTime", "high"),
    # --- medium band (3-4) -------------------------------------------------
    ("C028", 14, 275000, "SometimesLate", "medium"),
    ("C029", 9, 190000, "RepeatedlyLate", "medium"),
    ("C030", 52, 44000, "SometimesLate", "medium"),
    ("C031", 22, 38000, "OnTime", "medium"),
    ("C032", 3, 290000, "RepeatedlyLate", "medium"),
    ("C033", 41, 61000, "OnTime", "medium"),
    ("C034", 16, 32000, "SometimesLate", "medium"),
    # --- low band (1-2) ----------------------------------------------------
    ("C035", 2, 27000, "OnTime", "low"),
    ("C036", 11, 98000, "OnTime", "low"),
    ("C037", 6, 46000, "OnTime", "low"),
    ("C038", 29, 34000, "OnTime", "low"),
    ("C039", 1, 21000, "OnTime", "low"),
    ("C040", 47, 39000, "OnTime", "low"),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "Customer ID",
                "Invoice No.",
                "Invoice Date",
                "Due Date",
                "Amount (Rs)",
                "History Code",
            ]
        )
        for i, (cid, days, amount, history, _note) in enumerate(ROWS, start=1):
            due = REPORT_DATE - timedelta(days=days)
            invoice_date = due - timedelta(days=30)
            w.writerow(
                [
                    cid,
                    f"INV-2026-{1000 + i}",
                    invoice_date.isoformat(),
                    due.isoformat(),
                    "" if amount is None else amount,
                    history,
                ]
            )
    print(f"wrote {OUT} ({len(ROWS)} rows)")


if __name__ == "__main__":
    main()
