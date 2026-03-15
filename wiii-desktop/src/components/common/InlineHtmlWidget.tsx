import { memo } from "react";
import { useChatStore } from "@/stores/chat-store";
import { InlineVisualFrame } from "./InlineVisualFrame";

interface InlineHtmlWidgetProps {
  code: string;
  className?: string;
  widgetId?: string;
}

const InlineHtmlWidget = memo(function InlineHtmlWidget({
  code,
  className = "",
  widgetId = "legacy-widget",
}: InlineHtmlWidgetProps) {
  const recordWidgetFeedback = useChatStore((state) => state.recordWidgetFeedback);

  return (
    <InlineVisualFrame
      html={code}
      className={className}
      sessionId={widgetId}
      frameKind="legacy"
      shellVariant="editorial"
      hostShellMode="force"
      onBridgeEvent={(detail) => {
        if (detail.bridgeType !== "result") return;
        const payload = detail.payload && typeof detail.payload === "object"
          ? detail.payload as Record<string, unknown>
          : undefined;
        recordWidgetFeedback({
          widget_id: String(detail.sessionId || widgetId),
          widget_kind: String(detail.kind || "widget_result"),
          summary: typeof detail.summary === "string" ? detail.summary : undefined,
          status: typeof detail.status === "string" && detail.status ? detail.status : undefined,
          title: typeof detail.title === "string" ? detail.title : undefined,
          visual_session_id: typeof detail.sessionId === "string" ? detail.sessionId : undefined,
          score: typeof payload?.score === "number" ? payload.score : undefined,
          correct_count: typeof payload?.correct_count === "number" ? payload.correct_count : undefined,
          total_count: typeof payload?.total_count === "number" ? payload.total_count : undefined,
          source: "legacy_widget",
          data: payload,
        });
      }}
    />
  );
});

export default InlineHtmlWidget;
