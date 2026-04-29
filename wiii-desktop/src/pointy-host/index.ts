/**
 * Wiii Pointy — public API.
 *
 * Drop into the host (LMS) page:
 *
 *   <script src="https://wiii.holilihu.online/pointy/wiii-pointy.umd.js"></script>
 *   <script>
 *     WiiiPointy.init({
 *       iframeOrigin: "https://wiii.holilihu.online",
 *       onNavigate: (route) => angularRouter.navigateByUrl(route),
 *     });
 *   </script>
 *
 * The bundle is **read-only** in V1: highlight, scroll_to, navigate,
 * show_tour. No auto-click, no auto-fill. Default tutor mode keeps the
 * student in control.
 */
import { createBridge, type BridgeHandle } from "./bridge";
import { destroyCursor, hideCursor } from "./cursor";
import { destroySpotlight, hideSpotlight } from "./spotlight";
import { cancelActiveTour } from "./tour";
import {
  POINTY_ACTIONS,
  POINTY_PROTOCOL_VERSION,
  type PointyConfig,
  type PointyToolDefinition,
} from "./types";

export const VERSION = "1.0.0";

const DEFAULT_TOOLS: PointyToolDefinition[] = [
  {
    name: "ui.highlight",
    description:
      "Trỏ và làm nổi bật một phần tử trên trang để hướng dẫn người dùng. Không tự click — chỉ chỉ đường.",
    input_schema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector hoặc [data-wiii-id=\"...\"]" },
        message: { type: "string", description: "Tooltip hiển thị bên cạnh element" },
        duration_ms: { type: "number", description: "Thời gian giữ spotlight (ms, mặc định 2200)" },
      },
      required: ["selector"],
    },
    surface: "page",
    mutates_state: false,
    requires_confirmation: false,
  },
  {
    name: "ui.scroll_to",
    description: "Cuộn trang đến một phần tử cụ thể.",
    input_schema: {
      type: "object",
      properties: {
        selector: { type: "string" },
        block: { type: "string", description: "start | center | end" },
      },
      required: ["selector"],
    },
    surface: "page",
    mutates_state: false,
    requires_confirmation: false,
  },
  {
    name: "ui.navigate",
    description:
      "Chuyển đến một route nội bộ (ưu tiên) hoặc URL tuyệt đối an toàn. Không phá vỡ session người dùng.",
    input_schema: {
      type: "object",
      properties: {
        route: { type: "string", description: "Route nội bộ, ví dụ: /courses/123" },
        url: { type: "string", description: "URL http(s) tuyệt đối" },
      },
    },
    surface: "page",
    mutates_state: false,
    requires_confirmation: false,
  },
  {
    name: "ui.show_tour",
    description: "Chạy hướng dẫn nhiều bước. Mỗi bước trỏ và highlight một element kèm tooltip.",
    input_schema: {
      type: "object",
      properties: {
        steps: {
          type: "array",
          description: "Danh sách bước { selector, message, duration_ms? }",
        },
        start_at: { type: "number", description: "Bước bắt đầu (mặc định 0)" },
      },
      required: ["steps"],
    },
    surface: "page",
    mutates_state: false,
    requires_confirmation: false,
  },
];

let activeBridge: BridgeHandle | null = null;

export interface InitResult {
  /** Returns the capability payload to post into the iframe via wiii:capabilities. */
  capabilities: () => {
    type: "wiii:capabilities";
    payload: {
      host_type: string;
      host_name?: string;
      version: string;
      surfaces: string[];
      tools: PointyToolDefinition[];
    };
  };
  destroy: () => void;
}

/**
 * Initialise the pointy bridge. Idempotent — calling init() twice replaces
 * the previous bridge.
 */
export function init(config: PointyConfig): InitResult {
  if (activeBridge) activeBridge.dispose();
  activeBridge = createBridge(config);

  return {
    capabilities: () => ({
      type: "wiii:capabilities",
      payload: {
        host_type: "lms",
        host_name: "Wiii Pointy host",
        version: String(POINTY_PROTOCOL_VERSION),
        surfaces: ["page"],
        tools: DEFAULT_TOOLS.slice(),
      },
    }),
    destroy: () => {
      destroy();
    },
  };
}

/** Tear down the bridge and remove all overlays. */
export function destroy(): void {
  if (activeBridge) {
    activeBridge.dispose();
    activeBridge = null;
  }
  cancelActiveTour();
  hideSpotlight();
  hideCursor();
  destroyCursor();
  destroySpotlight();
}

export const ACTIONS = POINTY_ACTIONS;

export type {
  PointyConfig,
  PointyToolDefinition,
  HighlightParams,
  ScrollToParams,
  NavigateParams,
  ShowTourParams,
  TourStep,
} from "./types";
