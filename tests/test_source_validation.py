import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from backend.parser import ImportValidationError, parse_report

ROOT = Path(__file__).resolve().parent.parent
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def changed_workbook(tmp_path, address, value=None, error=False):
    source = next((ROOT / "data" / "input").glob("*КОМПЛ*.xlsx"), None)
    if source is None:
        pytest.skip("Requires the supplied completion workbook")
    target = tmp_path / "changed.xlsx"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as output:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                tree = ET.fromstring(data)
                cell = tree.find(f".//s:c[@r='{address}']", NS)
                if error:
                    cell.set("t", "e")
                content = cell.find("s:v", NS)
                if content is None:
                    content = cell.find("s:is/s:t", NS)
                content.text = str(value)
                data = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
            output.writestr(item, data)
    return target


def test_changed_leaf_fails_subtotal_reconciliation(tmp_path):
    path = changed_workbook(tmp_path, "J36", "1.01")
    with pytest.raises(ImportValidationError, match="не сходится"):
        parse_report(path)


def test_inconsistent_days_fail_import(tmp_path):
    source = next((ROOT / "data" / "input").glob("*КОМПЛ*.xlsx"), None)
    if source is None:
        pytest.skip("Requires completion workbook")
    report = parse_report(source)
    future = next(node for node in report.leaves if node.days_until is not None and node.days_until > 0)
    path = changed_workbook(tmp_path, f"H{future.row}", str(future.days_until + 1))
    with pytest.raises(ImportValidationError, match="дата и число дней"):
        parse_report(path)


def test_real_excel_error_is_not_treated_as_blank(tmp_path):
    path = changed_workbook(tmp_path, "J36", "#VALUE!", error=True)
    with pytest.raises(ImportValidationError, match="ошибка Excel"):
        parse_report(path)


def test_future_created_document_is_rejected(tmp_path):
    path = changed_workbook(tmp_path, "E23", "09.07.2026")
    with pytest.raises(ImportValidationError, match="дата возникновения позже"):
        parse_report(path)
