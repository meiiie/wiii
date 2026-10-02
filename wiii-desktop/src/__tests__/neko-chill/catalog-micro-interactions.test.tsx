import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChillCatalogPicker } from "@/neko-chill/components/ChillCatalogPicker";
const items = [{ id: "a", label: "Alpha" }, { id: "locked", label: "Unavailable", disabled: true }, { id: "b", label: "Beta" }, { id: "c", label: "Gamma" }];
function mount(value = "b") {
  const change = vi.fn(); const props = { items, value, onChange: change, ariaLabel: "Model" };
  const view = render(<><ChillCatalogPicker {...props} /><button>Outside</button></>);
  fireEvent.click(screen.getByRole("button", { name: "Model" }));
  return { ...view, change, props, input: screen.getByRole("combobox") };
}
function active() { return document.getElementById(screen.getByRole("combobox").getAttribute("aria-activedescendant")!); }
describe("catalog micro-interactions", () => {
  it("focuses search and highlights current selection, not the first item", () => {
    const { input } = mount(); expect(document.activeElement).toBe(input); expect(active()?.textContent).toBe("Beta");
    expect(screen.getByRole("option", { name: "Beta" }).getAttribute("aria-selected")).toBe("true");
  });
  it("Tab and Shift+Tab leave without changing model", () => {
    const { input, change } = mount(); fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Tab" }); expect(change).not.toHaveBeenCalled(); expect(screen.queryByRole("listbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Model" }));
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Tab", shiftKey: true }); expect(change).not.toHaveBeenCalled();
  });
  it("arrows skip unavailable options and Home/End explore without commit", () => {
    const { input, change } = mount("a"); fireEvent.keyDown(input, { key: "ArrowDown" }); expect(active()?.textContent).toBe("Beta");
    fireEvent.keyDown(input, { key: "End" }); expect(active()?.textContent).toBe("Gamma");
    fireEvent.keyDown(input, { key: "Home" }); expect(active()?.textContent).toBe("Alpha"); expect(change).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "ArrowUp" }); fireEvent.keyDown(input, { key: "Enter" }); expect(change).toHaveBeenCalledExactlyOnceWith("c");
  });
  it("Escape restores trigger; explicit selection reaches the owner", () => {
    const { input, change } = mount(); fireEvent.keyDown(input, { key: "Escape" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Model" }));
    fireEvent.click(screen.getByRole("button", { name: "Model" })); fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" }); expect(change).toHaveBeenCalledExactlyOnceWith("b");
  });
  it("closes immediately when a pending change blocks controls", () => {
    const { rerender, props } = mount(); rerender(<ChillCatalogPicker {...props} pending disabled />);
    expect(screen.queryByRole("listbox")).toBeNull(); expect((screen.getByRole("button", { name: "Model" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Model" }).getAttribute("aria-busy")).toBe("true");
  });
  it("empty search has no stale active descendant and can be cleared", () => {
    const { input } = mount(); fireEvent.change(input, { target: { value: "not-a-model" } });
    expect(input.getAttribute("aria-activedescendant")).toBeNull(); expect(screen.getByRole("status")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Xóa bộ lọc" })); expect(active()?.textContent).toBe("Beta"); expect(document.activeElement).toBe(input);
  });
  it("does not commit during IME composition", () => {
    const { input, change } = mount(); fireEvent.keyDown(input, { key: "ArrowDown" }); fireEvent.keyDown(input, { key: "Enter", keyCode: 229 });
    expect(change).not.toHaveBeenCalled(); expect(screen.getByRole("listbox")).toBeTruthy();
  });
  it("outside pointer dismisses without selecting", () => {
    const { change } = mount(); fireEvent.pointerDown(screen.getByRole("button", { name: "Outside" })); expect(screen.queryByRole("listbox")).toBeNull(); expect(change).not.toHaveBeenCalled();
  });
  it("keyboard order matches grouped visual order", () => {
    render(<ChillCatalogPicker ariaLabel="Grouped" value="a" onChange={vi.fn()} items={[{id:"a",label:"A",group:"One"},{id:"b",label:"B",group:"Two"},{id:"c",label:"C",group:"One"}]} />);
    fireEvent.click(screen.getByRole("button", { name:"Grouped" })); fireEvent.keyDown(screen.getByRole("combobox"), { key:"ArrowDown" }); expect(active()?.textContent).toBe("C");
  });
});
