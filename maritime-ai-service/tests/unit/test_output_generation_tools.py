"""Tests for deterministic output generation tools."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.engine.tools.output_generation_tools import (
    get_output_generation_tools,
    tool_generate_excel_file,
    tool_generate_html_file,
    tool_generate_word_document,
)


class TestOutputGenerationTools:
    def test_generate_html_file(self, tmp_path: Path):
        with patch(
            "app.engine.tools.output_generation_tools._get_generated_dir",
            return_value=tmp_path,
        ):
            result = tool_generate_html_file.invoke(
                {
                    "html_content": "<main><h1>Hello Wiii</h1></main>",
                    "title": "Landing Demo",
                }
            )

        payload = json.loads(result)
        file_path = Path(payload["file_path"])

        assert payload["format"] == "html"
        assert file_path.exists()
        assert file_path.suffix == ".html"
        html = file_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "Hello Wiii" in html

    def test_generate_excel_file(self, tmp_path: Path):
        rows_json = json.dumps(
            [
                {"name": "A", "price": 10},
                {"name": "B", "price": 12},
            ]
        )

        with patch(
            "app.engine.tools.output_generation_tools._get_generated_dir",
            return_value=tmp_path,
        ):
            result = tool_generate_excel_file.invoke(
                {
                    "rows_json": rows_json,
                    "title": "Price Table",
                    "sheet_name": "Prices",
                }
            )

        payload = json.loads(result)
        file_path = Path(payload["file_path"])

        assert payload["format"] == "xlsx"
        assert payload["row_count"] == 2
        assert payload["column_count"] == 2
        assert file_path.exists()
        assert file_path.suffix == ".xlsx"
        with zipfile.ZipFile(file_path) as archive:
            names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names

    def test_generate_word_document(self, tmp_path: Path):
        with patch(
            "app.engine.tools.output_generation_tools._get_generated_dir",
            return_value=tmp_path,
        ):
            result = tool_generate_word_document.invoke(
                {
                    "markdown_content": "# Heading\n\n- item 1\n- item 2\n\nParagraph text.",
                    "title": "Meeting Notes",
                }
            )

        payload = json.loads(result)
        file_path = Path(payload["file_path"])

        assert payload["format"] == "docx"
        assert file_path.exists()
        assert file_path.suffix == ".docx"
        with zipfile.ZipFile(file_path) as archive:
            names = set(archive.namelist())
            xml = archive.read("word/document.xml").decode("utf-8")
        assert "word/document.xml" in names
        assert "Meeting Notes" in xml

    def test_get_output_generation_tools(self):
        tool_names = {tool.name for tool in get_output_generation_tools()}
        assert tool_names == {
            "tool_generate_html_file",
            "tool_generate_excel_file",
            "tool_generate_word_document",
        }
