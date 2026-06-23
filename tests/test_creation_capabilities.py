from __future__ import annotations

import json
from pathlib import Path

from yantra.capabilities.connector import AtulyaTantraConnector
from yantra.capabilities.output_classifier import OutputTypeClassifier


def test_output_classifier_detects_formats():
    classifier = OutputTypeClassifier()
    assert classifier.detect("make a YouTube video").format == "video"
    assert classifier.detect("create an Excel spreadsheet").format == "xlsx"
    assert classifier.detect("write ordinary notes").format == "markdown"


def test_connector_creates_standard_library_outputs(tmp_path: Path):
    connector = AtulyaTantraConnector(tmp_path)

    markdown = connector.create("Quarterly report. Summarize progress.", "markdown")
    image = connector.create("Launch infographic", "svg")
    video = connector.create("Explain Atulya in three scenes.", "video", duration_minutes=1)

    assert markdown.ok and Path(markdown.path).read_text(encoding="utf-8").startswith("# ")
    assert image.ok and "<svg" in Path(image.path).read_text(encoding="utf-8")
    assert video.ok and len(json.loads(Path(video.path).read_text(encoding="utf-8"))["scenes"]) == 3
