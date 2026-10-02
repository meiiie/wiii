import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { NekoTranscript } from "@/neko-chill/components/NekoTranscript";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";

vi.mock("@/components/common/ShikiMinimalHighlighter", () => ({
  ShikiMinimalHighlighter: ({ children, language }: { children: string; language: string }) => <pre data-testid="syntax-code" data-language={language}><code>{children}</code></pre>,
}));

describe("Markdown code routing and safety", () => {
  it.each(["", "c++", "c#", "diff", "unknown-language"])("renders a fenced block once and preserves its language token (%s)", async language => {
    const text = "const pattern = './src/**/*';\nconst label = 'A --- B';";
    const { container } = render(<MarkdownRenderer content={`Before\n\n\`\`\`${language}\n${text}\n\`\`\``} />);
    const block = await screen.findByTestId("code-block");
    expect(screen.getAllByTestId("code-block")).toHaveLength(1);
    expect(block.querySelector("code")?.textContent).toBe(text);
    expect((await screen.findByTestId("syntax-code")).getAttribute("data-language")).toBe(language || "text");
    expect(container.querySelector("pre [data-testid='code-block']")).toBeNull();
    expect(screen.getByRole("button", { name: "Sao chép mã" })).toBeTruthy();
  });

  it.each([
    ['    const label = "A --- B";', 'const label = "A --- B";'],
    ['> ```js\n> const label = "A --- B";\n> ```', 'const label = "A --- B";'],
    ['- item\n    ```js\n    const label = "A --- B";\n    ```', 'const label = "A --- B";'],
  ])("preserves code in pure indentation and containers (%s)", async (content, expected) => {
    render(<MarkdownRenderer content={content} />);
    const block = await screen.findByTestId("code-block");
    expect(block.querySelector("code")?.textContent).toBe(expected);
  });

  it("keeps inline code inline and routes indented code through block controls", async () => {
    const { container } = render(<MarkdownRenderer content={"Inline `x + y` stays in prose.\n\n    first()\n    second()"} />);
    const block = await screen.findByTestId("code-block");
    expect(block.querySelector("code")?.textContent).toBe("first()\nsecond()");
    expect(container.querySelector("p code")?.textContent).toBe("x + y");
    expect(screen.getAllByTestId("code-block")).toHaveLength(1);
  });

  it("keeps prefixed partial fences literal while streaming, then highlights the completed code", async () => {
    const code = "const label = 'A --- B';\nconst glob = './src/**/*';\nconst list = 'a 1. b';";
    const prefix = "Draft: --- code follows\n\n```typescript\n";
    const { rerender } = render(<MarkdownRenderer content={prefix + code} streaming />);
    let block = await screen.findByTestId("code-block");
    expect(block.querySelector("code")?.textContent).toBe(code);
    expect(screen.queryByTestId("syntax-code")).toBeNull();
    rerender(<MarkdownRenderer content={prefix + code + "\n```"} />);
    await screen.findByTestId("syntax-code");
    block = screen.getByTestId("code-block");
    expect(block.querySelector("code")?.textContent).toBe(code);
  });

  it("keeps a valid GFM table readable alongside an incomplete code fence", async () => {
    render(<MarkdownRenderer content={'| Key | Value |\n| --- | --- |\n| glob | ./src/**/* |\n\n```js\nconst label = "A --- B";'} streaming />);
    expect(await screen.findByRole("table")).toBeTruthy();
    expect(screen.getByRole("cell", { name: "./src/**/*" })).toBeTruthy();
    expect((await screen.findByTestId("code-block")).querySelector("code")?.textContent).toBe('const label = "A --- B";');
  });

  it("highlights history but keeps only the live Neko answer lightweight until completion", async () => {
    const session = {
      id: "renderer-tail", agentName: "Neko Core", status: "streaming", controls: [], commands: [], events: [],
      pendingPermission: null, resolvingPermissionId: null,
      messages: [
        { id: "history", role: "assistant", blocks: [{ id: "past", type: "answer", content: "```js\nconst past = true;\n```" }] },
        { id: "live", role: "assistant", blocks: [{ id: "tail", type: "answer", content: "```js\nconst live = true;" }] },
      ],
    } as unknown as NekoSession;
    const { rerender } = render(<NekoTranscript session={session} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    expect(await screen.findAllByTestId("code-block")).toHaveLength(2);
    expect(await screen.findAllByTestId("syntax-code")).toHaveLength(1);
    expect(screen.getAllByTestId("code-block")[1].querySelector("code")?.textContent).toBe("const live = true;");
    rerender(<NekoTranscript session={{ ...session, status: "idle" }} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    expect(await screen.findAllByTestId("syntax-code")).toHaveLength(2);
  });

  it("renders literal HTML in code and removes script/event handlers/unsafe links from prose", async () => {
    const literal = '<script>window.bad = true</script>\n<img src="x" onerror="window.bad = true">';
    const content = `<script>window.bad = true</script>\n<p onclick="window.bad = true">Safe text</p>\n<a href="javascript:alert(1)">Unsafe link</a>\n\n\`\`\`html\n${literal}\n\`\`\``;
    const { container } = render(<MarkdownRenderer content={content} />);
    const block = await screen.findByTestId("code-block");
    expect(block.querySelector("code")?.textContent).toBe(literal);
    expect(container.querySelector("script, [onclick], [onerror]")).toBeNull();
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(container.textContent).toContain("Safe text");
    const copy = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: copy } });
    fireEvent.click(screen.getByRole("button", { name: "Sao chép mã" }));
    await screen.findByRole("button", { name: "Đã sao chép" });
    expect(copy).toHaveBeenCalledExactlyOnceWith(literal);
  });
});

it("routes spaces before a tab as indented code without losing copy controls", async () => {
  render(<MarkdownRenderer content={" \tfirst()\n \tsecond()"} />);
  const block = await screen.findByTestId("code-block");
  expect(block.querySelector("code")?.textContent).toBe("first()\nsecond()");
  expect(within(block).getByRole("button", { name: "Sao chép mã" })).toBeTruthy();
});
