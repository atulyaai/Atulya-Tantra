"""Safe OCR label matching and click confirmation tests."""
from __future__ import annotations

import asyncio

import pytest

from atulya import kriya, sharir
from atulya.mastishk import assess, describe_action


def _ocr(words, lefts, *, lines=None, confidence=None):
    count = len(words)
    return {
        "text": words,
        "left": lefts,
        "top": [20] * count,
        "width": [40] * count,
        "height": [12] * count,
        "conf": confidence or [90] * count,
        "block_num": [1] * count,
        "par_num": [1] * count,
        "line_num": lines or [1] * count,
    }


def test_ocr_match_uses_exact_contiguous_label_and_combines_box():
    data = _ocr(["Open", "File", "Save"], [10, 55, 130])
    assert sharir._find_ocr_box(data, "Open File") == (52, 26)


def test_ocr_match_refuses_missing_or_ambiguous_labels():
    with pytest.raises(sharir.Refused, match="couldn't find"):
        sharir._find_ocr_box(_ocr(["Cancel"], [10]), "Save")
    with pytest.raises(sharir.Refused, match="2 matches"):
        sharir._find_ocr_box(_ocr(["Save", "Save"], [10, 100], lines=[1, 2]), "Save")


def test_click_text_scales_ocr_location_to_screen_coordinates(monkeypatch):
    data = _ocr(["Save"], [10])
    clicks = []

    class Gui:
        def size(self):
            return 200, 200

        def click(self, x, y):
            clicks.append((x, y))

    monkeypatch.setattr(sharir, "require", lambda _permission: None)
    monkeypatch.setattr(sharir, "screenshot", lambda: "screen.png")
    monkeypatch.setattr(sharir, "_read_ocr_data", lambda _path: (data, 100, 100))
    monkeypatch.setattr(sharir, "get_gui", lambda: Gui())
    assert "Clicked the text" in sharir.click_text("Save")
    assert clicks == [(60, 52)]


def test_screen_text_click_requires_confirmation():
    decision = assess("screen", {"action": "click_text", "text": "Save"})
    assert decision.needs_confirmation
    assert describe_action("screen", {"action": "click_text", "text": "Save"}) == "click the Save text on your screen"



def test_screen_tool_dispatches_text_click_to_computer_layer(monkeypatch):
    seen = {}

    async def dispatch(event, arguments, function, *args):
        seen["event"] = event
        seen["arguments"] = arguments
        return function(*args)

    monkeypatch.setattr(kriya, "_on_computer", dispatch)
    monkeypatch.setattr(sharir, "click_text", lambda text: f"clicked:{text}")
    assert asyncio.run(kriya.screen("click_text", text="Save")) == "clicked:Save"
    assert seen == {"event": "screen.click_text", "arguments": {"text": "Save"}}
