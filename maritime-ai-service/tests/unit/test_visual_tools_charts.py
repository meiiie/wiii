class TestChartVisual:
    """Test chart visual generation."""

    def test_chart_accepts_row_data_shape(self):
        from app.engine.tools.visual_tools import _build_chart_html

        spec = {
            "type": "bar",
            "data": [
                {"label": "Feeder", "value": 15},
                {"label": "Panamax", "value": 20},
                {"label": "ULCV", "value": 18},
            ],
            "caption": "Toc do khai thac trung binh.",
        }
        html = _build_chart_html(spec, "Container speed")
        assert "No chart data provided" not in html
        assert "Feeder" in html
        assert "Panamax" in html
        assert "ULCV" in html
        assert "Toc do khai thac trung binh." in html


class TestChartVisual:
    """Test chart (SVG bar/line) visual generation."""

    def test_basic_bar_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        spec = {
            "labels": ["Q1", "Q2", "Q3"],
            "datasets": [{"label": "Revenue", "data": [100, 200, 150]}],
        }
        html = _build_chart_html(spec, "Revenue Chart")
        assert "<!DOCTYPE html>" in html
        assert "Revenue" in html
        assert "Q1" in html
        assert "<svg" in html
        assert "chart-legend" in html

    def test_line_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        spec = {
            "chart_type": "line",
            "labels": ["Jan", "Feb"],
            "datasets": [{"label": "Growth", "data": [10, 20]}],
        }
        html = _build_chart_html(spec, "Growth")
        assert "<path" in html  # line path
        assert "<circle" in html  # data points

    def test_multi_dataset_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        spec = {
            "labels": ["A", "B"],
            "datasets": [
                {"label": "Series 1", "data": [10, 20]},
                {"label": "Series 2", "data": [15, 25]},
            ],
        }
        html = _build_chart_html(spec, "Multi")
        assert "Series 1" in html
        assert "Series 2" in html

    def test_empty_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        html = _build_chart_html({}, "Empty")
        assert "No chart data" in html
