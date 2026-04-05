import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { ThinkingBlock } from "@/components/chat/ThinkingBlock";

vi.mock("@/components/common/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}));

function countOccurrences(haystack: string, needle: string) {
  return haystack.split(needle).length - 1;
}

describe("ThinkingBlock dedup", () => {
  it("does not repeat the same long summary in expanded header and body", () => {
    const duplicatedLine =
      "Ban muon minh tao mot bieu do bang Python, mot y tuong rat thu vi day.";

    const { container } = render(
      <ThinkingBlock
        label="Bat nhip"
        summary={duplicatedLine}
        content={`${duplicatedLine}\n\nMinh se chon cach trinh bay gon va de nhin hon.`}
        autoExpand
        thinkingLevel="detailed"
      />,
    );

    const bodyText = container.textContent || "";
    expect(countOccurrences(bodyText, duplicatedLine)).toBe(0);
    expect(container.querySelector(".thinking-block__content-note")).toBeNull();
  });

  it("keeps collapsed headline without duplicating the preview line", () => {
    const duplicatedLine =
      "Minh dang nhin vao yeu cau ve bieu do bang Python cua ban.";

    const { container } = render(
      <ThinkingBlock
        summary={duplicatedLine}
        content={`${duplicatedLine}\n\nMinh se luu file PNG de gui lai cho ban.`}
        thinkingLevel="balanced"
      />,
    );

    const bodyText = container.textContent || "";
    expect(countOccurrences(bodyText, duplicatedLine)).toBe(1);
  });

  it("drops a leading paragraph when it semantically duplicates the summary", () => {
    const leadingParagraph =
      "Minh dang nhin vao yeu cau ve bieu do bang Python cua ban.";

    const { container } = render(
      <ThinkingBlock
        summary={leadingParagraph}
        content={`${leadingParagraph}\n\nMinh se chuyen sang buoc thuc thi de tao file PNG cho ban.`}
        autoExpand
        thinkingLevel="detailed"
      />,
    );

    const bodyText = container.textContent || "";
    expect(countOccurrences(bodyText, leadingParagraph)).toBe(0);
    expect(bodyText).toContain("Minh se chuyen sang buoc thuc thi de tao file PNG cho ban.");
  });

  it("uses streamed body text for the collapsed preview instead of summary-only metadata", () => {
    const conciseSummary = "Minh dang chot huong tao file PNG cho ban.";
    const longParagraph =
      "Du lieu da duoc xu ly xong xuoi, minh dang can nhin lai cach bien nhung con so kho khan thanh mot hinh anh de mo ra la hieu ngay.";

    const { container } = render(
      <ThinkingBlock
        label="Ban giao"
        summary={conciseSummary}
        content={`${longParagraph}\n\nMinh se gui lai artifact ngay sau buoc nay.`}
        thinkingLevel="balanced"
      />,
    );

    const bodyText = container.textContent || "";
    expect(bodyText).toContain(longParagraph);
    expect(bodyText).not.toContain(conciseSummary);
  });
});
