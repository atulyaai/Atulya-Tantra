import asyncio
from datetime import datetime

import pytest

from atulya.agent import money as m
from atulya.agent import tools as t
from atulya.agent.intent_router import route_intent

NOW = datetime(2026, 10, 15, 10, 0)


@pytest.fixture(autouse=True)
def books(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "_DATA_DIR", tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()


def run(coro):
    return asyncio.run(coro)


def test_amounts_and_categories():
    assert m.parse_amount("₹1,250.50") == 1250.5 and m.parse_amount("Rs 500") == 500 and m.parse_amount("(300)") == 300
    assert m.parse_amount("abc") is None and m.parse_amount("") is None
    assert m.categorize("Swiggy order") == "food" and m.categorize("BIGBASKET") == "groceries" and m.categorize("xyz") == ""


def test_add_summarize_and_budget():
    assert "Saved ₹500 for groceries" in run(m.expense_add(500, note="bigbasket"))
    run(m.expense_add(250, "food", "lunch"))
    assert "Biggest: groceries ₹500, food ₹250" in run(m.expense_summary("month"))
    assert "₹500 on groceries" in run(m.expense_summary("month", "groceries"))
    assert "Budget for food is ₹1,000" in run(m.budget_set("food", 1000))
    assert "₹350 of ₹1,000 used, ₹650 left" in run(m.expense_add(100, "food", "tea"))
    out = run(m.expense_add(900, "food", "dinner"))
    assert "Over your food budget by" in out


def test_periods_and_undo():
    data = {"expenses": [
        {"ts": datetime(2026, 10, 14, 12).timestamp(), "amount": 100, "category": "a"},
        {"ts": datetime(2026, 9, 30, 12).timestamp(), "amount": 40, "category": "a"},
        {"ts": datetime(2026, 10, 15, 8).timestamp(), "amount": 7, "category": "b"}]}
    assert m.summarize(data["expenses"], "month", now=NOW)["total"] == 107
    assert m.summarize(data["expenses"], "last_month", now=NOW)["total"] == 40
    assert m.summarize(data["expenses"], "today", now=NOW)["total"] == 7
    run(m.expense_add(10, "x"))
    assert "Removed ₹10" in run(m.expense_undo())
    assert "nothing to undo" in run(m.expense_undo())


def test_bills_due_and_paid():
    run(m.bill_add("electricity", 2300, 18))
    due = m.bills_due_soon(m._load(), 7, NOW)
    assert due and due[0]["days"] == 3 and due[0]["name"] == "electricity"
    assert m.bills_due_soon(m._load(), 2, NOW) == []
    data = m._load()
    data["bills"][0]["paid"] = "2026-10"
    assert m.bills_due_soon(data, 7, NOW) == []
    assert "don't have a bill" in run(m.bill_paid("rent"))


STATEMENT = ("Account Statement\nDate,Narration,Withdrawal Amt.,Deposit Amt.,Balance\n"
             "01/10/2026,SWIGGY ORDER,450.00,,9000\n02/10/2026,SALARY,,50000,59000\n03/10/2026,UBER TRIP,180.50,,58800\n")


def test_statement_parse_debits_only_and_single_amount_column():
    rows = m.parse_statement(STATEMENT, "b1", NOW)
    assert [(r["note"], r["amount"], r["category"]) for r in rows] == [("SWIGGY ORDER", 450.0, "food"), ("UBER TRIP", 180.5, "transport")]
    single = "Date,Description,Amount\n2026-10-01,Netflix,-649\n2026-10-02,Refund,+100\n"
    assert [r["amount"] for r in m.parse_statement(single, "b2", NOW)] == [649.0]
    with pytest.raises(ValueError):
        m.parse_statement("a,b\n1,2\n", "b3")


def test_import_dedupes_undoes_and_stays_in_the_data_folder(tmp_path):
    (tmp_path / "data" / "s.csv").write_text(STATEMENT)
    assert "Added 2 entries" in run(m.statement_import("s.csv"))
    assert "Added 0 entries" in run(m.statement_import("s.csv")) and "skipped 2" in run(m.statement_import("s.csv"))
    assert "Removed the last statement import (2 entries)" in run(m.expense_undo())
    (tmp_path / "secret.csv").write_text(STATEMENT)
    assert "data folder" in run(m.statement_import(str(tmp_path / "secret.csv")))
    assert "data folder" in run(m.statement_import("../secret.csv"))


def test_voice_phrases_route_to_money_tools():
    r = route_intent("I spent 500 on groceries")
    assert (r.tool, r.arguments["amount"], r.arguments["note"]) == ("expense_add", 500.0, "groceries")
    assert route_intent("i spent ₹1,200 on dinner yesterday").arguments["date"] == "yesterday"
    r = route_intent("how much did I spend on food this month")
    assert (r.tool, r.arguments) == ("expense_summary", {"period": "month", "category": "food"})
    assert route_intent("how much did I spend last month").arguments["period"] == "last_month"
    assert route_intent("set a budget for food of 5000").arguments == {"category": "food", "amount": 5000.0}
    assert route_intent("what bills are due").tool == "bills_due"
    assert route_intent("add bill electricity 2300 due on 18").arguments == {"name": "electricity", "amount": 2300.0, "due_day": 18}
    assert route_intent("I paid the electricity bill").arguments == {"name": "electricity"}
    assert route_intent("undo the last expense").tool == "expense_undo"
    assert route_intent("what is the weather in Delhi").tool == "get_weather"   # untouched


def test_snapshot_and_bill_event_once(monkeypatch):
    run(m.expense_add(300, "food"))
    run(m.bill_add("rent", 15000, datetime.now().day))
    snap = m.snapshot()
    assert snap["month"]["total"] == 300 and snap["bills"][0]["name"] == "rent" and snap["currency"] == m.CURRENCY

    class Bus:
        events = []

        async def emit(self, kind, payload):
            self.events.append((kind, payload))

    bus = Bus()

    async def go():
        task = asyncio.create_task(m.watch_bills(bus, interval=0.05))
        await asyncio.sleep(0.2)
        task.cancel()

    run(go())
    assert [e[0] for e in bus.events] == ["bill.due"] and bus.events[0][1]["name"] == "rent"


def test_tools_with_a_parameter_called_name_run_through_the_registry():
    from atulya.cognition.toolbelt import build_unified_registry

    registry = build_unified_registry()
    result = run(registry.execute("bill_add", name="rent", amount=15000, due_day=5))
    assert result.success and "rent" in result.output
    assert "paid for this month" in run(registry.execute("bill_paid", name="rent")).output
