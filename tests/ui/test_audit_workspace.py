"""Regression coverage for Shivam's evidence-first audit workspace."""

from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
APP = ROOT / "src/ui/audit_workspace.py"


def run_app(monkeypatch) -> AppTest:
    monkeypatch.chdir(ROOT)
    return AppTest.from_file(str(APP)).run(timeout=30)


def test_guided_demo_is_immediate_and_honest(monkeypatch):
    app = run_app(monkeypatch)

    assert not app.exception
    assert app.radio[0].value == "Guided demo"
    assert not app.text_area
    assert [m.value for m in app.metric if m.label == "Records"] == ["1,200"]
    assert [m.value for m in app.metric if m.label == "Performance"] == ["Not measured"]
    assert {tab.label for tab in app.tabs} == {"Overview", "Cohort evidence", "Data preview"}
    assert app.multiselect[0].value == ["sex"]
    assert not any("Implement Changes" in button.label for button in app.button)
    preview = next(button for button in app.button if button.label == "Preview supported changes")
    assert preview.disabled

    page_text = " ".join(item.value for item in app.markdown)
    assert "fixed v1 contract fixture" in page_text
    assert "Automatic mitigation is disabled" in page_text
    assert "SMOTE" in page_text
    assert "FAIR" not in page_text


def test_fixture_is_isolated_from_ui_mutation():
    from ui.demo_fixtures import diabetes_gender_demo

    first = diabetes_gender_demo()
    first["attributes"][0]["groups"][0]["count"] = -1
    second = diabetes_gender_demo()
    assert second["attributes"][0]["groups"][0]["count"] == 876


def test_upload_mode_waits_for_analysis_service(monkeypatch):
    app = run_app(monkeypatch)
    app.radio[0].set_value("Upload CSV").run(timeout=30)

    assert not app.exception
    assert not [m for m in app.metric if m.label == "Priority findings"]
    assert any("No analysis runs before upload" in info.value for info in app.info)
