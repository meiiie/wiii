import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WiiiMark } from "@/components/common/WiiiMark";
import { BootSplash } from "@/workbench/WorkbenchBoot";
import { readFileSync } from "node:fs";

const logoStyles = readFileSync("src/components/common/wiii-logo.css", "utf8");

describe("Wiii inline Neko Peek mark", () => {
  it("is a static decorative native SVG by default at the existing default size", () => {
    const { container } = render(<WiiiMark />);
    const mark = container.querySelector("svg")!;

    expect(mark).toBeTruthy();
    expect(mark.getAttribute("viewBox")).toBe("0 0 1024 1024");
    expect(mark.getAttribute("width")).toBe("20");
    expect(mark.getAttribute("height")).toBe("20");
    expect(mark.getAttribute("aria-hidden")).toBe("true");
    expect(mark.getAttribute("focusable")).toBe("false");
    expect(mark.getAttribute("draggable")).toBe("false");
    expect(mark.getAttribute("data-state")).toBe("ready");
    expect(screen.queryByRole("img")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("preserves sizing, classes, data attributes and interaction props for existing hosts", () => {
    const onClick = vi.fn();
    render(<WiiiMark size={17} alt="Wiii" className="shrink-0" data-testid="host-mark" style={{ opacity: 0.75 }} onClick={onClick} />);
    const mark = screen.getByRole("img", { name: "Wiii" });

    expect(mark).toBe(screen.getByTestId("host-mark"));
    expect(mark.getAttribute("width")).toBe("17");
    expect(mark.getAttribute("height")).toBe("17");
    expect(mark.style.width).toBe("17px");
    expect(mark.style.height).toBe("17px");
    expect(mark.style.opacity).toBe("0.75");
    expect(mark.classList.contains("shrink-0")).toBe(true);
    expect(mark.getAttribute("aria-hidden")).toBeNull();

    fireEvent.click(mark);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("uses the title as the accessible name when there is no alt label", () => {
    render(<WiiiMark title="Wiii Workbench" size={24} />);
    const mark = screen.getByRole("img", { name: "Wiii Workbench" });
    const title = mark.querySelector("title")!;

    expect(title.textContent).toBe("Wiii Workbench");
    expect(mark.getAttribute("aria-labelledby")).toBe(title.id);
    expect(mark.getAttribute("aria-hidden")).toBeNull();
    expect(mark.getAttribute("width")).toBe("24");
  });

  it("keeps an alt label as the accessible name and preserves a separate tooltip", () => {
    render(<WiiiMark alt="Wiii" title="Không gian Wiii" size={32} />);
    const mark = screen.getByRole("img", { name: "Wiii" });

    expect(mark.querySelector("title")?.textContent).toBe("Không gian Wiii");
    expect(mark.getAttribute("aria-label")).toBe("Wiii");
    expect(mark.getAttribute("aria-labelledby")).toBeNull();
  });

  it("keeps every title and gradient reference local to its instance and stable on rerender", () => {
    const view = render(<><WiiiMark title="Wiii một" /><WiiiMark title="Wiii hai" /></>);
    const marks = screen.getAllByRole("img");
    const allIds = Array.from(view.container.querySelectorAll("[id]"), (node) => node.id);

    expect(new Set(allIds).size).toBe(allIds.length);
    for (const mark of marks) {
      const localIds = new Set(Array.from(mark.querySelectorAll("[id]"), (node) => node.id));
      expect(localIds.has(mark.getAttribute("aria-labelledby")!)).toBe(true);
      const fills = Array.from(mark.querySelectorAll("[fill]"), (node) => node.getAttribute("fill")!);
      const references = fills.filter((fill) => fill.startsWith("url(#"));
      expect(references.length).toBeGreaterThan(0);
      for (const fill of references) {
        expect(localIds.has(fill.slice(5, -1))).toBe(true);
      }
    }

    view.rerender(<><WiiiMark title="Wiii một" size={32} /><WiiiMark title="Wiii hai" size={48} /></>);
    expect(Array.from(view.container.querySelectorAll("[id]"), (node) => node.id)).toEqual(allIds);
  });

  it("contains native vector paths without scripts, embedded bitmaps, external resources or foreign HTML", () => {
    const { container } = render(<WiiiMark alt="Wiii" />);
    const mark = screen.getByRole("img", { name: "Wiii" });

    expect(mark.querySelector("path")).toBeTruthy();
    expect(mark.querySelector("linearGradient")).toBeTruthy();
    expect(container.querySelector("script, image, foreignObject, iframe, use, text")).toBeNull();
    expect(mark.querySelector("[href], [src]")).toBeNull();
    expect(mark.querySelector(".wiii-eye-left")).toBeTruthy();
    expect(mark.querySelector(".wiii-eye-right")).toBeTruthy();
    expect(mark.querySelector(".wiii-tail-front")).toBeTruthy();
  });

  it("limits hover to one brief cycle and disables motion for reduced-motion users", () => {
    expect(logoStyles).toContain("@media (hover: hover) and (pointer: fine)");
    expect(logoStyles).toContain('.wiii-logo[data-state="ready"]:hover');
    expect(logoStyles).toContain("animation: wiii-logo-blink 800ms ease-in-out 1;");
    expect(logoStyles).not.toContain("infinite");
    expect(logoStyles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(logoStyles).toContain("animation: none !important;");
    expect(logoStyles).toContain("transform: none !important;");
    const defaultStyle = logoStyles.match(/\.wiii-logo \{([^}]+)\}/)?.[1];
    expect(defaultStyle).toBeDefined();
    expect(defaultStyle).not.toContain("animation:");
  });

  it("keeps the boot mark static while retaining the visible loading label", () => {
    render(<BootSplash label="Wiii đang mở..." />);
    const mark = screen.getByRole("img", { name: "Wiii" });

    expect(screen.getByText("Wiii đang mở...")).toBeTruthy();
    expect(mark.classList.contains("animate-pulse")).toBe(false);
    expect(mark.getAttribute("data-state")).toBe("ready");
    expect(mark.getAttribute("width")).toBe("48");
  });
});
