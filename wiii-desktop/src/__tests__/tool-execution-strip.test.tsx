import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ToolExecutionStrip } from "@/components/chat/ToolExecutionStrip";
import type { ToolExecutionBlockData } from "@/api/types";
import { useCodeStudioStore } from "@/stores/code-studio-store";

describe("ToolExecutionStrip", () => {
  beforeEach(() => {
    useCodeStudioStore.setState({
      activeSessionId: null,
      sessions: {},
    });
  });

  it("renders CodeStudioCard when tool_create_visual_code returns a visual_session_id in result payload", () => {
    useCodeStudioStore.setState({
      activeSessionId: "vs_app_1",
      sessions: {
        vs_app_1: {
          sessionId: "vs_app_1",
          title: "Pendulum App",
          language: "html",
          status: "complete",
          code: "<div>app</div>",
          versions: [{ version: 1, code: "<div>app</div>", title: "Pendulum App", timestamp: Date.now() }],
          activeVersion: 1,
          chunkCount: 1,
          totalBytes: 14,
          createdAt: Date.now(),
          metadata: { studioLane: "app" },
        },
      },
    });

    const block: ToolExecutionBlockData = {
      type: "tool_execution",
      id: "tool-code-1",
      status: "completed",
      tool: {
        id: "tool-code-1",
        name: "tool_create_visual_code",
        args: {
          title: "Pendulum App",
        },
        result: JSON.stringify({
          visual_session_id: "vs_app_1",
        }),
      },
    };

    render(<ToolExecutionStrip block={block} />);

    expect(screen.getByText("Code Studio")).toBeTruthy();
    expect(screen.getByText("Pendulum App")).toBeTruthy();
  });

  it("hides raw python code and filesystem paths by default", () => {
    const block: ToolExecutionBlockData = {
      type: "tool_execution",
      id: "tool-1",
      status: "completed",
      tool: {
        id: "tool-1",
        name: "tool_execute_python",
        args: {
          code: "import matplotlib.pyplot as plt\nplt.savefig('chart.png')",
        },
        result: [
          "Output: Bieu do da tao thanh cong!",
          "Artifacts:",
          "- chart.png (image/png) -> /home/appuser/.wiii/workspace/generated/chart_20260309.png",
        ].join("\n"),
      },
    };

    render(<ToolExecutionStrip block={block} />);

    expect(screen.getByText("Script Python de tao bieu do chart.png")).toBeTruthy();
    expect(screen.getByText("Da tao 1 tep: chart.png")).toBeTruthy();
    expect(screen.queryByText(/import matplotlib/i)).toBeNull();
    expect(screen.queryByText(/\/home\/appuser/i)).toBeNull();
  });

  it("reveals sanitized technical detail only when expanded", () => {
    const block: ToolExecutionBlockData = {
      type: "tool_execution",
      id: "tool-2",
      status: "completed",
      tool: {
        id: "tool-2",
        name: "tool_execute_python",
        args: {
          code: "print('hello')\nplt.savefig('demo.png')",
        },
        result: "Output: done\nArtifacts:\n- demo.png (image/png) -> C:\\temp\\generated\\demo.png",
      },
    };

    render(<ToolExecutionStrip block={block} />);

    expect(screen.queryByRole("region", { name: "Chi tiet script" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /chi tiet/i }));

    const detail = screen.getByRole("region", { name: "Chi tiet script" });
    expect(detail).toBeTruthy();
    expect(screen.getByText(/print\('hello'\)/i)).toBeTruthy();
    expect(screen.queryByText(/C:\\temp\\generated/i)).toBeNull();
    expect(detail.textContent || "").toContain("demo.png");
  });

  it("uses softer phrasing for visual generation strips", () => {
    const block: ToolExecutionBlockData = {
      type: "tool_execution",
      id: "tool-visual-1",
      status: "completed",
      tool: {
        id: "tool-visual-1",
        name: "tool_generate_visual",
        args: {
          title: "Softmax vs linear attention",
        },
        result: '{"title":"Softmax vs linear attention"}',
      },
    };

    render(<ToolExecutionStrip block={block} />);

    expect(screen.getByText("Dang phac thao minh hoa cho: Softmax vs linear attention")).toBeTruthy();
    expect(screen.getByText("Da chen minh hoa ngay trong cau tra loi")).toBeTruthy();
    expect(screen.queryByText(/ky thuat/i)).toBeNull();
  });
});
