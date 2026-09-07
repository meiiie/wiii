import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import MermaidDiagram from "@/components/common/MermaidDiagram";

const mermaid = vi.hoisted(() => ({ initialize: vi.fn(), render: vi.fn() }));
vi.mock("mermaid", () => ({ default: mermaid }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("isolated Mermaid output", () => {
  it("keeps diagram HTML and CSS inside a scriptless frame without navigation permissions", async () => {
    const diagram = '<html><body><style>body{background:red}</style><div id="diagram-content">Graph</div></body></html>';
    mermaid.render.mockResolvedValue({ svg: `<iframe style="height:160px" src="data:text/html;charset=UTF-8;base64,${btoa(diagram)}" sandbox="allow-popups allow-top-navigation-by-user-activation"></iframe>` });
    render(<MermaidDiagram code="graph TD; A --> B" />);
    const frame = await screen.findByTitle("Biểu đồ Mermaid");
    expect(frame.getAttribute("sandbox")).toBe("");
    expect(frame.getAttribute("srcdoc")).toBe(diagram);
    expect(frame.hasAttribute("src")).toBe(false);
    expect(frame.style.height).toBe("160px");
    expect(document.getElementById("diagram-content")).toBeNull();
    expect(mermaid.initialize).toHaveBeenCalledWith(expect.objectContaining({ securityLevel: "sandbox" }));
  });

  it("refuses unexpected inline output rather than injecting it into Wiii", async () => {
    mermaid.render.mockResolvedValue({ svg: '<svg></svg><div id="injected">Injected</div>' });
    render(<MermaidDiagram code="stateDiagram-v2" />);
    await waitFor(() => expect(screen.getByText("Lỗi biểu đồ Mermaid")).toBeTruthy());
    expect(document.getElementById("injected")).toBeNull();
    expect(screen.queryByTitle("Biểu đồ Mermaid")).toBeNull();
  });
});
