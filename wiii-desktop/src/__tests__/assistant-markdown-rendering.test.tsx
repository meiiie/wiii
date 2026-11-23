import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("MarkdownRenderer assistant cleanup", () => {
  it.each([
    ["GFM", ""],
    ["HTML", "\n\n<span>Ghi chú</span>"],
    ["math", "\n\n$x$"],
  ])("keeps %s tables semantic inside a keyboard-accessible viewport", async (_route, suffix) => {
    const { MarkdownRenderer } = await import("@/components/common/MarkdownRenderer");
    const content = [
      "| Lô | Cảng | Sức chứa | Khối lượng | Giờ mở | Đề xuất | Hạn dỡ | Kết luận |",
      "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
      "| **GAMMA** | EAST | 30 | 35 | 08:00–15:00 | 14:30→15:30 | 14:00 | Vượt sức chứa |",
    ].join("\n");

    render(<MarkdownRenderer content={content + suffix} />);

    const viewport = await screen.findByRole("region", { name: "Bảng" });
    const table = within(viewport).getByRole("table");
    expect(viewport.tabIndex).toBe(0);
    expect(within(table).getAllByRole("columnheader")).toHaveLength(8);
    expect(within(table).getAllByRole("cell")).toHaveLength(8);
    expect(within(table).getByRole("cell", { name: "GAMMA" })).toBeTruthy();
    expect(within(table).getByRole("cell", { name: "14:00" })).toBeTruthy();
    expect((within(table).getByRole("columnheader", { name: "Sức chứa" }) as HTMLElement).style.textAlign).toBe("right");
  });

  it("renders dense assistant table and quotes as structured markdown", async () => {
    const { MarkdownRenderer } = await import("@/components/common/MarkdownRenderer");
    const content = [
      "--- 🔍 So sánh nhanh: | Tiêu chí | Annex I | Annex VI |---------|----------|---------| | Ô nhiễm | Dầu ra biển | Khí thải ra không khí | Ghi chép | Oil Record Book | FONAR, EIAPP | --- 💡 Mẹo nhớ: đọc theo từng cột.",
      "Cậu chỉ cần nói: > “Mình thấy nút Khóa học” hoặc > “Mình không thấy gì cả”",
    ].join("\n\n");

    render(<MarkdownRenderer content={content} />);

    const table = await screen.findByRole("table");
    expect(within(table).getByText("Tiêu chí")).toBeTruthy();
    expect(within(table).getByText("Annex I")).toBeTruthy();
    expect(within(table).getByText("Khí thải ra không khí")).toBeTruthy();
    expect(screen.getByText("💡 Mẹo nhớ: đọc theo từng cột.")).toBeTruthy();
    expect(screen.getByText("“Mình thấy nút Khóa học”")).toBeTruthy();
    expect(screen.getByText("“Mình không thấy gì cả”")).toBeTruthy();
  });
});
