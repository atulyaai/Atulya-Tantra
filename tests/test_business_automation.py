"""Tests for Business and Enterprise Automation Tools."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from yantra.capabilities import create_default_registry
from yantra.capabilities.business_automation import (
    HRAttendancePayrollTool,
    DataScrubberTool,
    GSTReconciliationTool,
    AccountingERPTool,
    SAPAutomationTool,
)


@pytest.mark.anyio
async def test_hr_attendance_payroll(tmp_path):
    # Create input CSV
    csv_file = tmp_path / "attendance.csv"
    csv_file.write_text(
        "EmployeeID,Name,DaysPresent,TotalDays\n"
        "EMP001,John Doe,28,30\n"
        "EMP002,Jane Smith,30,30\n"
    )

    basic_pay = {"EMP001": 50000, "EMP002": 60000}
    tool = HRAttendancePayrollTool()

    result = await tool.execute(
        input_csv=str(csv_file),
        basic_pay_map=basic_pay,
        tax_rate=0.1
    )

    assert result.success
    assert "Processed payroll for 2 employees" in result.output
    assert (tmp_path / "payroll_output.json").exists()

    saved_data = json.loads((tmp_path / "payroll_output.json").read_text())
    assert len(saved_data) == 2
    assert saved_data[0]["EmployeeID"] == "EMP001"
    assert saved_data[0]["NetPay"] == 46200.0  # (50000 * 28/30 + 10%) - 10% tax = 46200


@pytest.mark.anyio
async def test_data_scrubber(tmp_path):
    csv_file = tmp_path / "messy.csv"
    csv_file.write_text(
        "ID,Name,Phone,Notes\n"
        "1,Alice,9876543210,  \n"
        "2,Bob, ,Good\n"
        "1,Alice,9876543210,Duplicate\n"
    )

    tool = DataScrubberTool()
    result = await tool.execute(
        input_csv=str(csv_file),
        clean_nulls=True,
        format_phone=True,
        remove_dupes=True
    )

    assert result.success
    cleaned_file = tmp_path / "cleaned_messy.csv"
    assert cleaned_file.exists()

    content = cleaned_file.read_text().splitlines()
    assert len(content) == 3  # Header + 2 unique rows
    assert "+91 98765-43210" in content[1]  # formatted phone
    assert "N/A" in content[1]  # cleaned empty space


@pytest.mark.anyio
async def test_gst_reconciliation(tmp_path):
    sales_file = tmp_path / "sales.csv"
    sales_file.write_text(
        "InvoiceNo,Amount,Tax,Vendor\n"
        "INV001,1000,180,VendorA\n"
        "INV002,2000,360,VendorB\n"
    )

    purchase_file = tmp_path / "purchase.csv"
    purchase_file.write_text(
        "InvoiceNo,Amount,Tax,Vendor\n"
        "INV001,1000,180,VendorA\n"
        "INV002,1900,342,VendorB\n"  # value mismatch
    )

    tool = GSTReconciliationTool()
    result = await tool.execute(sales_csv=str(sales_file), purchase_csv=str(purchase_file))

    assert result.success
    report_file = tmp_path / "gst_reconciliation_report.json"
    assert report_file.exists()

    report = json.loads(report_file.read_text())
    assert report["MatchedCount"] == 1
    assert report["MismatchCount"] == 1
    assert report["Mismatches"][0]["Type"] == "ValueMismatch"


@pytest.mark.anyio
async def test_accounting_invoice():
    items = [
        {"name": "Laptop", "qty": 1, "price": 45000},
        {"name": "Mouse", "qty": 2, "price": 750}
    ]

    tool = AccountingERPTool()
    result = await tool.execute(customer_name="Acme Corp", items=items, tax_rate=0.18)

    assert result.success
    assert "Invoice" in result.output
    assert result.metadata["Total"] == 54870.0  # (45000 + 1500) * 1.18


@pytest.mark.anyio
async def test_sap_automation(tmp_path):
    recipe_file = tmp_path / "recipe.yaml"
    recipe = {
        "connection": {"system_id": "PRD", "client": "800"},
        "steps": [
            {
                "tcode": "VA01",
                "action": "CreateSalesOrder",
                "fields": {"OrderType": "OR", "SoldTo": "100203"}
            }
        ]
    }
    recipe_file.write_text(yaml.dump(recipe))

    tool = SAPAutomationTool()
    result = await tool.execute(recipe_yaml_path=str(recipe_file))

    assert result.success
    assert "VA01" in result.output
    assert "PRD" in result.output


def test_registry_integration():
    registry = create_default_registry()
    tools = registry.list_tools()
    tool_names = [t["name"] for t in tools]

    assert "hr_attendance_payroll" in tool_names
    assert "data_scrub" in tool_names
    assert "gst_reconcile" in tool_names
    assert "accounting_invoice" in tool_names
    assert "sap_gui_automation" in tool_names
