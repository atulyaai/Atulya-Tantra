"""Autonomous Expense and Transaction Tracker for Atulya-Tantra (Jarvis).

Stores personal finances in SQLite and synchronizes to Google Sheets.
Supports automated parsing of bank & UPI transaction alerts (SMS/Email).
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("ATULYA_DATA_DIR", "data"))


class ExpenseStore:
    def __init__(self, data_dir: Path | str | None = None):
        self.path = Path(data_dir or DATA_DIR) / "expenses.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    amount REAL,
                    merchant TEXT,
                    category TEXT,
                    date TEXT,
                    notes TEXT,
                    created_at REAL
                )
            """)

    def log(self, user_id: str, amount: float, merchant: str, category: str = "General",
            date: str | None = None, notes: str = "") -> dict[str, Any]:
        """Record an expense entry."""
        if amount <= 0:
            raise ValueError("Expense amount must be greater than zero")
        date_str = date or datetime.now().strftime("%Y-%m-%d %H:%M")
        with closing(sqlite3.connect(self.path)) as db, db:
            cursor = db.execute(
                "INSERT INTO expenses (user_id, amount, merchant, category, date, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, amount, merchant.strip()[:100], category.strip()[:50], date_str, notes[:200], time.time())
            )
            entry_id = cursor.lastrowid
        return {
            "id": entry_id,
            "amount": amount,
            "merchant": merchant,
            "category": category,
            "date": date_str,
            "notes": notes
        }

    def list_recent(self, user_id: str, limit: int = 15) -> list[dict[str, Any]]:
        """List recent recorded expenses."""
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id, amount, merchant, category, date, notes FROM expenses WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def summary(self, user_id: str) -> dict[str, Any]:
        """Get total expenses and category breakdown."""
        with closing(sqlite3.connect(self.path)) as db:
            total = db.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id=?", (user_id,)).fetchone()[0]
            count = db.execute("SELECT count(*) FROM expenses WHERE user_id=?", (user_id,)).fetchone()[0]
            categories = db.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category", (user_id,)).fetchall()
        return {
            "total_spent": total,
            "total_transactions": count,
            "by_category": {cat: amt for cat, amt in categories}
        }


def parse_transaction_sms(sms_text: str) -> dict[str, Any] | None:
    """Parse Indian bank / UPI SMS formats (HDFC, SBI, ICICI, Axis, Paytm, PhonePe, GPay)."""
    text = sms_text.strip()
    # Amount match (e.g. Rs. 450.00, INR 1200, Rs 50)
    amt_match = re.search(r"(?:rs\.?|inr)\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
    if not amt_match:
        return None
    amount = float(amt_match.group(1).replace(",", ""))

    # Merchant match (e.g. to Swiggy, at Amazon, VPA someone@upi, Info: Uber)
    merchant = "Unknown Merchant"
    m_match = re.search(r"\b(?:to|at|vpa|info)\s*[:\s]\s*([A-Za-z0-9\.\-_@ ]{2,30})", text, re.IGNORECASE)
    if m_match:
        merchant = m_match.group(1).strip()
        # Clean trailing transaction words
        merchant = re.sub(r"\s+(on|ref|avl|bal|upi|acc).*$", "", merchant, flags=re.IGNORECASE).strip()

    # Category heuristic
    m_lower = merchant.lower()
    if any(k in m_lower for k in ("swiggy", "zomato", "restaurant", "cafe", "food", "mcdonald", "starbucks")):
        category = "Food & Dining"
    elif any(k in m_lower for k in ("uber", "ola", "metro", "fuel", "petrol", "transport", "irctc", "flight")):
        category = "Travel & Commute"
    elif any(k in m_lower for k in ("amazon", "flipkart", "myntra", "store", "mall", "market")):
        category = "Shopping"
    elif any(k in m_lower for k in ("pharmacy", "hospital", "clinic", "lab", "apollo")):
        category = "Healthcare"
    elif any(k in m_lower for k in ("electricity", "water", "gas", "bill", "broadband", "recharge", "airtel", "jio")):
        category = "Utilities"
    else:
        category = "Personal"

    return {
        "amount": amount,
        "merchant": merchant,
        "category": category,
        "raw": text[:200]
    }
