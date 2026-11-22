import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectDialog, projectDialogPrimaryTitle } from "@/neko-chill/components/ProjectDialog";
import {
  BROWSER_FOLDER_PICKER_UNAVAILABLE_VI,
  canChooseWorkspaceFolder,
  chooseWorkspaceFolder,
} from "@/neko-chill/workspace";

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

  it("disables the single empty-folder action with a local title in browser preview", async () => {
    const onCancel = vi.fn();
    const onSave = vi.fn(async () => {});
    render(<ProjectDialog project={null} onCancel={onCancel} onSave={onSave} />);

    expect(screen.getByTestId("browser-folder-picker-hint").textContent).toMatch(
      /trình duyệt|desktop Wiii/i,
    );

    const empty = screen.getByTestId("project-dialog-empty-folder");
    expect(screen.queryByTestId("project-dialog-add-folder")).toBeNull();
    expect((empty as HTMLButtonElement).disabled).toBe(true);
    expect(empty.getAttribute("title")).toBe(BROWSER_FOLDER_PICKER_UNAVAILABLE_VI);
    expect(empty.getAttribute("aria-disabled")).toBe("true");

    await act(async () => {
      fireEvent.click(empty);
    });

    expect(chooseWorkspaceFolder).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("offers one native folder action, switching to add only after a root is selected", async () => {
    vi.mocked(canChooseWorkspaceFolder).mockReturnValue(true);
    vi.mocked(chooseWorkspaceFolder).mockResolvedValue({
      name: "demo",
      path: "/tmp/demo",
    });
    render(<ProjectDialog project={null} onCancel={vi.fn()} onSave={vi.fn(async () => {})} />);

    expect(screen.queryByTestId("browser-folder-picker-hint")).toBeNull();
    expect(screen.queryByTestId("native-folder-picker-hint")).toBeNull();
    expect(screen.queryByTestId("project-dialog-add-folder")).toBeNull();
    expect(screen.getByTestId("project-dialog-empty-folder").getAttribute("title")).toBeNull();

    await act(async () => {
      fireEvent.click(screen.getByTestId("project-dialog-empty-folder"));
    });

    expect(chooseWorkspaceFolder).toHaveBeenCalledOnce();
    expect(screen.getByText("demo")).toBeTruthy();
    expect(screen.queryByTestId("project-dialog-empty-folder")).toBeNull();
    expect(screen.getByRole("button", { name: "Thêm thư mục" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Gỡ thư mục demo" }));
    expect(screen.queryByTestId("project-dialog-add-folder")).toBeNull();
    expect(screen.getByTestId("project-dialog-empty-folder")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});


describe("projectDialogPrimaryTitle", () => {
  it("explains missing name and folder together", () => {
    expect(projectDialogPrimaryTitle({
      mode: "create",
      saving: false,
      hasName: false,
      hasRoots: false,
    })).toBe("Hãy đặt tên dự án và thêm ít nhất một thư mục nguồn.");
  });

  it("explains missing folder after name is set", () => {
    expect(projectDialogPrimaryTitle({
      mode: "create",
      saving: false,
      hasName: true,
      hasRoots: false,
    })).toBe("Dự án cần ít nhất một thư mục nguồn.");
  });

  it("returns the enabled create label when ready", () => {
    expect(projectDialogPrimaryTitle({
      mode: "create",
      saving: false,
      hasName: true,
      hasRoots: true,
    })).toBe("Tạo dự án");
  });
});

describe("ProjectDialog primary title wiring", () => {
  it("puts the missing-folder reason on the disabled create button", () => {
    render(<ProjectDialog project={null} onCancel={vi.fn()} onSave={vi.fn(async () => {})} />);
    const primary = screen.getByTestId("project-dialog-primary");
    expect((primary as HTMLButtonElement).disabled).toBe(true);
    expect(primary.getAttribute("title")).toBe(
      "Hãy đặt tên dự án và thêm ít nhất một thư mục nguồn.",
    );
    fireEvent.change(screen.getByPlaceholderText(/Ví dụ/i), { target: { value: "Demo" } });
    expect(primary.getAttribute("title")).toBe("Dự án cần ít nhất một thư mục nguồn.");
  });
});
