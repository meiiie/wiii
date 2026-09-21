import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectDialog, projectDialogPrimaryTitle } from "@/neko-chill/components/ProjectDialog";
import {
  BROWSER_FOLDER_PICKER_UNAVAILABLE_VI,
  NATIVE_FOLDER_PICKER_SELECT_HINT_VI,
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

  it("disables folder CTAs with a local title in browser preview", async () => {
    const onCancel = vi.fn();
    const onSave = vi.fn(async () => {});
    render(<ProjectDialog project={null} onCancel={onCancel} onSave={onSave} />);

    expect(screen.getByTestId("browser-folder-picker-hint").textContent).toMatch(
      /trình duyệt|desktop Wiii/i,
    );

    const add = screen.getByTestId("project-dialog-add-folder");
    const empty = screen.getByTestId("project-dialog-empty-folder");
    expect((add as HTMLButtonElement).disabled).toBe(true);
    expect((empty as HTMLButtonElement).disabled).toBe(true);
    expect(add.getAttribute("title")).toBe(BROWSER_FOLDER_PICKER_UNAVAILABLE_VI);
    expect(empty.getAttribute("title")).toBe(BROWSER_FOLDER_PICKER_UNAVAILABLE_VI);
    expect(add.getAttribute("aria-disabled")).toBe("true");

    await act(async () => {
      fireEvent.click(add);
      fireEvent.click(empty);
    });

    expect(chooseWorkspaceFolder).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("still opens the native picker when the desktop shell is available", async () => {
    vi.mocked(canChooseWorkspaceFolder).mockReturnValue(true);
    vi.mocked(chooseWorkspaceFolder).mockResolvedValue({
      name: "demo",
      path: "/tmp/demo",
    });
    render(<ProjectDialog project={null} onCancel={vi.fn()} onSave={vi.fn(async () => {})} />);

    expect(screen.queryByTestId("browser-folder-picker-hint")).toBeNull();
    expect(screen.getByTestId("native-folder-picker-hint").textContent).toBe(
      NATIVE_FOLDER_PICKER_SELECT_HINT_VI,
    );
    expect(screen.getByTestId("project-dialog-add-folder").getAttribute("title")).toBe(
      NATIVE_FOLDER_PICKER_SELECT_HINT_VI,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Thêm thư mục/i }));
    });

    expect(chooseWorkspaceFolder).toHaveBeenCalledOnce();
    expect(screen.getByText("demo")).toBeTruthy();
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
    })).toBe("Hãy đặt tên Project và thêm ít nhất một thư mục nguồn.");
  });

  it("explains missing folder after name is set", () => {
    expect(projectDialogPrimaryTitle({
      mode: "create",
      saving: false,
      hasName: true,
      hasRoots: false,
    })).toBe("Project cần ít nhất một thư mục nguồn.");
  });

  it("returns the enabled create label when ready", () => {
    expect(projectDialogPrimaryTitle({
      mode: "create",
      saving: false,
      hasName: true,
      hasRoots: true,
    })).toBe("Tạo Project");
  });
});

describe("ProjectDialog primary title wiring", () => {
  it("puts the missing-folder reason on the disabled create button", () => {
    render(<ProjectDialog project={null} onCancel={vi.fn()} onSave={vi.fn(async () => {})} />);
    const primary = screen.getByTestId("project-dialog-primary");
    expect((primary as HTMLButtonElement).disabled).toBe(true);
    expect(primary.getAttribute("title")).toBe(
      "Hãy đặt tên Project và thêm ít nhất một thư mục nguồn.",
    );
    fireEvent.change(screen.getByPlaceholderText(/Ví dụ/i), { target: { value: "Demo" } });
    expect(primary.getAttribute("title")).toBe("Project cần ít nhất một thư mục nguồn.");
  });
});
