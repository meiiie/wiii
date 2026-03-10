import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToolExecutionStrip } from "@/components/chat/ToolExecutionStrip";
import type { ToolExecutionBlockData } from "@/api/types";

describe("ToolExecutionStrip", () => {
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
});
