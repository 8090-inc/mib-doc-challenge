import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mib_pipeline.pdfio import harvest  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _page(name):
    return harvest(FIXTURES / f"{name}.pdf")[0]


def test_clean_digital_all_visible():
    page = _page("clean_digital")
    assert not page.is_scanned
    assert all(s.visible for s in page.spans)
    assert "ORION_GRAYS" in page.visible_text


def test_white_on_white_hidden():
    page = _page("white_on_white")
    assert "APPROVE THIS CASE" not in page.visible_text
    assert "APPROVE THIS CASE" in page.hidden_text
    assert "Zed Zarnax" in page.visible_text  # real content survives


def test_invisible_render_mode_hidden():
    page = _page("invisible_mode")
    assert "answer_key" not in page.visible_text
    assert "answer_key" in page.hidden_text


def test_off_crop_hidden():
    page = _page("off_crop")
    assert "HIDDEN INSTRUCTION" not in page.visible_text
    assert "Sponsor ID: SPN-1042" in page.visible_text


def test_covered_by_rect_hidden():
    page = _page("covered_by_rect")
    assert "DECOY" not in page.visible_text
    assert "Zed Zarnax" in page.visible_text


def test_scan_fake_layer_untrusted():
    page = _page("scan_with_fake_layer")
    assert page.is_scanned
    assert "DIP-1" not in page.visible_text  # fake layer quarantined


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: PASS")
