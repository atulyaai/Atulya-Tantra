"""Money helper: expenses, budgets, bills and bank-statement import. Local only.

Everything is kept in ``data/agent/money.json`` on this computer. Atulya never connects to a bank and never
moves money; it only records what you tell it (or what is in a statement file you give it) and answers questions.
"""
from __future__ import annotations

import asyncio
import csv
import io
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from atulya.agent import tools as _t
from atulya.agent.tools import tool

CURRENCY = os.environ.get("ATULYA_CURRENCY", "₹")

# Keyword -> category, first match wins. Edit freely; unknown text keeps the words you used as its category.
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("groceries", ("grocer", "bigbasket", "blinkit", "zepto", "dmart", "vegetable", "supermarket", "milk")),
    ("food", ("swiggy", "zomato", "restaurant", "cafe", "lunch", "dinner", "breakfast", "snack", "coffee")),
    ("transport", ("uber", "ola ", "rapido", "fuel", "petrol", "diesel", "metro", "auto", "taxi", "toll", "parking")),
    ("bills", ("electricity", "water bill", "recharge", "jio", "airtel", "vodafone", "wifi", "broadband", "gas bill", "rent")),
    ("shopping", ("amazon", "flipkart", "myntra", "ajio", "mall", "clothes", "shoes")),
    ("health", ("pharmacy", "apollo", "doctor", "hospital", "medicine", "clinic", "lab test")),
    ("entertainment", ("netflix", "spotify", "movie", "hotstar", "prime video", "concert", "game")),
    ("investments", ("sip", "mutual fund", "zerodha", "groww", "stocks", "demat", "ppf", "nps")),
]


def categorize(text: str) -> str:
    t = f" {str(text).lower()} "
    for category, words in RULES:
        if any(w in t for w in words):
            return category
    return ""


def parse_amount(value: Any) -> float | None:
    """'₹1,250.50', 'Rs 500', '(300)', '-45' -> a positive number (None if it isn't one)."""
    s = re.sub(r"[^\d.,()\-]", "", str(value or "")).replace(",", "")
    neg = s.startswith("(") or s.startswith("-")
    s = s.strip("()-")
    try:
        return abs(float(s)) if s else None
    except ValueError:
        return None if not neg else None


def money(x: float) -> str:
    return f"{CURRENCY}{x:,.0f}" if abs(x - round(x)) < 0.005 else f"{CURRENCY}{x:,.2f}"


def _load() -> dict[str, Any]:
    data = _t._load_json("money.json")
    data = data if isinstance(data, dict) else {}
    data.setdefault("expenses", [])
    data.setdefault("budgets", {})
    data.setdefault("bills", [])
    return data


def _save(data: dict[str, Any]) -> None:
    _t._save_json("money.json", data)


def _period(name: str, now: datetime) -> tuple[datetime, datetime, str]:
    name = (name or "month").strip().lower().replace(" ", "_")
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if name == "today":
        return today, today + timedelta(days=1), "today"
    if name in ("week", "this_week"):
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7), "this week"
    if name in ("last_month", "previous_month"):
        end = today.replace(day=1)
        return (end - timedelta(days=1)).replace(day=1), end, "last month"
    if name in ("year", "this_year"):
        return today.replace(month=1, day=1), today.replace(year=today.year + 1, month=1, day=1), "this year"
    start = today.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt, "this month"


def summarize(expenses: list[dict[str, Any]], period: str = "month", category: str = "", now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    start, end, label = _period(period, now)
    chosen = [e for e in expenses if start.timestamp() <= e["ts"] < end.timestamp()
              and (not category or e.get("category", "").lower() == category.lower())]
    by_cat: dict[str, float] = {}
    for e in chosen:
        by_cat[e.get("category") or "other"] = by_cat.get(e.get("category") or "other", 0) + e["amount"]
    return {"label": label, "total": sum(e["amount"] for e in chosen), "count": len(chosen),
            "by_category": sorted(by_cat.items(), key=lambda kv: -kv[1])}


def _parse_when(text: str, now: datetime) -> float:
    t = (text or "").strip().lower()
    if not t or t == "today":
        return now.timestamp()
    if t == "yesterday":
        return (now - timedelta(days=1)).timestamp()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(text.strip(), fmt).replace(hour=12).timestamp()
        except ValueError:
            continue
    return now.timestamp()


def _budget_note(data: dict[str, Any], category: str, now: datetime) -> str:
    cap = data["budgets"].get(category.lower())
    if not cap:
        return ""
    spent = summarize(data["expenses"], "month", category, now)["total"]
    left = cap - spent
    return (f" {category.title()} budget: {money(spent)} of {money(cap)} used, {money(left)} left." if left >= 0
            else f" Over your {category} budget by {money(-left)} ({money(spent)} of {money(cap)}).")


@tool("expense_add", "Record money you spent (a note for your own books; nothing is paid)", {
    "amount": {"type": "number", "description": "Amount spent"},
    "category": {"type": "string", "description": "e.g. groceries, food, transport, bills (guessed from the note if blank)", "default": ""},
    "note": {"type": "string", "description": "What it was for", "default": ""},
    "date": {"type": "string", "description": "Optional: today, yesterday or YYYY-MM-DD", "default": ""},
})
async def expense_add(amount: float, category: str = "", note: str = "", date: str = "") -> str:
    value = parse_amount(amount)
    if not value:
        return "Tell me how much it was."
    now = datetime.now()
    category = (category or categorize(note) or "other").strip().lower()
    data = _load()
    data["expenses"].append({"id": uuid.uuid4().hex[:8], "ts": _parse_when(date, now), "amount": value,
                             "category": category, "note": note.strip()[:120]})
    _save(data)
    month = summarize(data["expenses"], "month", now=now)["total"]
    return f"Saved {money(value)} for {category}. This month so far: {money(month)}." + _budget_note(data, category, now)


@tool("expense_summary", "How much you spent: today, this week, this month, last month or this year, optionally for one category", {
    "period": {"type": "string", "description": "today | week | month | last_month | year", "default": "month"},
    "category": {"type": "string", "description": "Optional category", "default": ""},
})
async def expense_summary(period: str = "month", category: str = "") -> str:
    s = summarize(_load()["expenses"], period, category.strip())
    if not s["count"]:
        return f"I have no spending recorded for {s['label']}" + (f" on {category}." if category else ".")
    top = ", ".join(f"{c} {money(v)}" for c, v in s["by_category"][:4])
    which = f" on {category}" if category else ""
    return f"You spent {money(s['total'])}{which} {s['label']} across {s['count']} entries" + ("" if category else f". Biggest: {top}.")


@tool("budget_set", "Set a monthly budget for a category", {
    "category": {"type": "string", "description": "e.g. food"},
    "amount": {"type": "number", "description": "Monthly limit"},
})
async def budget_set(category: str, amount: float) -> str:
    value = parse_amount(amount)
    if not category.strip() or not value:
        return "Tell me the category and the monthly amount."
    data = _load()
    data["budgets"][category.strip().lower()] = value
    _save(data)
    return f"Budget for {category.strip().lower()} is {money(value)} a month." + _budget_note(data, category.strip(), datetime.now())


@tool("expense_undo", "Remove the last expense you added (or the last statement import)", {})
async def expense_undo() -> str:
    data = _load()
    if not data["expenses"]:
        return "There is nothing to undo."
    batch = data["expenses"][-1].get("batch")
    if batch:
        removed = [e for e in data["expenses"] if e.get("batch") == batch]
        data["expenses"] = [e for e in data["expenses"] if e.get("batch") != batch]
        _save(data)
        return f"Removed the last statement import ({len(removed)} entries)."
    gone = data["expenses"].pop()
    _save(data)
    return f"Removed {money(gone['amount'])} for {gone['category']}."


@tool("bill_add", "Remember a monthly bill and the day it is due", {
    "name": {"type": "string", "description": "e.g. electricity"},
    "amount": {"type": "number", "description": "Usual amount"},
    "due_day": {"type": "integer", "description": "Day of the month it is due (1-28)"},
})
async def bill_add(name: str, amount: float, due_day: int) -> str:
    value, day = parse_amount(amount), int(due_day or 0)
    if not name.strip() or not value or not 1 <= day <= 31:
        return "Tell me the bill's name, amount and the day of the month it is due."
    data = _load()
    data["bills"] = [b for b in data["bills"] if b["name"].lower() != name.strip().lower()]
    data["bills"].append({"id": uuid.uuid4().hex[:8], "name": name.strip(), "amount": value, "due_day": day, "paid": ""})
    _save(data)
    return f"I will remind you about {name.strip()} ({money(value)}) before the {day}th each month. I never pay it for you."


def _due_date(bill: dict[str, Any], now: datetime) -> datetime:
    day = min(int(bill["due_day"]), 28 if now.month == 2 else 30 if now.month in (4, 6, 9, 11) else 31)
    due = now.replace(day=day, hour=9, minute=0, second=0, microsecond=0)
    if due < now.replace(hour=0, minute=0, second=0, microsecond=0):
        nxt = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        due = nxt.replace(day=min(int(bill["due_day"]), 28), hour=9)
    return due


def bills_due_soon(data: dict[str, Any], days: int, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now()
    out = []
    for b in data["bills"]:
        due = _due_date(b, now)
        if b.get("paid") == due.strftime("%Y-%m"):
            continue
        left = (due.date() - now.date()).days
        if 0 <= left <= days:
            out.append({**b, "days": left, "due": due.strftime("%d %b")})
    return sorted(out, key=lambda b: b["days"])


@tool("bills_due", "Which of your bills are due in the next few days", {
    "days": {"type": "integer", "description": "How many days ahead (default 7)", "default": 7},
})
async def bills_due(days: int = 7) -> str:
    due = bills_due_soon(_load(), int(days or 7))
    if not due:
        return f"No bills are due in the next {days} days."
    return "\n".join(f"{b['name']}: {money(b['amount'])} due {b['due']}" + (" (today)" if b["days"] == 0 else f" (in {b['days']} days)") for b in due)


@tool("bill_paid", "Mark a bill as paid for this month (you paid it; I only note it)", {
    "name": {"type": "string", "description": "Bill name"},
})
async def bill_paid(name: str) -> str:
    data = _load()
    now = datetime.now()
    for b in data["bills"]:
        if name.strip().lower() in b["name"].lower():
            b["paid"] = _due_date(b, now).strftime("%Y-%m")
            _save(data)
            return f"Noted: {b['name']} is paid for this month."
    return f"I don't have a bill called {name}."


# ── bank statement import (CSV you give me; I never log in anywhere) ─────────────────────────
_DATE_COLS = ("date", "txn date", "transaction date", "value date", "posting date")
_DESC_COLS = ("description", "narration", "particulars", "details", "remarks", "transaction details")
_DEBIT_COLS = ("debit", "withdrawal", "withdrawal amt.", "withdrawals", "dr")
_AMOUNT_COLS = ("amount", "amount (inr)", "transaction amount")


def parse_statement(text: str, batch: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """Turn a bank-statement CSV into expense entries (money going out only)."""
    now = now or datetime.now()
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    head = next((i for i, r in enumerate(rows) if any(c.strip().lower() in _DATE_COLS for c in r)), None)
    if head is None:
        raise ValueError("I couldn't find a Date column. Export the statement as CSV with a header row.")
    cols = [c.strip().lower() for c in rows[head]]
    pick = lambda names: next((cols.index(n) for n in names if n in cols), None)  # noqa: E731
    d_i, t_i, db_i, am_i = pick(_DATE_COLS), pick(_DESC_COLS), pick(_DEBIT_COLS), pick(_AMOUNT_COLS)
    if db_i is None and am_i is None:
        raise ValueError("I couldn't find a Debit or Amount column.")
    out = []
    for r in rows[head + 1:]:
        if len(r) <= max(i for i in (d_i, t_i, db_i, am_i) if i is not None):
            continue
        raw = r[db_i] if db_i is not None else r[am_i]
        if db_i is None and str(raw).strip().startswith(("+",)):
            continue  # a credit in a single-amount column
        value = parse_amount(raw)
        if not value or (db_i is None and re.search(r"\bcr\b|credit", " ".join(r).lower())):
            continue
        desc = r[t_i].strip() if t_i is not None else ""
        out.append({"id": uuid.uuid4().hex[:8], "ts": _parse_when(r[d_i], now), "amount": value,
                    "category": categorize(desc) or "other", "note": desc[:120], "batch": batch})
    return out


@tool("statement_import", "Add the spending from a bank statement CSV in your Atulya data folder", {
    "path": {"type": "string", "description": "File name or path of the CSV inside the data folder"},
})
async def statement_import(path: str) -> str:
    root = Path("data").resolve()
    file = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if root not in file.parents or file.suffix.lower() != ".csv" or not file.is_file():
        return "Put the statement CSV in the Atulya data folder (for example data/statement.csv) and tell me its name."
    try:
        entries = parse_statement(await asyncio.to_thread(file.read_text, "utf-8-sig"), uuid.uuid4().hex[:8])
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        return f"I couldn't read that statement: {exc}"
    if not entries:
        return "I found no spending in that file."
    data = _load()
    known = {(e["ts"], e["amount"], e["note"]) for e in data["expenses"]}
    fresh = [e for e in entries if (e["ts"], e["amount"], e["note"]) not in known]
    data["expenses"].extend(fresh)
    _save(data)
    top = ", ".join(f"{c} {money(v)}" for c, v in summarize(fresh, "year", now=datetime.now() + timedelta(days=366 * 5))["by_category"][:3])
    return (f"Added {len(fresh)} entries ({money(sum(e['amount'] for e in fresh))})"
            + (f", skipped {len(entries) - len(fresh)} already saved" if len(entries) != len(fresh) else "")
            + (f". Biggest: {top}." if top else ".") + " Say “undo the import” if that isn't right.")


def snapshot(now: datetime | None = None) -> dict[str, Any]:
    """What the dashboard tile shows."""
    now = now or datetime.now()
    data = _load()
    month = summarize(data["expenses"], "month", now=now)
    last = summarize(data["expenses"], "last_month", now=now)
    budgets = [{"category": c, "limit": v, "spent": summarize(data["expenses"], "month", c, now)["total"]}
               for c, v in sorted(data["budgets"].items())]
    return {"currency": CURRENCY, "month": month, "last_month_total": last["total"], "budgets": budgets,
            "bills": bills_due_soon(data, 10, now), "entries": len(data["expenses"])}


async def watch_bills(events: Any, interval: float = 3600.0, lead_days: int = 3) -> None:
    """Publish ``bill.due`` once a day for each unpaid bill due within ``lead_days``."""
    told: set[str] = set()
    while True:
        try:
            today = time.strftime("%Y-%m-%d")
            for b in bills_due_soon(_load(), lead_days):
                key = f"{b['id']}@{today}"
                if key not in told:
                    told.add(key)
                    await events.emit("bill.due", {"name": b["name"], "amount": money(b["amount"]), "due": b["due"], "days": b["days"]})
            if len(told) > 400:
                told.clear()
        except Exception:  # noqa: BLE001 - the watcher must never die
            pass
        await asyncio.sleep(interval)
