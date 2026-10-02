import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  highlight: vi.fn(),
  openArtifact: vi.fn(),
  getPyodideRuntime: vi.fn(() => {
    throw new Error("Code rendering must not start Pyodide");
  }),
}));

vi.mock("@/components/common/ShikiMinimalHighlighter", () => ({
  ShikiMinimalHighlighter: (props: {
    children: string;
    language: string;
    showLineNumbers?: boolean;
  }) => {
    mocks.highlight(props);
    return (
      <pre data-testid="shiki-highlighter" data-line-numbers={String(props.showLineNumbers)}>
        <code>{props.children}</code>
      </pre>
    );
  },
}));

vi.mock("@/stores/ui-store", () => ({
  useUIStore: { getState: () => ({ openArtifact: mocks.openArtifact }) },
}));

vi.mock("@/lib/pyodide-runtime", () => ({
  getPyodideRuntime: mocks.getPyodideRuntime,
}));

import { CodeBlock } from "@/components/common/CodeBlock";

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((accept, decline) => {
    resolve = accept;
    reject = decline;
  });
  return { promise, resolve, reject };
}

function installClipboard(writeText?: (code: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: writeText ? { writeText } : undefined,
  });
}

async function clickCopy() {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Sao chép mã" }));
  });
}

const code = "print('Xin chào')\nprint('<b>mã</b>')";
const copyError = "Chưa sao chép được. Chọn mã và sao chép thủ công, hoặc thử lại.";
let originalClipboard: PropertyDescriptor | undefined;

beforeEach(() => {
  originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  if (originalClipboard) {
    Object.defineProperty(navigator, "clipboard", originalClipboard);
  } else {
    Reflect.deleteProperty(navigator, "clipboard");
  }
  expect(mocks.getPyodideRuntime).not.toHaveBeenCalled();
  expect(mocks.openArtifact).not.toHaveBeenCalled();
});

describe("CodeBlock copy interactions", () => {
  it("shows a visible Vietnamese recovery message when clipboard is unavailable and allows retry", async () => {
    installClipboard();
    render(<CodeBlock code={code} language="python" />);

    await clickCopy();

    const status = screen.getByRole("status");
    expect(status.textContent).toBe(copyError);
    expect(status.classList.contains("sr-only")).toBe(false);
    const retry = screen.getByRole("button", { name: "Sao chép mã" });
    expect(retry.getAttribute("aria-describedby")).toBe(status.id);
    expect((retry as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByText("Đã sao chép toàn bộ mã.")).toBeNull();

    const writeText = vi.fn().mockResolvedValue(undefined);
    installClipboard(writeText);
    await clickCopy();

    expect(writeText).toHaveBeenCalledExactlyOnceWith(code);
    expect(screen.getByRole("status").textContent).toBe("Đã sao chép toàn bộ mã.");
  });

  it("retains the raw code after clipboard rejection and retries the copy", async () => {
    const writeText = vi.fn()
      .mockRejectedValueOnce(new Error("Clipboard permission denied"))
      .mockResolvedValueOnce(undefined);
    installClipboard(writeText);
    render(<CodeBlock code={code} language="python" />);

    await clickCopy();

    expect(screen.getByRole("status").textContent).toBe(copyError);
    expect(screen.getByRole("region").textContent).toBe(code);
    expect(screen.queryByRole("button", { name: "Đã sao chép" })).toBeNull();

    await clickCopy();

    expect(writeText).toHaveBeenCalledTimes(2);
    expect(writeText).toHaveBeenNthCalledWith(1, code);
    expect(writeText).toHaveBeenNthCalledWith(2, code);
    expect(screen.getByRole("button", { name: "Đã sao chép" })).toBeTruthy();
  });

  it("waits for clipboard acknowledgement and dispatches repeated clicks only once", async () => {
    const pending = deferred();
    const writeText = vi.fn(() => pending.promise);
    installClipboard(writeText);
    render(<CodeBlock code={code} language="python" />);

    fireEvent.click(screen.getByRole("button", { name: "Sao chép mã" }));
    const copying = screen.getByRole("button", { name: "Đang sao chép" });
    fireEvent.click(copying);
    fireEvent.click(copying);

    expect(writeText).toHaveBeenCalledExactlyOnceWith(code);
    expect((copying as HTMLButtonElement).disabled).toBe(true);
    expect(copying.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByRole("status").textContent).toBe("Đang sao chép mã…");
    expect(screen.queryByRole("button", { name: "Đã sao chép" })).toBeNull();

    await act(async () => pending.resolve());

    expect(screen.getByRole("button", { name: "Đã sao chép" }).getAttribute("aria-busy")).toBe("false");
    expect(screen.getByRole("status").textContent).toBe("Đã sao chép toàn bộ mã.");
  });

  it.each(["resolve", "reject"] as const)(
    "ignores a stale clipboard %s after code changes while a newer copy is pending",
    async (outcome) => {
      const oldCopy = deferred();
      const newCopy = deferred();
      const nextCode = "print('Mã mới')\nprint('Giữ kết quả đúng phiên bản')";
      const writeText = vi.fn()
        .mockImplementationOnce(() => oldCopy.promise)
        .mockImplementationOnce(() => newCopy.promise);
      installClipboard(writeText);
      const view = render(<CodeBlock code={code} language="python" />);

      await clickCopy();
      view.rerender(<CodeBlock code={nextCode} language="python" />);
      expect(screen.queryByRole("status")).toBeNull();
      await clickCopy();

      await act(async () => {
        if (outcome === "resolve") oldCopy.resolve();
        else oldCopy.reject(new Error("Old clipboard request failed"));
      });

      expect(screen.getByRole("button", { name: "Đang sao chép" })).toBeTruthy();
      expect(screen.getByRole("status").textContent).toBe("Đang sao chép mã…");
      expect(screen.queryByText(copyError)).toBeNull();
      expect(screen.queryByRole("button", { name: "Đã sao chép" })).toBeNull();
      expect(writeText).toHaveBeenNthCalledWith(1, code);
      expect(writeText).toHaveBeenNthCalledWith(2, nextCode);

      await act(async () => newCopy.resolve());

      expect(screen.getByRole("status").textContent).toBe("Đã sao chép toàn bộ mã.");
    },
  );

  it("does not let an earlier success timer reset a newer pending copy", async () => {
    vi.useFakeTimers();
    const pending = deferred();
    const writeText = vi.fn()
      .mockResolvedValueOnce(undefined)
      .mockImplementationOnce(() => pending.promise);
    installClipboard(writeText);
    render(<CodeBlock code={code} language="python" />);

    await clickCopy();
    expect(screen.getByRole("button", { name: "Đã sao chép" })).toBeTruthy();
    act(() => vi.advanceTimersByTime(1500));

    fireEvent.click(screen.getByRole("button", { name: "Đã sao chép" }));
    act(() => vi.advanceTimersByTime(1000));

    expect(screen.getByRole("button", { name: "Đang sao chép" })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toBe("Đang sao chép mã…");

    await act(async () => pending.resolve());
    act(() => vi.advanceTimersByTime(1999));
    expect(screen.getByRole("button", { name: "Đã sao chép" })).toBeTruthy();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole("button", { name: "Sao chép mã" })).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("cleans up the success timer on unmount and ignores a late pending acknowledgement", async () => {
    vi.useFakeTimers();
    const pending = deferred();
    const writeText = vi.fn()
      .mockResolvedValueOnce(undefined)
      .mockImplementationOnce(() => pending.promise);
    installClipboard(writeText);
    const first = render(<CodeBlock code={code} language="python" />);

    await clickCopy();
    expect(vi.getTimerCount()).toBe(1);
    first.unmount();
    expect(vi.getTimerCount()).toBe(0);

    const second = render(<CodeBlock code={code} language="python" />);
    await clickCopy();
    second.unmount();
    await act(async () => pending.resolve());

    expect(vi.getTimerCount()).toBe(0);
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("CodeBlock reading interactions", () => {
  it("toggles wrap accessibly without changing the code", () => {
    const source = "line one\nline two\nline three\nline four\nline five";
    render(<CodeBlock code={source} language="text" />);
    const wrap = screen.getByRole("button", { name: "Ngắt dòng mã" });
    const viewport = screen.getByRole("region");

    expect(wrap.getAttribute("aria-pressed")).toBe("false");
    expect(wrap.getAttribute("aria-controls")).toBe(viewport.id);
    expect(screen.getByTestId("shiki-highlighter").getAttribute("data-line-numbers")).toBe("true");

    fireEvent.click(wrap);

    expect(wrap.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("shiki-highlighter").getAttribute("data-line-numbers")).toBe("false");
    expect(viewport.textContent).toBe(source);

    fireEvent.click(wrap);
    expect(wrap.getAttribute("aria-pressed")).toBe("false");
    expect(viewport.textContent).toBe(source);
  });

  it("previews 80 lines of a huge block, copies every raw line, and expands and collapses it", async () => {
    const lines = Array.from({ length: 1001 }, (_, index) => "const dòng_" + index + " = '<tag>&';");
    const source = lines.join("\n");
    const preview = lines.slice(0, 80).join("\n");
    const writeText = vi.fn().mockResolvedValue(undefined);
    installClipboard(writeText);
    render(<CodeBlock code={source} language="javascript" />);
    const viewport = screen.getByRole("region");

    expect(viewport.textContent).toBe(preview);
    expect(screen.getByText("80 / 1001 dòng")).toBeTruthy();
    expect(screen.queryByTestId("shiki-highlighter")).toBeNull();
    expect(mocks.highlight).not.toHaveBeenCalled();
    const expand = screen.getByRole("button", { name: "Xem toàn bộ mã" });
    expect(expand.getAttribute("aria-expanded")).toBe("false");
    expect(expand.getAttribute("aria-controls")).toBe(viewport.id);

    await clickCopy();

    expect(writeText).toHaveBeenCalledExactlyOnceWith(source);
    fireEvent.click(expand);
    expect(viewport.textContent).toBe(source);
    const collapse = screen.getByRole("button", { name: "Thu gọn mã" });
    expect(collapse.getAttribute("aria-expanded")).toBe("true");
    expect(screen.queryByTestId("shiki-highlighter")).toBeNull();

    fireEvent.click(collapse);

    expect(viewport.textContent).toBe(preview);
    expect(screen.getByRole("button", { name: "Xem toàn bộ mã" }).getAttribute("aria-expanded")).toBe("false");
    expect(mocks.highlight).not.toHaveBeenCalled();
  });

  it("keeps streaming code as plaintext and highlights only after completion", () => {
    const source = "const message = '<b>mã</b>';\nconsole.log(message);";
    const view = render(<CodeBlock code={source} language="javascript" streaming />);

    expect(screen.getByRole("region").textContent).toBe(source);
    expect(screen.getByText("Đang nhận mã…")).toBeTruthy();
    expect(screen.queryByTestId("shiki-highlighter")).toBeNull();
    expect(mocks.highlight).not.toHaveBeenCalled();

    const completedCode = source + "\n// hoàn tất";
    view.rerender(<CodeBlock code={completedCode} language="javascript" streaming={false} />);

    expect(screen.queryByText("Đang nhận mã…")).toBeNull();
    expect(screen.getByTestId("shiki-highlighter").textContent).toBe(completedCode);
    expect(mocks.highlight).toHaveBeenCalledWith(expect.objectContaining({
      children: completedCode,
      language: "javascript",
    }));
  });

  it.each([true, false])("renders HTML literally without creating executable elements (streaming=%s)", (streaming) => {
    const source = '<script>throw new Error("execute");</script>\n<img src="x" onerror="alert(1)">\n<iframe src="https://example.invalid"></iframe>';
    const { container } = render(<CodeBlock code={source} language="html" streaming={streaming} />);

    expect(screen.getByRole("region").textContent).toBe(source);
    expect(container.querySelector("script, img, iframe")).toBeNull();
    expect(screen.getByRole("button", { name: "Mở trong sandbox" })).toBeTruthy();
    expect(mocks.openArtifact).not.toHaveBeenCalled();
  });
});
