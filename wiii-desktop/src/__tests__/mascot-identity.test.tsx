import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WiiiMark } from "@/components/common/WiiiMark";
import { WiiiMascot } from "@/components/common/WiiiMascot";

describe("Wiii Neko Peek identity", () => {
  it("uses the approved inline Neko Peek vector for compact product marks", () => {
    render(<WiiiMark title="Wiii Workbench" size={24} />);

    const mark = screen.getByRole("img", { name: "Wiii Workbench" });
    expect(mark.tagName.toLowerCase()).toBe("svg");
    expect(mark.getAttribute("viewBox")).toBe("0 0 1024 1024");
    expect(mark.getAttribute("width")).toBe("24");
    expect(mark.getAttribute("draggable")).toBe("false");
  });

  it("uses the transparent full-body asset on generous brand surfaces", () => {
    render(<WiiiMascot alt="Mascot Wiii" size={108} />);

    const mascot = screen.getByAltText("Mascot Wiii");
    expect(mascot.getAttribute("src")).toBe("/wiii-mascot-full.png");
    expect(mascot.getAttribute("height")).toBe("108");
  });

  it("uses the mascot in splash and no longer references the rejected SVG mark", async () => {
    const splash = await import("../../public/splashscreen.html?raw");
    const index = await import("../../index.html?raw");

    expect(splash.default).toContain("/wiii-mascot-full.png");
    expect(index.default).not.toContain("wiii-workbench-mark.svg");
    expect(index.default).toContain("/icon-192.png?v=6");
  });

  it("lets the Rust shell own the single tray icon", async () => {
    const configModule = await import("../../src-tauri/tauri.conf.json?raw");
    const config = JSON.parse(configModule.default);

    expect(config.app).not.toHaveProperty("trayIcon");
  });
});
