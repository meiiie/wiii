import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectDialog } from "@/neko-chill/components/ProjectDialog";
import { canChooseWorkspaceFolder, chooseWorkspaceFolder } from "@/neko-chill/workspace";

vi.mock("@/neko-chill/workspace", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/neko-chill/workspace")>();
  return {
    ...actual,
    canChooseWorkspaceFolder: vi.fn(() => false),
    chooseWorkspaceFolder: vi.fn(async () => null),
    resolveWorkspaceFolder: vi.fn(async (path: string) => actual.workspaceFromPath(path)),
  };
});

describe("ProjectDialog browser folder-picker honesty", () => {
  beforeEach(() => {
    vi.mocked(canChooseWorkspaceFolder).mockReset().mockReturnValue(false);
    vi.mocked(chooseWorkspaceFolder).mockReset().mockResolvedValue(null);
  });

  it("shows a browser-preview hint and explains a silent picker no-op", async () => {
    const onCancel = vi.fn();
    const onSave = vi.fn(async () => {});
    render(<ProjectDialog project={null} onCancel={onCancel} onSave={onSave} />);

    expect(screen.getByTestId("browser-folder-picker-hint").textContent).toMatch(
      /trình duyệt|desktop Wiii/i,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Thêm thư mục/i }));
    });

    expect(chooseWorkspaceFolder).not.toHaveBeenCalled();
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/trình duyệt.*thư mục|desktop Wiii/i);
  });

  it("still opens the native picker when the desktop shell is available", async () => {
    vi.mocked(canChooseWorkspaceFolder).mockReturnValue(true);
    vi.mocked(chooseWorkspaceFolder).mockResolvedValue({
      name: "demo",
      path: "/tmp/demo",
    });
    render(<ProjectDialog project={null} onCancel={vi.fn()} onSave={vi.fn(async () => {})} />);

    expect(screen.queryByTestId("browser-folder-picker-hint")).toBeNull();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Thêm thư mục/i }));
    });

    expect(chooseWorkspaceFolder).toHaveBeenCalledOnce();
    expect(screen.getByText("demo")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
