import asyncio
from datetime import datetime

import pytest

from atulya.yantra import money as m
from atulya.yantra import tools as t
from atulya.yantra.intent_router import route_intent

NOW = datetime(2026, 10, 15, 10, 0)


@pytest.fixture(autouse=True)
def books(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "_DATA_DIR", tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kosh").mkdir()


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
    (tmp_path / "kosh" / "s.csv").write_text(STATEMENT)
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
    from atulya.buddhi.toolbelt import build_unified_registry

    registry = build_unified_registry()
    result = run(registry.execute("bill_add", name="rent", amount=15000, due_day=5))
    assert result.success and "rent" in result.output
    assert "paid for this month" in run(registry.execute("bill_paid", name="rent")).output


# ── bank alerts (sample wordings written to resemble common Indian-bank messages; not copied from a bank) ──
ALERTS = [
    ("Rs 500.00 debited from A/c XX1234 on 03-10-26 to VPA swiggy@icici. UPI Ref 4455", 500.0, "swiggy", "1234", "debit"),
    ("Sent Rs.250.00 from HDFC Bank A/c *4321 To BIGBASKET On 03/10/26 Ref 99887", 250.0, "BIGBASKET", "4321", "debit"),
    ("INR 1,299.00 spent on ICICI Bank Card XX9876 on 03-Oct-26 at AMAZON. Avl Lmt INR 50,000", 1299.0, "AMAZON", "9876", "debit"),
    ("Rs.120 spent on Credit Card x5566 at ZOMATO on 2026-10-03.", 120.0, "ZOMATO", "5566", "debit"),
    ("Paid Rs.180.50 to Uber via Paytm", 180.5, "Uber", "", "debit"),
    ("Your a/c no. XXXX1234 is credited with Rs 50,000.00 on 01-10-2026 by salary", 50000.0, "", "1234", "credit"),
]


@pytest.mark.parametrize("text,amount,merchant,acct,kind", ALERTS)
def test_alert_parsing(text, amount, merchant, acct, kind):
    a = m.parse_alert(text, NOW)
    assert a and (a["amount"], a["kind"], a["account"]) == (amount, kind, acct)
    assert merchant.lower() in a["merchant"].lower()


@pytest.mark.parametrize("text", [
    "123456 is your OTP for transaction of Rs 500. Do not share it.",
    "Your credit card bill of Rs 4,500 is due on 15-10-26. Pay now.",
    "Rs 5000 will be debited from your account on 20-10-26 for SIP.",
    "Transaction of Rs 300 failed due to insufficient balance.",
    "Pre-approved loan offer up to Rs 5,00,000! Apply now.",
    "Hello, see you at 5pm", "",
])
def test_alerts_that_must_not_be_recorded(text):
    assert m.parse_alert(text, NOW) is None


def test_alert_dates_are_read_from_the_message():
    a = m.parse_alert("Rs 500 debited from A/c XX1234 on 03-10-26 to VPA x@y", NOW)
    assert datetime.fromtimestamp(a["ts"]).date().isoformat() == "2026-10-03"
    b = m.parse_alert("Paid Rs.180.50 to Uber via Paytm", NOW)
    assert datetime.fromtimestamp(b["ts"]).date() == NOW.date()


def test_record_alert_categorises_and_never_double_counts():
    text = "INR 1,299.00 spent on ICICI Bank Card XX9876 on 03-Oct-26 at AMAZON."
    assert m.record_alert(text, "sms", NOW)["status"] == "added"
    assert m.record_alert(text, "sms", NOW)["status"] == "duplicate"                      # same text again
    email = "Alert: INR 1,299.00 spent on ICICI Bank Card XX9876 on 03-Oct-26 at AMAZON PAY INDIA"
    assert m.record_alert(email, "email", NOW)["status"] == "duplicate"                   # same transaction by email
    data = m._load()
    assert len(data["expenses"]) == 1 and data["expenses"][0]["category"] == "shopping" and data["expenses"][0]["source"] == "sms"
    assert m.record_alert("Rs 50,000 credited to A/c XX1234 on 01-10-26 salary", "sms", NOW)["kind"] == "credit"
    assert len(m._load()["expenses"]) == 1 and m._load()["income"][0]["amount"] == 50000
    assert m.record_alert("hello there", "sms", NOW)["status"] == "ignored"


def test_two_real_purchases_of_the_same_amount_on_one_day_are_both_kept():
    a = "Rs 100 spent on Card x1111 at TEA STALL on 03-10-26 ref 1"
    b = "Rs 100 spent on Card x1111 at TEA STALL on 03-10-26 ref 2"
    assert m.record_alert(a, "sms", NOW)["status"] == "added" and m.record_alert(b, "sms", NOW)["status"] == "added"


def test_email_text_and_tool(monkeypatch):
    import email

    msg = email.message_from_string("Subject: Txn alert\nContent-Type: text/plain\n\nRs 75 spent on Card x2222 at CAFE COFFEE on 03-10-26.")
    assert "CAFE COFFEE" in m.message_text(msg)

    class FakeGoogle:
        async def list_messages(self, query, limit):
            return [{"subject": "Alert", "snippet": "Rs 75 spent on Card x2222 at CAFE COFFEE on 03-10-26."},
                    {"subject": "Newsletter", "snippet": "10% offer today"}]

    monkeypatch.setattr(t, "_google", lambda: FakeGoogle())
    assert "Added 1 transactions from email, ₹75 spent" in run(m.expenses_from_email(7))
    assert "no new bank transactions (1 already saved)" in run(m.expenses_from_email(7))
    monkeypatch.setattr(t, "_google", lambda: None)
    monkeypatch.setattr(t, "_EMAIL_CFG", {})
    assert "isn't set up" in run(m.expenses_from_email(7))


def test_sms_inbox_endpoint_is_locked_to_its_own_key(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from atulya.sevak.app import app
    from atulya.sevak.state import ADMIN_TOKEN

    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
    c = TestClient(app)
    sms = "Rs 500.00 debited from A/c XX1234 on 03-10-26 to VPA swiggy@icici"
    assert c.post("/api/money/sms", content=sms).status_code == 401                              # no key
    assert c.post("/api/money/sms", content=sms, headers={"X-Atulya-Inbox": ADMIN_TOKEN}).status_code == 401  # the admin token is NOT the key
    key = c.get("/api/money/inbox", headers={"X-Atulya-Token": ADMIN_TOKEN}).json()["key"]
    assert c.get("/api/money/inbox").status_code in (401, 403)
    ok = c.post("/api/money/sms", content=sms, headers={"X-Atulya-Inbox": key})
    assert ok.status_code == 200 and ok.json()["status"] == "added"
    assert c.post("/api/money/sms", json={"message": sms}, headers={"X-Atulya-Inbox": key}).json()["status"] == "duplicate"
    assert c.post(f"/api/money/sms?key={key}", content="text=" + "Rs+250+spent+on+Card+x1+at+CAFE+on+03-10-26").json()["status"] == "added"
    assert c.post("/api/money/sms", content="  ", headers={"X-Atulya-Inbox": key}).status_code == 400
    # the inbox key opens nothing else
    assert c.get("/api/dashboard", headers={"X-Atulya-Token": key}).status_code in (401, 403)
    new = c.post("/api/money/inbox/rotate", headers={"X-Atulya-Token": ADMIN_TOKEN}).json()["key"]
    assert new != key and c.post("/api/money/sms", content=sms, headers={"X-Atulya-Inbox": key}).status_code == 401


def test_email_phrases_route_but_plain_email_checks_do_not():
    assert route_intent("check my email for bank transactions").tool == "expenses_from_email"
    assert route_intent("update my expenses from email").tool == "expenses_from_email"
    assert route_intent("check my email").tool == "fetch_emails"


# ── "if not sure, check with AI" ─────────────────────────────────────────────────────────────
ODD = "Hi! Your wallet ZipPay: Rs 340.00 moved to FreshMart on 03-10-26. Thanks for using ZipPay."


def fake_ai(reply):
    async def ask(prompt):
        ask.prompts.append(prompt)
        return reply
    ask.prompts = []
    return ask


def test_rules_first_ai_only_when_unsure():
    assert m.parse_alert(ODD, NOW) is None                                   # the rules cannot read this wording
    ask = fake_ai('{"needed": true, "kind": "debit", "amount": 340, "merchant": "FreshMart", "category": "groceries"}')
    r = run(m.record_alert_async(ODD, "sms", NOW, ask))
    assert r["status"] == "added" and r["ai"] is True and r["category"] == "groceries" and "please check" in m._alert_reply(r)
    assert m._load()["expenses"][0]["ai"] is True
    clear = "Rs 500.00 debited from A/c XX1234 on 03-10-26 to VPA swiggy@icici"
    ask2 = fake_ai("{}")
    assert run(m.record_alert_async(clear, "sms", NOW, ask2))["status"] == "added" and ask2.prompts == []   # rules were enough


def test_the_ai_is_never_asked_about_otps_or_offers_and_cannot_invent_numbers():
    ask = fake_ai('{"needed": true, "kind": "debit", "amount": 500, "merchant": "x", "category": "other"}')
    for text in ("123456 is your OTP. Rs 500 will be debited. Do not share.", "Pre-approved offer: borrow Rs 500000 now!", "see you at 5"):
        assert run(m.record_alert_async(text, "sms", NOW, ask))["status"] == "ignored"
    assert ask.prompts == []
    liar = fake_ai('{"needed": true, "kind": "debit", "amount": 9999, "merchant": "x", "category": "other"}')
    assert run(m.record_alert_async(ODD, "sms", NOW, liar))["status"] == "ignored"            # 9999 is not in the message
    for bad in ('{"needed": false, "kind": "other", "amount": null}', "not json", '{"needed": true, "kind": "debit", "amount": -5}',
                '{"needed": true, "kind": "transfer", "amount": 340}'):
        assert run(m.record_alert_async(ODD, "sms", NOW, fake_ai(bad)))["status"] == "ignored"
    assert m._load()["expenses"] == []


def test_ai_privacy_and_off_switch(monkeypatch):
    assert m.redact_for_ai("Rs 1,299.00 sent to 9876543210 ref 123456789012 mail a@b.com see https://x.io/y") == \
        "Rs 1,299.00 sent to ########## ref ############ mail [email] see [link]"
    ask = fake_ai('{"needed": true, "kind": "debit", "amount": 340, "merchant": "FreshMart", "category": "groceries"}')
    run(m.record_alert_async("ZipPay: Rs 340.00 moved to 9876543210 FreshMart on 03-10-26", "sms", NOW, ask))
    assert "9876543210" not in ask.prompts[0] and "<<<MESSAGE" in ask.prompts[0]              # redacted, and fenced as data
    monkeypatch.setenv("ATULYA_MONEY_AI", "off")
    off = fake_ai("{}")
    assert run(m.record_alert_async("Wallet: Rs 77.00 moved to Shop on 04-10-26", "sms", NOW, off))["status"] == "ignored" and off.prompts == []
