"""Regression coverage for the integrated evidence-first workspace."""

from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
APP = ROOT / "src/ui/audit_workspace.py"


def run_app(monkeypatch) -> AppTest:
    monkeypatch.chdir(ROOT)
    return AppTest.from_file(str(APP)).run(timeout=30)


def test_guided_demo_uses_live_descriptive_service(monkeypatch):
    app = run_app(monkeypatch)

    assert not app.exception
    assert app.radio[0].value == "Guided demo"
    assert not app.text_area
    assert [m.value for m in app.metric if m.label == "Records"] == ["1,200"]
    assert [m.value for m in app.metric if m.label == "Attributes assessed"] == ["1"]
    assert [m.value for m in app.metric if m.label == "Representation flags"] == ["0"]
    assert [m.value for m in app.metric if m.label == "Identifier signals"]
    assert {tab.label for tab in app.tabs} == {
        "Overview", "Cohort evidence", "Identifier screening", "Data quality", "Data preview"
    }
    assert app.multiselect[0].value == ["sex"]
    assert not any("Implement Changes" in button.label for button in app.button)
    preview = next(button for button in app.button if button.label == "Preview supported changes")
    assert preview.disabled

    page_text = " ".join(item.value for item in app.markdown)
    assert "Live guided demo" in page_text
    assert "No rule-based review flags" in page_text
    assert "Automatic mitigation is disabled" in page_text
    assert "screening result, not privacy clearance" in page_text
    assert "fixed v1 contract fixture" not in page_text
    assert "FAIR" not in page_text


def test_large_reference_gap_remains_descriptive(monkeypatch):
    app = run_app(monkeypatch)
    app.checkbox[0].check().run(timeout=30)

    assert not app.exception
    assert [m.value for m in app.metric if m.label == "Representation flags"] == ["0"]
    page_text = " ".join(item.value for item in app.markdown)
    assert "does not apply a universal" in page_text


def test_empty_demographic_selection_is_insufficient_not_fair(monkeypatch):
    app = run_app(monkeypatch)
    app.multiselect[0].set_value([]).run(timeout=30)

    assert not app.exception
    assert [m.value for m in app.metric if m.label == "Attributes assessed"] == ["0"]
    assert any("insufficient" in info.value.lower() for info in app.info)
    page_text = " ".join(item.value for item in app.markdown)
    assert "Representation status: Fair" not in page_text
    assert "dataset is fair" not in page_text.lower()


def test_upload_mode_waits_for_a_file(monkeypatch):
    app = run_app(monkeypatch)
    app.radio[0].set_value("Upload CSV").run(timeout=30)

    assert not app.exception
    assert not [m for m in app.metric if m.label == "Review flags"]
    assert any("assign column roles" in info.value for info in app.info)
