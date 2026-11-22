import { type ComponentProps, type ComponentType } from "react";
import { render } from "@testing-library/react";
import ReactMarkdown from "react-markdown";
import { describe, expect, it } from "vitest";
import { createMarkdownRenderComponents } from "@/components/common/markdown-render-components";

const components = createMarkdownRenderComponents();

describe("ordered-list marker gutter", () => {
  it.each([
    [9, 1, "1ch"],
    [12, 1, "2ch"],
    [105, 1, "3ch"],
    [5, 98, "3ch"],
    [2, 99999999, "9ch"],
  ])("sizes %i direct items starting at %i", (count, start, width) => {
    const content = Array.from({ length: count }, (_, index) => `${start + index}. Item`).join("\n");
    const { container } = render(<ReactMarkdown components={components}>{content}</ReactMarkdown>);
    const list = container.querySelector("ol")!;
    expect(list.style.getPropertyValue("--ol-marker-width")).toBe(width);
    expect(list.querySelectorAll(":scope > li")).toHaveLength(count);
    expect(list.start).toBe(start);
  });

  it("counts only direct items and sizes nested lists independently", () => {
    const content = `1. Parent\n${Array.from({ length: 12 }, (_, index) => `   ${index + 1}. Child`).join("\n")}\n2. Parent`;
    const { container } = render(<ReactMarkdown components={components}>{content}</ReactMarkdown>);
    const lists = container.querySelectorAll("ol");
    expect(lists).toHaveLength(2);
    expect(lists[0].style.getPropertyValue("--ol-marker-width")).toBe("1ch");
    expect(lists[1].style.getPropertyValue("--ol-marker-width")).toBe("2ch");
  });

  const OrderedList = components.ol as ComponentType<ComponentProps<"ol">>;

  it.each([
    [-100, "4ch"],
    [-1, "2ch"],
    [0, "1ch"],
    [Number.MAX_SAFE_INTEGER, "16ch"],
    [Number.NaN, "1ch"],
    [Number.POSITIVE_INFINITY, "1ch"],
    [Number.MAX_VALUE, "1ch"],
  ])("handles start=%s without invalid CSS", (start, width) => {
    const { container } = render(<OrderedList start={start}><li>First</li><li>Second</li></OrderedList>);
    const list = container.querySelector("ol")!;
    expect(list.style.getPropertyValue("--ol-marker-width")).toBe(width);
    expect(list.getAttribute("start")).toBe(String(Number.isSafeInteger(start) ? start : 1));
  });

  it("handles an empty list and preserves other list attributes and styles", () => {
    const { container } = render(<OrderedList aria-label="Empty" style={{ color: "red" }} />);
    const list = container.querySelector("ol")!;
    expect(list.style.getPropertyValue("--ol-marker-width")).toBe("1ch");
    expect(list.style.color).toBe("red");
    expect(list.getAttribute("aria-label")).toBe("Empty");
    expect(list.hasAttribute("start")).toBe(false);
    expect(list.children).toHaveLength(0);
  });
});
