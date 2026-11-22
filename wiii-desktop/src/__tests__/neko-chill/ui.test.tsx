import { createRef, type FormEvent } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NekoButton, NekoIconButton, NekoInput, NekoListButton } from "@/neko-chill/components/ui";

describe("desktop native control contracts", () => {
  it("does not accidentally submit a surrounding form and preserves button focus refs", () => {
    const submit = vi.fn((event: FormEvent) => event.preventDefault());
    const ref = createRef<HTMLButtonElement>();
    render(<form onSubmit={submit}><NekoButton ref={ref}>Hủy</NekoButton><NekoButton type="submit">Lưu</NekoButton></form>);
    fireEvent.click(screen.getByRole("button", { name: "Hủy" }));
    expect(submit).not.toHaveBeenCalled();
    ref.current?.focus();
    expect(document.activeElement).toBe(ref.current);
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }));
    expect(submit).toHaveBeenCalledOnce();
  });

  it("keeps icon labels, input focus refs, and native disabled list behavior", () => {
    const choose = vi.fn();
    const inputRef = createRef<HTMLInputElement>();
    render(<>
      <NekoIconButton label="Xóa bộ lọc" onClick={() => inputRef.current?.focus()}>×</NekoIconButton>
      <label>Tìm model<NekoInput ref={inputRef} /></label>
      <NekoListButton role="option" aria-selected="false" disabled onClick={choose}>Chưa sẵn sàng</NekoListButton>
    </>);
    fireEvent.click(screen.getByRole("button", { name: "Xóa bộ lọc" }));
    expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Tìm model" }));
    fireEvent.click(screen.getByRole("option"));
    expect(choose).not.toHaveBeenCalled();
  });
});
