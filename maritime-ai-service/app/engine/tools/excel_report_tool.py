"""
Excel Report Tool — Sprint 148: "Săn Hàng"

Generates product comparison Excel reports using XlsxWriter.
Output: ~/.wiii/workspace/reports/product_report_{timestamp}.xlsx

Pattern: follows filesystem_tools.py sandbox pattern.
"""

import json
import logging
import os
import time
from pathlib import Path

from langchain_core.tools import tool

from app.engine.tools.registry import (
    ToolCategory,
    ToolAccess,
    get_tool_registry,
)

logger = logging.getLogger(__name__)


def _get_reports_dir() -> Path:
    """Get the reports directory, creating it if needed."""
    from app.core.config import get_settings
    settings = get_settings()
    workspace = Path(settings.workspace_root).expanduser()
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


@tool
def tool_generate_product_report(products_json: str, title: str = "Báo cáo so sánh sản phẩm") -> str:
    """Generate an Excel report comparing products across platforms.
    Creates a formatted .xlsx file with product data, pricing, and links.

    Args:
        products_json: JSON string of product list. Each item should have:
            platform, title, price, seller, rating, sold_count, delivery, location, link
        title: Report title (default: "Báo cáo so sánh sản phẩm")

    Returns:
        Path to the generated Excel file, or error message.
    """
    try:
        import xlsxwriter
    except ImportError:
        return json.dumps({"error": "xlsxwriter not installed. Run: pip install xlsxwriter"}, ensure_ascii=False)

    try:
        products = json.loads(products_json)
        if not isinstance(products, list):
            return json.dumps({"error": "products_json must be a JSON array"}, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {str(e)[:100]}"}, ensure_ascii=False)

    if not products:
        return json.dumps({"error": "No products to report"}, ensure_ascii=False)

    # Generate file path
    reports_dir = _get_reports_dir()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"product_report_{timestamp}.xlsx"
    filepath = reports_dir / filename

    try:
        workbook = xlsxwriter.Workbook(str(filepath))
        worksheet = workbook.add_worksheet("So sánh sản phẩm")

        # Formats
        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#FF8C00",
            "font_color": "#FFFFFF",
            "border": 1,
            "text_wrap": True,
            "valign": "vcenter",
            "align": "center",
        })
        price_fmt = workbook.add_format({
            "num_format": "#,##0 ₫",
            "border": 1,
        })
        cell_fmt = workbook.add_format({
            "border": 1,
            "text_wrap": True,
            "valign": "top",
        })
        link_fmt = workbook.add_format({
            "border": 1,
            "font_color": "#0563C1",
            "underline": True,
        })
        min_price_fmt = workbook.add_format({
            "num_format": "#,##0 ₫",
            "border": 1,
            "bg_color": "#C6EFCE",
            "font_color": "#006100",
            "bold": True,
        })
        max_price_fmt = workbook.add_format({
            "num_format": "#,##0 ₫",
            "border": 1,
            "bg_color": "#FFC7CE",
            "font_color": "#9C0006",
        })
        title_fmt = workbook.add_format({
            "bold": True,
            "font_size": 14,
        })

        # Title row
        worksheet.merge_range("A1:K1", title, title_fmt)
        worksheet.write("A2", f"Ngày tạo: {time.strftime('%d/%m/%Y %H:%M')}", workbook.add_format({"italic": True}))

        # Headers (row 3, 0-indexed = row 2 skipped for spacing)
        headers = ["STT", "Sàn", "Tên SP", "Giá (VNĐ)", "Người bán", "Đánh giá", "Lượt bán", "Vận chuyển", "Địa chỉ", "Link", "Mô tả"]
        col_widths = [5, 18, 45, 16, 25, 10, 12, 15, 20, 35, 35]
        for col, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.set_column(col, col, width)
            worksheet.write(3, col, header, header_fmt)

        # Extract numeric prices for sorting and highlighting
        prices = []
        for p in products:
            price_val = _extract_price(p.get("price", ""), p.get("extracted_price"))
            prices.append(price_val)

        # Sort products by price ascending (cheapest first), None/0 at end
        paired = list(zip(products, prices))
        paired.sort(key=lambda x: x[1] if x[1] and x[1] > 0 else float('inf'))
        products = [p for p, _ in paired]
        prices = [pr for _, pr in paired]

        valid_prices = [p for p in prices if p and p > 0]
        min_price = min(valid_prices) if valid_prices else None
        max_price = max(valid_prices) if valid_prices else None

        # Data rows
        for i, product in enumerate(products):
            row = 4 + i
            price_val = prices[i]

            # Select price format based on min/max
            p_fmt = price_fmt
            if price_val and min_price and price_val == min_price:
                p_fmt = min_price_fmt
            elif price_val and max_price and price_val == max_price:
                p_fmt = max_price_fmt

            worksheet.write(row, 0, i + 1, cell_fmt)
            worksheet.write(row, 1, product.get("platform", ""), cell_fmt)
            worksheet.write(row, 2, product.get("title", ""), cell_fmt)
            worksheet.write(row, 3, price_val or 0, p_fmt)
            worksheet.write(row, 4, product.get("seller", "") or product.get("source", ""), cell_fmt)
            worksheet.write(row, 5, product.get("rating", "") or "", cell_fmt)
            worksheet.write(row, 6, product.get("sold_count", "") or "", cell_fmt)
            worksheet.write(row, 7, product.get("delivery", ""), cell_fmt)
            worksheet.write(row, 8, product.get("location", ""), cell_fmt)

            link = product.get("link") or product.get("url", "")
            if link:
                worksheet.write_url(row, 9, link, link_fmt, "Xem SP")
            else:
                worksheet.write(row, 9, "", cell_fmt)

            # Description/specs column
            description = product.get("snippet", "") or product.get("description", "")
            worksheet.write(row, 10, description, cell_fmt)

        # Summary row
        summary_row = 4 + len(products) + 1
        summary_fmt = workbook.add_format({"bold": True, "border": 1, "bg_color": "#F2F2F2"})
        worksheet.write(summary_row, 0, "", summary_fmt)
        worksheet.write(summary_row, 1, "TỔNG KẾT", summary_fmt)
        worksheet.write(summary_row, 2, f"{len(products)} sản phẩm từ {len(set(p.get('platform', '') for p in products))} sàn", summary_fmt)
        if min_price:
            worksheet.write(summary_row, 3, min_price, min_price_fmt)
        worksheet.write(summary_row, 4, f"Giá thấp nhất: {_format_vnd(min_price)}" if min_price else "", summary_fmt)

        workbook.close()

        return json.dumps({
            "file_path": str(filepath),
            "filename": filename,
            "total_products": len(products),
            "platforms": list(set(p.get("platform", "") for p in products)),
            "min_price": min_price,
            "max_price": max_price,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("[EXCEL_REPORT] Generation failed: %s", e)
        return json.dumps({"error": f"Lỗi tạo báo cáo: {str(e)[:200]}"}, ensure_ascii=False)


def _extract_price(price_str, extracted_price=None) -> float:
    """Extract numeric price from various formats."""
    if extracted_price and isinstance(extracted_price, (int, float)):
        return float(extracted_price)
    if not price_str:
        return 0.0
    price_str = str(price_str)
    # Remove currency symbols and formatting
    import re
    cleaned = re.sub(r'[^\d.,]', '', price_str)
    # Vietnamese format: both . and , are thousands separators (VND has no decimals)
    cleaned = cleaned.replace('.', '').replace(',', '')
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _format_vnd(price: float) -> str:
    """Format price as Vietnamese Dong."""
    if not price:
        return "N/A"
    return f"{price:,.0f}₫".replace(",", ".")


# =============================================================================
# Registration
# =============================================================================

def init_excel_report_tool():
    """Register Excel report tool with the global registry."""
    registry = get_tool_registry()
    registry.register(tool_generate_product_report, ToolCategory.PRODUCT_SEARCH, ToolAccess.WRITE)
    logger.info("Excel report tool registered")
