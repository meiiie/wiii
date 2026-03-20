import { CheckCircle2, ChevronDown, LoaderCircle } from "lucide-react";
import type { ContentBlock, ThinkingPhase } from "@/api/types";

type JourneyStatus = "active" | "completed";

interface JourneyStep {
  id: string;
  label: string;
  detail?: string;
  status: JourneyStatus;
  node?: string;
  startTime?: number;
  endTime?: number;
}

interface ThinkingJourneyBannerProps {
  blocks?: ContentBlock[];
  phases?: ThinkingPhase[];
  fallbackLabel?: string;
  isStreaming?: boolean;
  mode?: "compact" | "rich";
  expanded?: boolean;
  onToggle?: () => void;
}

const LABEL_RULES: Array<{ keywords: string[]; label: string }> = [
  { keywords: ["phan tich", "analysis", "analyze", "supervisor", "guardian", "routing"], label: "Lam ro yeu cau" },
  { keywords: ["tra cuu", "retrieval", "lookup", "rag", "knowledge"], label: "Thu thap thong tin" },
  { keywords: ["tim kiem web", "web search", "internet", "news", "news search"], label: "Tim nguon moi" },
  { keywords: ["tim kiem san pham", "product search", "san pham"], label: "Tim kiem san pham" },
  { keywords: ["danh gia", "grading", "grader", "quality"], label: "Danh gia do tin cay" },
  { keywords: ["tinh chinh", "rewrite", "refine"], label: "Tinh chinh huong tra loi" },
  { keywords: ["tong hop", "synthesis", "generation", "tao cau tra loi", "response"], label: "Soan phan hoi" },
  { keywords: ["bo nho", "memory"], label: "Goi lai ngu canh" },
  { keywords: ["song song", "parallel", "dispatch"], label: "Phan cong song song" },
  { keywords: ["hop nhat", "aggregator", "tong hop bao cao"], label: "Hop nhat ket qua" },
  { keywords: ["social", "off topic", "direct"], label: "Phan hoi truc tiep" },
];

const NODE_COPY: Record<string, { label: string }> = {
  guardian: { label: "Giu an toan dau vao" },
  supervisor: { label: "Lam ro dieu ban muon" },
  direct: { label: "Giu nhip tro chuyen" },
  rag_agent: { label: "Luc lai tai lieu lien quan" },
  rag: { label: "Luc lai tai lieu lien quan" },
  tutor_agent: { label: "Sap lai loi giai de hieu" },
  tutor: { label: "Sap lai loi giai de hieu" },
  synthesizer: { label: "Det cau tra loi cuoi" },
  memory_agent: { label: "Goi lai ngu canh cua ban" },
  product_search_agent: { label: "So gia va doi chieu nguon" },
  search: { label: "So gia va doi chieu nguon" },
  parallel_dispatch: { label: "Tach viec cho nhieu huong" },
  aggregator: { label: "Gop cac huong tot nhat" },
  colleague_agent: { label: "Tham khao them mot goc nhin" },
};

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function cleanSentence(value: string): string {
  return value
    .replace(/^[\s\-\u2013\u2014\u2022]+/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 3).trim()}...`;
}

function normalizeNode(node?: string): string {
  return normalizeText(node || "").replace(/\s+/g, "_");
}

function toSentenceCase(value: string): string {
  if (!value) return value;
  return value.charAt(0).toLowerCase() + value.slice(1);
}

function joinLabels(labels: string[]): string {
  if (labels.length <= 1) return labels[0] || "";
  if (labels.length === 2) return `${labels[0]} va ${labels[1]}`;
  return `${labels.slice(0, -1).join(", ")} va ${labels[labels.length - 1]}`;
}

function formatDuration(totalMs?: number): string | null {
  if (!totalMs || totalMs <= 0) return null;
  const totalSeconds = Math.round(totalMs / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, "0")}`;
}

function summarizeContent(value?: string): string | undefined {
  if (!value) return undefined;
  const firstLine = value
    .split(/\n+/)
    .map((line) => cleanSentence(line))
    .find((line) => line.length > 0);
  if (!firstLine) return undefined;
  // Sprint 234: Increased from 108→180 to match backend adaptive thinking depth
  return truncateText(firstLine, 180);
}

function getNodeCopy(node?: string) {
  const normalizedNode = normalizeNode(node);
  return normalizedNode ? NODE_COPY[normalizedNode] : undefined;
}

function normalizeJourneyLabel(raw?: string, fallback?: string, node?: string): string {
  const nodeCopy = getNodeCopy(node);
  if (nodeCopy) return nodeCopy.label;

  const source = cleanSentence(raw || fallback || "");
  const normalized = normalizeText(`${source} ${fallback || ""}`);

  for (const rule of LABEL_RULES) {
    if (rule.keywords.some((keyword) => normalized.includes(keyword))) {
      return rule.label;
    }
  }

  if (!source) return "Dang xu ly";
  return truncateText(source, 42);
}

function pushStep(steps: JourneyStep[], nextStep: JourneyStep) {
  const lastStep = steps[steps.length - 1];
  if (lastStep && lastStep.label === nextStep.label) {
    lastStep.status = nextStep.status;
    lastStep.detail = lastStep.detail || nextStep.detail;
    lastStep.startTime = lastStep.startTime || nextStep.startTime;
    lastStep.endTime = nextStep.endTime || lastStep.endTime;
    return;
  }
  steps.push(nextStep);
}

function deriveStepsFromBlocks(blocks: ContentBlock[], isStreaming: boolean): JourneyStep[] {
  const steps: JourneyStep[] = [];

  for (const block of blocks) {
    if (block.type === "thinking") {
      if (block.groupId) continue;
      pushStep(steps, {
        id: block.id,
        label: normalizeJourneyLabel(block.summary || block.label, block.content, block.node || block.workerNode),
        detail: summarizeContent(block.content),
        status: isStreaming && !block.endTime ? "active" : "completed",
        node: block.node || block.workerNode,
        startTime: block.startTime,
        endTime: block.endTime,
      });
      continue;
    }

    if (block.type === "action_text") {
      const detail = summarizeContent(block.content);
      if (!detail) continue;
      const lastStep = steps[steps.length - 1];
      if (lastStep && !lastStep.detail) {
        lastStep.detail = detail;
      } else {
        pushStep(steps, {
          id: block.id,
          label: normalizeJourneyLabel(block.content, block.node, block.node),
          detail,
          status: "completed",
          node: block.node,
        });
      }
      continue;
    }

    if (block.type === "subagent_group") {
      pushStep(steps, {
        id: block.id,
        label: normalizeJourneyLabel(block.label, block.label, "parallel_dispatch"),
        detail: summarizeContent(block.label),
        status: isStreaming && !block.endTime ? "active" : "completed",
        node: "parallel_dispatch",
        startTime: block.startTime,
        endTime: block.endTime,
      });
    }
  }

  return steps;
}

function deriveStepsFromPhases(phases: ThinkingPhase[]): JourneyStep[] {
  const steps: JourneyStep[] = [];

  for (const phase of phases) {
    const fallbackDetail =
      phase.statusMessages[phase.statusMessages.length - 1] || phase.thinkingContent || phase.node;

    pushStep(steps, {
      id: phase.id,
      label: normalizeJourneyLabel(phase.label, fallbackDetail, phase.node),
      detail: summarizeContent(fallbackDetail),
      status: phase.status,
      node: phase.node,
      startTime: phase.startTime,
      endTime: phase.endTime,
    });
  }

  return steps;
}

function buildJourney(blocks: ContentBlock[], phases: ThinkingPhase[], fallbackLabel: string, isStreaming: boolean) {
  const steps = phases.length > 0
    ? deriveStepsFromPhases(phases)
    : deriveStepsFromBlocks(blocks, isStreaming);

  if (steps.length === 0 && fallbackLabel) {
    steps.push({
      id: "fallback",
      label: normalizeJourneyLabel(fallbackLabel),
      detail: summarizeContent(fallbackLabel),
      status: isStreaming ? "active" : "completed",
    });
  }

  const activeStep = [...steps].reverse().find((step) => step.status === "active") || steps[steps.length - 1];
  const completedCount = steps.filter((step) => step.status === "completed").length;
  // Sprint 234: Increased from 4→6 for complex multi-tool thinking flows
  const visibleLabels = Array.from(new Set(steps.map((step) => step.label))).slice(0, 6);
  const lowerLabels = visibleLabels.map((label) => toSentenceCase(label));
  const headline = isStreaming
    ? `Wiii dang ${toSentenceCase(activeStep?.label || "xu ly yeu cau")}`
    : visibleLabels.length > 0
      ? `Wiii da ${joinLabels(lowerLabels)}`
      : "Wiii da hoan tat xu ly";
  const lastDetail = steps
    .map((step) => step.detail)
    .filter((detail): detail is string => typeof detail === "string" && detail.length > 0)
    .slice(-1)[0];
  const caption = activeStep?.detail
    || lastDetail
    || (isStreaming
      ? "Mo ra de theo doi nhip suy luan hien tai."
      : "Mo ra de xem lai toan bo nhung gi da dien ra.");

  const timestamps = steps
    .flatMap((step) => [step.startTime, step.endTime])
    .filter((value): value is number => typeof value === "number");
  const durationText = timestamps.length >= 2
    ? formatDuration(Math.max(...timestamps) - Math.min(...timestamps))
    : null;

  return {
    steps,
    activeStep,
    completedCount,
    headline,
    caption,
    durationText,
  };
}

export function ThinkingJourneyBanner({
  blocks = [],
  phases = [],
  fallbackLabel = "",
  isStreaming = false,
  mode = "rich",
  expanded = false,
  onToggle,
}: ThinkingJourneyBannerProps) {
  const journey = buildJourney(blocks, phases, fallbackLabel, isStreaming);

  if (journey.steps.length === 0 && !fallbackLabel) {
    return null;
  }

  const Root = onToggle ? "button" : "div";

  return (
    <Root
      {...(onToggle ? { type: "button", onClick: onToggle, "aria-expanded": expanded } : {})}
      className={`thinking-journey thinking-journey--${mode} ${onToggle ? "thinking-journey--interactive" : ""}`}
    >
      <div className="thinking-journey__header">
        <span className="thinking-journey__state" aria-hidden="true">
          {isStreaming ? (
            <LoaderCircle size={14} className="thinking-journey__spinner" />
          ) : (
            <CheckCircle2 size={14} />
          )}
        </span>

        <div className="thinking-journey__body">
          <div className="thinking-journey__headline">{journey.headline}</div>
          <div className="thinking-journey__caption">{journey.caption}</div>

        </div>

        <div className="thinking-journey__meta">
          <span>{isStreaming ? "Dang xu ly" : "Hoan tat"}</span>
          <span>{isStreaming ? `${journey.completedCount}/${journey.steps.length} nhip` : `${journey.steps.length} nhip`}</span>
          {journey.durationText && <span>{journey.durationText}</span>}
        </div>

        {onToggle && (
          <ChevronDown
            size={14}
            className={`thinking-journey__chevron ${expanded ? "thinking-journey__chevron--open" : ""}`}
          />
        )}
      </div>

      {journey.steps.length > 0 && (
        <div className="thinking-journey__chips">
          {/* Sprint 234: 4→6 for multi-tool thinking */}
          {journey.steps.slice(0, 6).map((step) => (
            <span
              key={step.id}
              className={`thinking-journey__chip ${
                step.status === "active"
                  ? "thinking-journey__chip--active"
                  : "thinking-journey__chip--completed"
              }`}
            >
              <span className="thinking-journey__chip-dot" aria-hidden="true" />
              <span>{step.label}</span>
            </span>
          ))}
          {journey.steps.length > 4 && (
            <span className="thinking-journey__chip thinking-journey__chip--overflow">
              +{journey.steps.length - 4}
            </span>
          )}
        </div>
      )}
    </Root>
  );
}
