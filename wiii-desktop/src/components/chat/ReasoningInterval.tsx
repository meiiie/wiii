import { useMemo, useState } from "react";
import type { ComponentType } from "react";
import { AnimatePresence, motion } from "motion/react";
import { createPortal } from "react-dom";
import {
  BookOpen,
  ChevronRight,
  Clock3,
  FileSearch,
  Globe2,
  Image as ImageIcon,
  TerminalSquare,
  Wrench,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type {
  ActionTextBlockData,
  ArtifactBlockData,
  ContentBlock,
  PreviewBlockData,
  ScreenshotBlockData,
  ThinkingBlockData,
  ThinkingLevel,
  ToolExecutionBlockData,
  VisualBlockData,
} from "@/api/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { NODE_LABELS, PHASE_LABELS } from "@/lib/reasoning-labels";
import {
  ToolExecutionStrip,
  summarizeToolExecutionBlock,
} from "./ToolExecutionStrip";
import { ThinkingBlock } from "./ThinkingBlock";
import { ScreenshotBlock } from "./ScreenshotBlock";
import { PreviewGroup } from "./PreviewGroup";
import { ArtifactCard } from "./ArtifactCard";
import { VisualBlock } from "./VisualBlock";

export type ReasoningIntervalItem =
  | { kind: "thinking"; id: string; block: ThinkingBlockData }
  | { kind: "action"; id: string; block: ActionTextBlockData }
  | { kind: "tool"; id: string; block: ToolExecutionBlockData }
  | { kind: "status"; id: string; content: string }
  | { kind: "preview"; id: string; block: PreviewBlockData }
  | { kind: "artifact"; id: string; block: ArtifactBlockData }
  | { kind: "screenshot"; id: string; block: ScreenshotBlockData };

export interface ReasoningIntervalViewModel {
  id: string;
  stepId?: string;
  node?: string;
  label: string;
  summary?: string;
  phase?: string;
  isLive: boolean;
  durationSeconds?: number;
  items: ReasoningIntervalItem[];
  rawBlocks: ContentBlock[];
}

function normalizeNode(node?: string) {
  return (node || "").toLowerCase().replace(/\s+/g, "_");
}

function getNodeLabel(node?: string) {
  return NODE_LABELS[normalizeNode(node)] || node || "Đang suy luận";
}

/** Short label for header (max ~60 chars). Full summary goes to body. */
function getIntervalHeaderLabel(interval: ReasoningIntervalViewModel) {
  // Priority: phase label > custom label > node label > fallback
  if (interval.phase && PHASE_LABELS[interval.phase]) return PHASE_LABELS[interval.phase];
  if (interval.label?.trim()) {
    const label = interval.label.trim();
    return label.length <= 60 ? label : `${label.slice(0, 57)}...`;
  }
  return getNodeLabel(interval.node);
}

/** Full summary for the expanded body preview. */
function getIntervalSummary(interval: ReasoningIntervalViewModel) {
  return interval.summary?.trim() || interval.label?.trim() || "";
}

function buildPreviewLine(block: PreviewBlockData) {
  const first = block.items[0];
  if (!first) return "Đã đối chiếu một preview";
  return `${first.title}${first.snippet ? ` — ${first.snippet}` : ""}`;
}

function buildArtifactLine(block: ArtifactBlockData) {
  const artifact = block.artifact;
  if (!artifact) return "Da tao mot artifact";
  return `${artifact.title}${artifact.artifact_type ? ` • ${artifact.artifact_type}` : ""}`;
}

function summarizeAction(block: ActionTextBlockData) {
  return {
    label: getNodeLabel(block.node),
    text: block.content,
  };
}

function resolveOperationIcon(kind: ReasoningIntervalItem["kind"], toolName?: string) {
  if (kind === "status") return Clock3;
  if (kind === "action") return ChevronRight;
  if (kind === "preview") return Globe2;
  if (kind === "artifact") return FileSearch;
  if (kind === "screenshot") return ImageIcon;
  if (kind === "tool" && toolName) {
    const { Icon } = summarizeToolExecutionBlock({
      type: "tool_execution",
      id: "__summary__",
      tool: { id: "__summary__", name: toolName },
      status: "pending",
    } as ToolExecutionBlockData);
    return Icon;
  }
  if (toolName?.includes("search")) return Globe2;
  if (toolName?.includes("python") || toolName?.includes("code")) return TerminalSquare;
  if (toolName?.includes("generate") || toolName?.includes("file")) return FileSearch;
  if (toolName?.includes("knowledge")) return BookOpen;
  return Wrench;
}

function normalizeInlineText(value: string | undefined) {
  return (value || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function renderThinkingMarkdown(
  block: ThinkingBlockData,
  withCursor = false,
) {
  if (!block.content?.trim()) return null;
  return (
    <div className="reasoning-interval__thinking">
      <MarkdownRenderer content={block.content} />
      {withCursor && (
        <span
          className="reasoning-interval__cursor"
          aria-hidden="true"
        />
      )}
    </div>
  );
}

function OperationRow({
  icon: Icon,
  label,
  body,
  tone = "default",
}: {
  icon: ComponentType<{ size?: string | number; className?: string }> | LucideIcon;
  label: string;
  body: string;
  tone?: "default" | "success" | "pending";
}) {
  return (
    <div className={`reasoning-op-row reasoning-op-row--${tone}`}>
      <div className="reasoning-op-row__icon" aria-hidden="true">
        <Icon size={12} />
      </div>
      <div className="reasoning-op-row__body">
        <div className="reasoning-op-row__label">{label}</div>
        <div className="reasoning-op-row__text">{body}</div>
      </div>
    </div>
  );
}

function renderOperationItem(
  item: ReasoningIntervalItem,
  thinkingLevel: ThinkingLevel,
) {
  if (item.kind === "status") {
    return (
      <OperationRow
        key={item.id}
        icon={resolveOperationIcon(item.kind)}
        label="Tien trinh"
        body={item.content}
        tone="pending"
      />
    );
  }

  if (item.kind === "action") {
    const action = summarizeAction(item.block);
    return (
      <OperationRow
        key={item.id}
        icon={resolveOperationIcon(item.kind)}
        label={action.label}
        body={action.text}
      />
    );
  }

  if (item.kind === "tool") {
    if (item.block.tool.name === "tool_create_visual_code") {
      return <ToolExecutionStrip key={item.id} block={item.block} />;
    }
    const summary = summarizeToolExecutionBlock(item.block);
    const body = [summary.argsLine, summary.resultLine].filter(Boolean).join(" • ")
      || "Đang thực hiện một thao tác";
    return (
      <OperationRow
        key={item.id}
        icon={summary.Icon}
        label={summary.label}
        body={body}
        tone={summary.isPending ? "pending" : "success"}
      />
    );
  }

  if (thinkingLevel !== "detailed") return null;

  if (item.kind === "preview") {
    return (
      <OperationRow
        key={item.id}
        icon={resolveOperationIcon(item.kind)}
        label="Preview"
        body={buildPreviewLine(item.block)}
      />
    );
  }

  if (item.kind === "artifact") {
    return (
      <OperationRow
        key={item.id}
        icon={resolveOperationIcon(item.kind)}
        label="Artifact"
        body={buildArtifactLine(item.block)}
        tone="success"
      />
    );
  }

  if (item.kind === "screenshot") {
    return (
      <OperationRow
        key={item.id}
        icon={resolveOperationIcon(item.kind)}
        label="Anh kiem chung"
        body={item.block.label || item.block.url || "Da cap nhat mot anh chup"}
      />
    );
  }

  return null;
}

function compactBalancedItems(items: ReasoningIntervalItem[], isLive: boolean) {
  const thinkingItems = items.filter((item) => item.kind === "thinking");
  const operationItems = items.filter((item) => (
    item.kind === "action" || item.kind === "tool" || item.kind === "status"
  ));

  const compactThinkingItems = (() => {
    if (thinkingItems.length <= 1) return thinkingItems;

    const addUniqueThinkingItem = (
      selected: ReasoningIntervalItem[],
      candidate?: ReasoningIntervalItem,
    ) => {
      if (!candidate || candidate.kind !== "thinking") return selected;
      const candidateText = normalizeInlineText(candidate.block.summary || candidate.block.content);
      if (!candidateText) return selected;
      const alreadyExists = selected.some((item) => (
        item.kind === "thinking"
        && normalizeInlineText(item.block.summary || item.block.content) === candidateText
      ));
      if (alreadyExists) return selected;
      return [...selected, candidate];
    };

    const openingThinking = thinkingItems[0];
    const latestThinking = thinkingItems[thinkingItems.length - 1];

    let selected: ReasoningIntervalItem[] = [];
    if (!isLive && thinkingItems.length === 2) {
      selected = addUniqueThinkingItem(selected, openingThinking);
      selected = addUniqueThinkingItem(selected, latestThinking);
      return selected.length > 0 ? selected : [latestThinking];
    }

    const summaryAnchor = thinkingItems.find((item) => (
      normalizeInlineText(item.block.summary).length > 0
    )) || openingThinking;

    selected = addUniqueThinkingItem(selected, summaryAnchor);
    selected = addUniqueThinkingItem(selected, latestThinking);

    return selected.length > 0 ? selected : [latestThinking];
  })();

  if (operationItems.length === 0) return compactThinkingItems;

  const findLastMatching = (
    predicate: (item: typeof operationItems[number]) => boolean,
  ) => {
    for (let index = operationItems.length - 1; index >= 0; index -= 1) {
      const candidate = operationItems[index];
      if (candidate && predicate(candidate)) return candidate;
    }
    return undefined;
  };

  const primaryOperation = (
    findLastMatching((item) => item.kind === "tool" && item.block.status === "pending")
    || findLastMatching((item) => item.kind === "status" && normalizeInlineText(item.content).startsWith("dang "))
    || findLastMatching((item) => item.kind === "tool")
    || (isLive ? findLastMatching((item) => item.kind === "action") : undefined)
    || operationItems[0]
  );

  return primaryOperation ? [...compactThinkingItems, primaryOperation] : compactThinkingItems;
}

function selectVisibleItems(
  items: ReasoningIntervalItem[],
  thinkingLevel: ThinkingLevel,
  isLive: boolean,
) {
  if (thinkingLevel === "detailed") return items;

  if (thinkingLevel === "balanced") {
    return compactBalancedItems(items, isLive);
  }

  return items.filter((item) => item.kind === "thinking");
}

export function ReasoningInterval({
  interval,
  thinkingLevel,
  onOpenInspector: _onOpenInspector,
}: {
  interval: ReasoningIntervalViewModel;
  thinkingLevel: ThinkingLevel;
  onOpenInspector: () => void;
}) {
  const headerLabel = getIntervalHeaderLabel(interval);
  void getIntervalSummary; // Available for future use (body preview)
  const durationText = interval.durationSeconds ? `${interval.durationSeconds}s` : "";

  // Sprint V5: Claude-pattern collapsible — header is clickable, body toggles
  const [expanded, setExpanded] = useState(false);
  const isBalanced = thinkingLevel === "balanced";
  void isBalanced;
  const allItems = interval.items;
  const visibleItems = useMemo(
    () => selectVisibleItems(allItems, thinkingLevel, interval.isLive),
    [allItems, thinkingLevel, interval.isLive],
  );
  // In balanced mode: collapsed by default, show body on click
  // In detailed mode: always expanded
  // While live: always show body (streaming)
  const showBody = thinkingLevel === "detailed" || interval.isLive || expanded;

  return (
    <section
      className={`reasoning-interval reasoning-interval--${interval.isLive ? "live" : "complete"}`}
      data-testid="reasoning-interval"
      data-step-id={interval.stepId || ""}
    >
      <div className="reasoning-interval__main">
        {/* Claude pattern: Header row — separated from body, acts as anchor point */}
        <button
          className="reasoning-interval__header-btn"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={showBody}
        >
          {interval.isLive ? (
            <span className="reasoning-interval__live-dot" />
          ) : (
            <svg className="reasoning-interval__header-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
            </svg>
          )}
          {interval.node && (
            <span className="reasoning-interval__agent-chip">
              {getNodeLabel(interval.node)}
            </span>
          )}
          <span className="reasoning-interval__header-label">{headerLabel}</span>
          {durationText && !interval.isLive && (
            <span className="reasoning-interval__header-duration">{durationText}</span>
          )}
          <svg
            width="12" height="12" viewBox="0 0 20 20" fill="currentColor"
            className={`reasoning-interval__chevron ${showBody ? "reasoning-interval__chevron--open" : ""}`}
          >
            <path d="M14.128 7.16482C14.3126 6.95983 14.6298 6.94336 14.835 7.12771C15.0402 7.31242 15.0567 7.62952 14.8721 7.83477L10.372 12.835C10.1755 13.0551 9.82445 13.0551 9.62788 12.835L5.12778 7.83477C4.94317 7.62952 4.95963 7.31242 5.16489 7.12771C5.37015 6.94336 5.68741 6.95983 5.87193 7.16482L9.99995 11.7519L14.128 7.16482Z" />
          </svg>
        </button>
        <span className="sr-only" role="status" aria-live="polite">{headerLabel}</span>

        {/* Claude pattern: Body with left rail (vertical line + content) */}
        <div
          className="reasoning-interval__collapse"
          style={{ gridTemplateRows: showBody ? "1fr" : "0fr" }}
        >
          <div className="reasoning-interval__collapse-inner">
            <div className="reasoning-interval__rail-layout">
              {/* Left rail: clock node icon + vertical line (Claude pattern) */}
              <div className="reasoning-interval__rail-track" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text-tertiary)', opacity: 0.5 }}>
                  <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                </svg>
                <div className="reasoning-interval__rail-line" />
              </div>
              {/* Right: thinking content */}
              <div className="reasoning-interval__rail-content">
                {visibleItems.map((item) => {
                  if (item.kind === "thinking") {
                    const isLastThinking = interval.isLive && interval.items[interval.items.length - 1]?.id === item.id;
                    return (
                      <div key={item.id} className="reasoning-interval__segment">
                        {renderThinkingMarkdown(item.block, isLastThinking)}
                      </div>
                    );
                  }
                  const operation = renderOperationItem(item, thinkingLevel);
                  if (!operation) return null;
                  return (
                    <div key={item.id} className="reasoning-interval__segment reasoning-interval__segment--operation">
                      {operation}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function renderInspectorBlock(block: ContentBlock) {
  if (block.type === "thinking") {
    return (
      <ThinkingBlock
        key={block.id}
        content={block.content}
        toolCalls={block.toolCalls}
        savedDuration={
          block.startTime && block.endTime
            ? Math.round((block.endTime - block.startTime) / 1000)
            : undefined
        }
        label={block.label}
        summary={block.summary || block.label}
        phase={block.phase}
        thinkingLevel="detailed"
        autoExpand
      />
    );
  }

  if (block.type === "tool_execution") {
    return <ToolExecutionStrip key={block.id} block={block} />;
  }

  if (block.type === "action_text") {
    const action = summarizeAction(block);
    return (
      <OperationRow
        key={block.id}
        icon={ChevronRight}
        label={action.label}
        body={action.text}
      />
    );
  }

  if (block.type === "screenshot") {
    return <ScreenshotBlock key={block.id} block={block} />;
  }

  if (block.type === "preview") {
    return <PreviewGroup key={block.id} block={block} />;
  }

  if (block.type === "artifact") {
    return <ArtifactCard key={block.id} artifact={block.artifact} />;
  }

  if (block.type === "visual") {
    return <VisualBlock key={block.id} block={block as VisualBlockData} embedded />;
  }

  if (block.type === "answer") {
    return (
      <div key={block.id} className="reasoning-inspector__answer">
        <MarkdownRenderer content={block.content} />
      </div>
    );
  }

  return null;
}

export function ThinkingInspectorDrawer({
  isOpen,
  title,
  blocks,
  onClose,
}: {
  isOpen: boolean;
  title: string;
  blocks: ContentBlock[];
  onClose: () => void;
}) {
  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.button
            type="button"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="reasoning-inspector__backdrop"
            onClick={onClose}
            aria-label="Dong trace"
          />
          <motion.aside
            initial={{ opacity: 0, x: 28 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 28 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="reasoning-inspector"
            data-testid="reasoning-inspector-drawer"
          >
            <header className="reasoning-inspector__header">
              <div>
                <div className="reasoning-inspector__eyebrow">Debug trace</div>
                <h3 className="reasoning-inspector__title">{title}</h3>
              </div>
              <button
                type="button"
                className="reasoning-inspector__close"
                onClick={onClose}
                aria-label="Dong trace"
              >
                <X size={16} />
              </button>
            </header>
            <div className="reasoning-inspector__body">
              {blocks.map((block) => renderInspectorBlock(block))}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}
