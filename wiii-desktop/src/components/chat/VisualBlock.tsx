import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import type {
  VisualBlockData,
  VisualControl,
  VisualPayload,
  VisualSessionState,
} from "@/api/types";
import { motion, AnimatePresence } from "motion/react";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { useChatStore } from "@/stores/chat-store";
import { useCodeStudioStore } from "@/stores/code-studio-store";
import { useUIStore } from "@/stores/ui-store";
import { trackVisualTelemetry } from "@/lib/visual-telemetry";
import { staggerContainer, staggerItem } from "@/lib/animations";
import InlineHtmlWidget from "@/components/common/InlineHtmlWidget";
import { InlineVisualFrame } from "@/components/common/InlineVisualFrame";
import { EmbeddedAppFrame } from "@/components/common/EmbeddedAppFrame";
import { RechartsRenderer } from "./RechartsRenderer";
import {
  DiagramAnnotationChip,
  DiagramCalloutPanel,
  DiagramConnectorArrow,
  DiagramCurveConnector,
  DiagramCenterpiece,
  DiagramFlowBridge,
  DiagramGroupBand,
  DiagramInsightPanel,
  DiagramLegend,
  DiagramMetricPill,
  DiagramNodeCard,
  DiagramSectionPill,
  DiagramStageFrame,
  DiagramStatusPill,
  DiagramStepBadge,
  paletteAt,
} from "@/components/chat/visual-primitives";
const asRecord = (value: unknown) => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const asList = (value: unknown) => Array.isArray(value) ? value : [];
const asText = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const asNumber = (value: unknown, fallback = 0) => typeof value === "number" && Number.isFinite(value) ? value : fallback;
const sessionIdOf = (visual: Pick<VisualPayload, "visual_session_id" | "id">) => visual.visual_session_id || visual.id;
const asIndexList = (value: unknown) => asList(value)
  .map((item) => asNumber(item, -1))
  .filter((item): item is number => Number.isInteger(item) && item >= 0);

// Editorial kickers were removed. Inline HTML/app visuals render in sandboxed frames,
// while the structured template fallback still exists for safety and rollback.

const CONTROL_LABELS: Record<string, string> = {
  focus_side: "Xem phần",
  current_step: "Bước hiện tại",
  show_values: "Hiện giá trị",
  active_layer: "Lớp đang xem",
  active_branch: "Nhánh đang xem",
  active_section: "Điểm nhấn",
  chart_style: "Kiểu biểu đồ",
  current_event: "Mốc đang xem",
  active_region: "Khu vực đang xem",
};

const CONTROL_OPTION_LABELS: Record<string, Record<string, string>> = {
  focus_side: {
    both: "Toàn cảnh",
    left: "Phía trái",
    right: "Phía phải",
  },
  active_layer: {
    all: "Tất cả",
  },
  active_branch: {
    all: "Tất cả",
  },
  active_section: {
    all: "Tất cả",
  },
  active_region: {
    all: "Tất cả",
  },
  chart_style: {
    bar: "Cột",
    line: "Đường",
    area: "Miền",
  },
};

const controlValueOf = (session: VisualSessionState | undefined, control: VisualControl) =>
  session?.controlValues?.[control.id]
  ?? control.value
  ?? (control.type === "toggle" ? false : undefined)
  ?? (control.type === "range" ? control.min ?? 0 : undefined)
  ?? control.options?.[0]?.value;

function normalizeNaturalText(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/gi, " ").replace(/\s+/g, " ").trim();
}

function cleanNarrativeSnippet(raw: string, visual: Pick<VisualPayload, "title">): string {
  if (!raw) return "";
  const cleaned = raw
    .replace(/^visual\s+[a-z_ ]+\s+de tom tat nhanh noi dung:\s*/i, "")
    .replace(/^visual\s+[a-z_ ]+:\s*/i, "")
    .replace(/^structured visual san sang:\s*/i, "")
    .replace(/^structured visual summary\s*/i, "")
    .replace(/^minh hoa da san sang:\s*/i, "")
    .replace(/^minh hoa nay\s*/i, "")
    .replace(/^summary\s*:\s*/i, "")
    .trim();
  if (!cleaned) return "";
  if (normalizeNaturalText(cleaned) === normalizeNaturalText(visual.title)) return "";
  return cleaned;
}

function cleanVisualSummary(visual: VisualPayload): string {
  const raw = visual.summary?.trim() || "";
  if (!raw) return "";
  const cleaned = cleanNarrativeSnippet(raw, visual);
  if (!cleaned) return "";
  return cleaned;
}

function cleanAnnotationTitle(value: string): string {
  const normalized = normalizeNaturalText(value);
  if (!normalized) return "Điểm nhấn";
  if (normalized === "summary" || normalized === "takeaway") return "Điểm chốt";
  if (/^annotation \d+$/.test(normalized)) return "Ghi chú";
  return value;
}

function getVisibleAnnotations(visual: VisualPayload) {
  return visual.annotations
    .map((annotation) => ({
      ...annotation,
      title: cleanAnnotationTitle(annotation.title),
      body: cleanNarrativeSnippet(annotation.body, visual),
    }))
    .filter((annotation) => annotation.title || annotation.body);
}

function getVisiblePanels(visual: VisualPayload) {
  return (visual.scene?.panels || [])
    .map((panel) => ({
      ...panel,
      title: cleanAnnotationTitle(panel.title),
      body: cleanNarrativeSnippet(panel.body || "", visual),
    }))
    .filter((panel) => panel.title || panel.body);
}

// Legacy visual kicker chrome is gone; inline prose now owns the narrative framing.

function controlLabel(control: VisualControl): string {
  return CONTROL_LABELS[control.id] || control.label || "Tùy chọn";
}

function controlOptionLabel(control: VisualControl, value: string, fallback: string): string {
  return CONTROL_OPTION_LABELS[control.id]?.[value] || fallback;
}

function renderItems(items: unknown[], muted = false) {
  if (items.length === 0) return null;
  return (
    <ul className={`space-y-2 text-sm text-text-secondary ${muted ? "opacity-45" : ""}`}>
      {items.map((item, index) => {
        if (typeof item === "string") {
          return <li key={`${item}-${index}`} className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 rounded-full bg-[var(--accent-orange)]" /><span>{item}</span></li>;
        }
        const record = asRecord(item);
        return <li key={`${asText(record.label)}-${index}`} className="flex gap-3"><span className="text-[var(--accent-orange)]">{asText(record.icon, "*")}</span><span>{asText(record.label)}{asText(record.label) && asText(record.value) ? ": " : ""}{asText(record.value)}</span></li>;
      })}
    </ul>
  );
}

function renderSignalChips(items: string[], paletteLine: string, muted = false) {
  if (items.length === 0) return null;
  return (
    <div className={`flex flex-wrap gap-2 ${muted ? "opacity-50" : ""}`}>
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border bg-white/78 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary shadow-[var(--shadow-sm)]"
          style={{ borderColor: paletteLine }}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function Comparison({ spec, focus }: { spec: Record<string, unknown>; focus: string }) {
  const columns = [asRecord(spec.left), asRecord(spec.right)];
  const axisLabel = asText(spec.axis_label, "Chi phí, bộ nhớ, độ chính xác");
  const comparisonTitle = asText(spec.title, `So sánh trên trục ${axisLabel.toLowerCase()}`);
  const comparisonCaption = asText(
    spec.caption,
    `Hai góc nhìn được đặt cạnh nhau để đọc nhanh sự đánh đổi quanh ${axisLabel.toLowerCase()}.`,
  );
  const legendItems = columns.map((side, index) => ({
    label: asText(side.title, index === 0 ? "Góc nhìn A" : "Góc nhìn B"),
    color: paletteAt(index).accent,
    detail: asText(side.subtitle),
  }));
  return <div className="space-y-4">
    <DiagramSectionPill className="hidden md:inline-flex">{axisLabel}</DiagramSectionPill>
    <DiagramStageFrame
      eyebrow="So sánh trực diện"
      title={comparisonTitle}
      caption={comparisonCaption}
      className="comparison-stage-frame"
    >
      <div className="space-y-5">
        <DiagramLegend items={legendItems} />
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_112px_minmax(0,1fr)]">
      {columns.map((side, index) => {
        const palette = paletteAt(index);
        const sideKey = index === 0 ? "left" : "right";
        const muted = focus !== "both" && focus !== sideKey;
        const highlight = asText(side.highlight) || asText(side.note) || asText(side.description);
        const items = asList(side.items);
        const stringItems = items.filter((item): item is string => typeof item === "string").slice(0, 3);
        const hasOnlyStringItems = stringItems.length > 0 && stringItems.length === items.length;
        return (
          <DiagramNodeCard
            key={sideKey}
            palette={palette}
            eyebrow={asText(side.subtitle, index === 0 ? "Bên trái" : "Bên phải")}
            title={asText(side.title, index === 0 ? "Phương án A" : "Phương án B")}
            badge={index === 0 ? "Góc nhìn A" : "Góc nhìn B"}
            muted={muted}
            emphasis={highlight ? (
              <>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-tertiary">Điểm để nhìn nhanh</p>
                <p className="mt-2 text-sm leading-6 text-text-secondary">{highlight}</p>
              </>
            ) : undefined}
          >
            <div className="space-y-4">
              {renderSignalChips(stringItems, palette.line, muted)}
              {!hasOnlyStringItems ? renderItems(items, muted) : null}
            </div>
          </DiagramNodeCard>
        );
      })}

      <DiagramFlowBridge label={axisLabel} />

      <div className="hidden" aria-hidden="true">
        <div className="flex h-full flex-col items-center justify-center gap-4">
          <div className="grid h-14 w-14 place-items-center rounded-full border border-[rgba(174,86,48,0.16)] bg-white/88 shadow-[var(--shadow-md)] text-[var(--accent-orange)]">
            →
          </div>
          <div className="max-w-[7rem] text-center text-[11px] font-medium uppercase tracking-[0.16em] text-text-tertiary">
            {axisLabel}
          </div>
        </div>
      </div>
        </div>
      </div>
    </DiagramStageFrame>
  </div>;
}

function Process({ spec, currentStep, reduced }: { spec: Record<string, unknown>; currentStep: number; reduced: boolean }) {
  const steps = asList(spec.steps);
  const activeIndex = Math.max(0, Math.min(currentStep - 1, steps.length - 1));
  const activeItem = asRecord(steps[activeIndex]);
  const activePalette = paletteAt(activeIndex);
  const processTitle = asText(spec.title, steps.length > 0 ? `${steps.length} bước chính` : "Quy trình từng bước");
  const processCaption = asText(
    spec.caption,
    asText(activeItem.description, "Mỗi bước đưa bạn đến một trạng thái rõ ràng hơn của quy trình."),
  );
  return <div className="space-y-5">
    <DiagramSectionPill tone="neutral">Dòng chảy từng bước</DiagramSectionPill>
    <DiagramStageFrame
      eyebrow="Quy trình giải thích"
      title={processTitle}
      caption={processCaption}
      className="process-stage-frame"
    >
      <div className="space-y-5">
        <div className="relative">
          {steps.length > 1 && (
            <div
              aria-hidden="true"
              className="absolute left-7 right-7 top-6 hidden h-px bg-[linear-gradient(90deg,rgba(199,91,57,0.16),rgba(44,132,219,0.35),rgba(21,154,138,0.22))] md:block"
            />
          )}
          <div className="grid gap-3 lg:grid-cols-[repeat(var(--steps),minmax(0,1fr))]" style={{ ["--steps" as string]: String(Math.max(steps.length, 1)) }}>
            {steps.map((step, index) => {
              const item = asRecord(step);
              const palette = paletteAt(index);
              const active = currentStep === index + 1;
              return (
                <div key={index} className="relative">
                  <article
                    className="relative rounded-[24px] border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(249,246,239,0.92))] p-5 shadow-[var(--shadow-sm)] transition-[opacity,transform] duration-300"
                    style={{
                      borderColor: palette.line,
                      opacity: active ? 1 : 0.52,
                      transform: active && !reduced ? "translateY(-3px)" : undefined,
                      boxShadow: active ? "var(--shadow-md)" : "var(--shadow-sm)",
                    }}
                  >
                    <div className="mb-4 flex items-start gap-3">
                      <DiagramStepBadge palette={palette} label={asText(item.icon, String(index + 1))} />
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-tertiary">Step {index + 1}</p>
                        <h4 className="mt-1 font-serif text-[clamp(1.22rem,4.6vw,1.55rem)] leading-tight text-text">{asText(item.title, `Step ${index + 1}`)}</h4>
                      </div>
                    </div>
                    {asText(item.description) && <p className="text-sm leading-6 text-text-secondary">{asText(item.description)}</p>}
                    {renderSignalChips(asList(item.signals).map((signal) => asText(signal)).filter(Boolean), palette.line, !active)}
                  </article>
                  {index < steps.length - 1 ? (
                    <>
                      <DiagramConnectorArrow
                        palette={palette}
                        orientation="vertical"
                        className="mt-3 flex justify-center lg:hidden"
                      />
                      <DiagramConnectorArrow
                        palette={palette}
                        orientation="horizontal"
                        className="absolute -right-7 top-[4.5rem] hidden lg:flex"
                      />
                    </>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
        {steps.length > 1 ? (
          <>
            <DiagramLegend
              items={[
                {
                  label: "Bước đang mở",
                  color: activePalette.accent,
                  detail: asText(activeItem.title, `Step ${activeIndex + 1}`),
                },
                {
                  label: "Dòng chảy",
                  color: paletteAt(Math.min(activeIndex + 1, Math.max(steps.length - 1, 0))).accent,
                  detail: "Tinh tiến dần",
                },
              ]}
            />
            <DiagramFlowBridge label="Tinh tiến dần" compact />
          </>
        ) : null}
      </div>
    </DiagramStageFrame>

    {steps.length > 0 && (
      <DiagramCalloutPanel
        palette={activePalette}
        eyebrow="Điểm cần chú ý"
        title={asText(activeItem.title, `Step ${activeIndex + 1}`)}
        accentLabel={activeIndex + 1}
        body={asText(activeItem.description) ? (
          <p>{asText(activeItem.description)}</p>
        ) : undefined}
      />
    )}
  </div>;
}

function Matrix({ spec, showValues }: { spec: Record<string, unknown>; showValues: boolean }) {
  const rows = asList(spec.rows).map((value) => asText(value));
  const cols = asList(spec.cols).map((value) => asText(value));
  const cells = asList(spec.cells);
  return <div className="overflow-x-auto"><table className="border-separate border-spacing-2"><thead><tr><th />{cols.map((col) => <th key={col} className="px-2 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-text-tertiary">{col}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={row}><th className="px-2 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-tertiary">{row}</th>{cols.map((col, colIndex) => {
    const value = asNumber(asList(cells[rowIndex])[colIndex], 0);
    const opacity = Math.max(0.12, Math.min(1, value));
    return <td key={`${row}-${col}`} className="h-14 w-16 rounded-[16px] border text-center text-sm font-semibold shadow-[var(--shadow-sm)]" style={{ borderColor: "rgba(199,91,57,0.22)", background: `rgba(199,91,57,${opacity})`, color: opacity > 0.45 ? "#fff" : "var(--text)" }}>{showValues ? value.toFixed(1) : ""}</td>;
  })}</tr>)}</tbody></table>{asText(spec.caption) && <p className="mt-3 text-sm text-text-secondary">{asText(spec.caption)}</p>}</div>;
}

function Cards({ items, keyName, focusId, labelPrefix }: { items: unknown[]; keyName: string; focusId: string; labelPrefix: string }) {
  return <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{items.map((item, index) => {
    const record = asRecord(item);
    const palette = paletteAt(index);
    const itemId = `${keyName}-${index + 1}`;
    const muted = focusId !== "all" && focusId !== itemId;
    return <div key={itemId} className="rounded-[20px] border p-5 shadow-[var(--shadow-sm)]" style={{ background: palette.soft, borderColor: palette.line, opacity: muted ? 0.35 : 1 }}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: palette.ink }}>{asText(record.title) || asText(record.name) || asText(record.label, `${labelPrefix} ${index + 1}`)}</p>
      {record.components ? <div className="mt-3 flex flex-wrap gap-2">{asList(record.components).map((part, partIndex) => <span key={`${partIndex}-${String(part)}`} className="rounded-full border bg-white px-3 py-1.5 text-sm font-medium shadow-[var(--shadow-sm)]" style={{ borderColor: palette.line }}>{String(part)}</span>)}</div> : null}
      {record.items ? <div className="mt-3">{renderItems(asList(record.items), muted)}</div> : null}
      {(asText(record.content) || asText(record.description)) && <p className="mt-3 text-sm leading-6 text-text-secondary">{asText(record.content) || asText(record.description)}</p>}
      {asText(record.value) && <p className="mt-4 font-serif text-4xl text-text">{asText(record.value)}</p>}
    </div>;
  })}</div>;
}

type ArchitectureBand = {
  id: string;
  label: string;
  detail: string;
  tone: "accent" | "neutral" | "success";
  layerIndexes: number[];
};

function getArchitectureBands(spec: Record<string, unknown>, layers: unknown[]): ArchitectureBand[] {
  const explicitGroups = asList(spec.groups)
    .map((group, index) => {
      const record = asRecord(group);
      const indexedLayers = asIndexList(record.layer_indexes)
        .filter((layerIndex) => layerIndex < layers.length);
      const resolvedLayerIndexes = indexedLayers.length > 0
        ? indexedLayers
        : asList(record.layer_ids)
          .map((layerId) => {
            const targetId = asText(layerId).toLowerCase();
            if (!targetId) return -1;
            return layers.findIndex((layer) => {
              const current = asRecord(layer);
              return [current.id, current.name, current.title]
                .map((value) => asText(value).toLowerCase())
                .includes(targetId);
            });
          })
          .filter((layerIndex): layerIndex is number => layerIndex >= 0);

      const layerIndexes = Array.from(new Set(resolvedLayerIndexes)).sort((left, right) => left - right);
      if (layerIndexes.length === 0) return null;

      const tone = ["accent", "neutral", "success"].includes(asText(record.tone))
        ? asText(record.tone) as ArchitectureBand["tone"]
        : (index === 0 ? "accent" : index === 1 ? "neutral" : "success");

      return {
        id: asText(record.id, `group-${index + 1}`),
        label: asText(record.title, `Cụm ${index + 1}`),
        detail: asText(record.detail, asText(record.description)),
        tone,
        layerIndexes,
      } satisfies ArchitectureBand;
    })
    .filter((band): band is ArchitectureBand => Boolean(band));

  if (explicitGroups.length > 0) return explicitGroups;

  if (layers.length === 0) return [];
  if (layers.length === 1) {
    return [{
      id: "band-core",
      label: "Lớp trung tâm",
      detail: "Một lớp gồm toàn bộ vai trò chính của visual runtime.",
      tone: "accent" as const,
      layerIndexes: [0],
    }];
  }
  if (layers.length === 2) {
    return [
      {
        id: "band-entry",
        label: "Lớp nhập",
        detail: "Nhận yêu cầu, điều hướng context, và mở flow giải thích.",
        tone: "accent" as const,
        layerIndexes: [0],
      },
      {
        id: "band-output",
        label: "Lớp đầu ra",
        detail: "Tổng hợp, render, và đưa kết quả trở lại màn hình.",
        tone: "success" as const,
        layerIndexes: [1],
      },
    ];
  }

  return [
    {
      id: "band-entry",
      label: "Lớp nhập",
      detail: "Nhận input và đặt nhịp cho toàn bộ luồng giải thích.",
      tone: "accent" as const,
      layerIndexes: [0],
    },
    {
      id: "band-core",
      label: "Vùng điều phối",
      detail: "Các lớp giữa phối hợp với nhau để render, patch, và giữ visual session ổn định.",
      tone: "neutral" as const,
      layerIndexes: layers.slice(1, -1).map((_, index) => index + 1),
    },
    {
      id: "band-output",
      label: "Lớp đầu ra",
      detail: "Phát visual và prose thành một câu trả lời liền mạch.",
      tone: "success" as const,
      layerIndexes: [layers.length - 1],
    },
  ].filter((band) => band.layerIndexes.length > 0);
}

function Architecture({ spec, focusId }: { spec: Record<string, unknown>; focusId: string }) {
  const layers = asList(spec.layers);
  const bands = getArchitectureBands(spec, layers);
  const architectureTitle = asText(spec.title, "Dòng chảy qua các lớp hệ thống");
  const architectureCaption = asText(
    spec.caption,
    "Mỗi lớp có một vai trò riêng và nối với nhau bằng đường chảy rõ ràng.",
  );
  return <div className="space-y-4">
    <DiagramSectionPill tone="neutral">Hệ thống nhiều lớp</DiagramSectionPill>
    <DiagramStageFrame
      eyebrow="Kiến trúc hệ thống"
      title={architectureTitle}
      caption={architectureCaption}
      className="architecture-stage-frame"
    >
      <div className="space-y-4">
        {bands.map((band, bandIndex) => (
          <div key={band.id} className="space-y-4">
            <DiagramGroupBand
              label={band.label}
              detail={band.detail}
              tone={band.tone}
            >
              {band.layerIndexes.map((layerIndex, localIndex) => {
                const record = asRecord(layers[layerIndex]);
                const palette = paletteAt(layerIndex);
                const layerId = `layer-${layerIndex + 1}`;
                const muted = focusId !== "all" && focusId !== layerId;
                return <div key={layerId} className="relative md:pl-16">
                  {localIndex < band.layerIndexes.length - 1 && (
                    <DiagramConnectorArrow
                      palette={palette}
                      orientation="vertical"
                      className="absolute left-[0.5rem] top-full hidden -translate-x-1/2 md:flex"
                    />
                  )}
                  <div className="absolute left-0 top-7 hidden md:block" aria-hidden="true">
                    <DiagramStepBadge palette={palette} label={layerIndex + 1} />
                  </div>
                  <DiagramNodeCard
                    palette={palette}
                    eyebrow={`Lớp ${layerIndex + 1}`}
                    title={asText(record.name) || asText(record.title, `Layer ${layerIndex + 1}`)}
                    badge={asText(record.value, `Tầng ${layerIndex + 1}`)}
                    muted={muted}
                  >
                    <div className="space-y-4">
                      {(asText(record.content) || asText(record.description)) && <p className="max-w-3xl text-sm leading-7 text-text-secondary">{asText(record.content) || asText(record.description)}</p>}
                      {record.components ? <div className="flex flex-wrap gap-2">{asList(record.components).map((part, partIndex) => <span key={`${partIndex}-${String(part)}`} className="rounded-full border bg-white/78 px-3 py-1.5 text-sm font-medium text-text shadow-[var(--shadow-sm)]" style={{ borderColor: palette.line }}>{String(part)}</span>)}</div> : null}
                      {record.items ? renderItems(asList(record.items), muted) : null}
                    </div>
                  </DiagramNodeCard>
                </div>;
              })}
            </DiagramGroupBand>
            {bandIndex < bands.length - 1 ? <DiagramFlowBridge label="Chuyển vùng" compact /> : null}
          </div>
        ))}
      </div>
    </DiagramStageFrame>
  </div>;
}

function Concept({ spec, focusId }: { spec: Record<string, unknown>; focusId: string }) {
  const center = asRecord(spec.center);
  const branches = asList(spec.branches);
  const centerTitle = asText(center.title, "Core concept");
  const conceptTitleCandidate = asText(spec.title, "Bản đồ mở rộng");
  const conceptTitle = normalizeNaturalText(conceptTitleCandidate) === normalizeNaturalText(centerTitle)
    ? "Bản đồ mở rộng"
    : conceptTitleCandidate;
  const conceptCaption = asText(
    spec.caption,
    "Bắt đầu từ ý trung tâm, sau đó mở rộng từng nhánh để thấy toàn bộ bức tranh.",
  );
  return <div className="space-y-6">
    <DiagramSectionPill tone="neutral">Ý trung tâm và các nhánh</DiagramSectionPill>
    <DiagramStageFrame
      eyebrow="Bản đồ khái niệm"
      title={conceptTitle}
      caption={conceptCaption}
      className="concept-stage-frame"
    >
      <div className="space-y-6">
        <div className="mx-auto max-w-2xl">
          <DiagramCenterpiece
            palette={paletteAt(0)}
            eyebrow="Ý trung tâm"
            title={centerTitle}
            body={asText(center.description) ? <p>{asText(center.description)}</p> : undefined}
          />
        </div>

        <div className="relative pt-6">
          {branches.length > 0 && <div aria-hidden="true" className="absolute left-1/2 top-0 h-6 w-px -translate-x-1/2 bg-[linear-gradient(180deg,rgba(174,86,48,0.35),rgba(174,86,48,0))]" />}
          {branches.length > 1 && <div aria-hidden="true" className="absolute left-[16%] right-[16%] top-6 hidden h-px bg-[linear-gradient(90deg,rgba(174,86,48,0.08),rgba(174,86,48,0.45),rgba(44,132,219,0.35),rgba(174,86,48,0.08))] md:block" />}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {branches.map((branch, index) => {
              const record = asRecord(branch);
              const palette = paletteAt(index);
              const branchId = `branch-${index + 1}`;
              const muted = focusId !== "all" && focusId !== branchId;
              const curveDirection = branches.length === 2
                ? (index === 0 ? "left" : "right")
                : index <= Math.floor((branches.length - 1) / 2) ? "left" : "right";
              return <div key={branchId} className="relative">
                <div className="absolute inset-x-0 top-0 hidden -translate-y-full md:block" aria-hidden="true">
                  {branches.length % 2 === 1 && index === Math.floor(branches.length / 2) ? (
                    <>
                      <div className="mx-auto h-4 w-px bg-[linear-gradient(180deg,rgba(174,86,48,0.35),rgba(174,86,48,0))]" />
                      <div className="mx-auto h-3 w-3 -translate-y-1/2 rounded-full border border-white bg-[var(--accent-orange)]" />
                    </>
                  ) : (
                    <DiagramCurveConnector palette={palette} direction={curveDirection} />
                  )}
                </div>
                <DiagramNodeCard
                  palette={palette}
                  eyebrow={`Nhánh ${index + 1}`}
                  title={asText(record.title, `Branch ${index + 1}`)}
                  muted={muted}
                  emphasis={(asText(record.content) || asText(record.description)) ? (
                    <p className="text-sm leading-7 text-text-secondary">{asText(record.content) || asText(record.description)}</p>
                  ) : undefined}
                >
                  {record.items ? renderItems(asList(record.items), muted) : null}
                </DiagramNodeCard>
              </div>;
            })}
          </div>
        </div>
      </div>
    </DiagramStageFrame>
  </div>;
}

function normalizeChartSpec(spec: Record<string, unknown>) {
  const labels = asList(spec.labels).map((value) => asText(value)).filter(Boolean);
  const datasets = asList(spec.datasets).map((value) => asRecord(value));
  if (labels.length > 0 && datasets.length > 0) {
    return { labels, datasets };
  }

  const rows = asList(spec.data)
    .map((value) => asRecord(value))
    .filter((row) => Object.keys(row).length > 0);

  if (rows.length > 0) {
    return {
      labels: rows.map((row, index) => asText(row.label, asText(row.name, asText(row.x, asText(row.category, `Item ${index + 1}`))))),
      datasets: [
        {
          label: asText(spec.series_label, asText(spec.dataset_label, asText(spec.title, "Du lieu"))),
          data: rows.map((row) => asNumber(row.value ?? row.y, 0)),
          colors: rows.map((row) => asText(row.color)),
        },
      ],
    };
  }

  const rawValues = asList(spec.data);
  return {
    labels: rawValues.map((_, index) => `Item ${index + 1}`),
    datasets: [
      {
        label: asText(spec.series_label, asText(spec.dataset_label, asText(spec.title, "Du lieu"))),
        data: rawValues.map((value) => asNumber(value, 0)),
      },
    ],
  };
}

function Chart({ spec, style }: { spec: Record<string, unknown>; style: string }) {
  const normalized = normalizeChartSpec(spec);
  const labels = normalized.labels;
  const dataset = asRecord(normalized.datasets[0]);
  const values = asList(dataset.data).map((value) => asNumber(value, 0));
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
  const peakIndex = values.findIndex((value) => value === max);
  const primary = paletteAt(1);
  const secondary = paletteAt(0);
  const points = values.map((value, index) => ({ x: 42 + (index * 292) / Math.max(values.length - 1, 1), y: 180 - (value / max) * 124, value, label: labels[index] || `Item ${index + 1}` }));
  const line = points.map((point) => `${point.x},${point.y}`).join(" ");
  const seriesLabel = asText(dataset.label, asText(spec.series_label, "Dữ liệu"));
  const peakPoint = points[peakIndex] || points[0];
  const chartTitle = asText(spec.title, seriesLabel);
  const chartCaption = asText(spec.caption, "Biểu đồ này nhấn vào sự thay đổi của giá trị theo từng mốc.");
  const yMarkers = [max, average, min].map((value) => ({
    value,
    y: 180 - (value / max) * 124,
  }));

  return <div className="space-y-4">
    <DiagramSectionPill tone="neutral">Đọc xu hướng theo trục</DiagramSectionPill>
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
      <DiagramStageFrame
        eyebrow="Biểu đồ giải thích"
        title={chartTitle}
        caption={chartCaption}
      >
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <DiagramStatusPill label="Series" detail={seriesLabel} tone="accent" />
            <DiagramStatusPill label="Peak" detail={peakPoint?.label || "Mốc nổi bật"} tone="warning" />
            <DiagramStatusPill label="Average" detail={average.toFixed(1)} tone="neutral" />
          </div>
          <svg viewBox="0 0 360 220" className="w-full">
            {[40, 80, 120, 160, 200].map((y) => (
              <line key={y} x1="36" y1={y} x2="336" y2={y} stroke="rgba(31,41,55,0.08)" strokeDasharray="4 6" />
            ))}
            {yMarkers.map((marker, index) => (
              <g key={`${marker.value}-${index}`}>
                <text x="30" y={marker.y + 4} textAnchor="end" className="fill-[var(--text-tertiary)] text-[9px] font-semibold">
                  {marker.value.toFixed(1)}
                </text>
                <line x1="36" y1={marker.y} x2="336" y2={marker.y} stroke="rgba(31,41,55,0.06)" strokeDasharray="3 6" />
              </g>
            ))}
            <line x1="36" y1="20" x2="36" y2="184" stroke="rgba(31,41,55,0.18)" strokeWidth="2" />
            <line x1="36" y1="184" x2="336" y2="184" stroke="rgba(31,41,55,0.18)" strokeWidth="2" />
            {peakPoint ? (
              <line
                x1={peakPoint.x}
                y1={peakPoint.y}
                x2={peakPoint.x}
                y2="184"
                stroke={secondary.accent}
                strokeWidth="1.5"
                strokeDasharray="4 5"
                opacity="0.72"
              />
            ) : null}
            {style === "line" || style === "area" ? (
              <>
                {style === "area" && (
                  <path
                    d={`M 42 184 ${points.map((point) => `L ${point.x} ${point.y}`).join(" ")} L ${points[points.length - 1]?.x || 42} 184 Z`}
                    fill="rgba(44,132,219,0.16)"
                  />
                )}
                <polyline fill="none" stroke={primary.accent} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" points={line} />
                {points.map((point, index) => (
                  <circle
                    key={`${point.label}-dot`}
                    cx={point.x}
                    cy={point.y}
                    r={index === peakIndex ? 6.5 : 4.5}
                    fill={index === peakIndex ? secondary.accent : primary.accent}
                    stroke="white"
                    strokeWidth="2"
                  />
                ))}
              </>
            ) : (
              points.map((point, index) => (
                <rect
                  key={point.label}
                  x={point.x - 14}
                  y={point.y}
                  width="28"
                  height={184 - point.y}
                  rx="10"
                  fill={asText(asList(dataset.colors)[index], index === peakIndex ? secondary.accent : primary.accent)}
                />
              ))
            )}
            {peakPoint ? (
              <>
                <rect
                  x={Math.max(58, peakPoint.x - 36)}
                  y={Math.max(18, peakPoint.y - 42)}
                  width="72"
                  height="22"
                  rx="11"
                  fill="rgba(255,255,255,0.95)"
                  stroke={secondary.accent}
                  strokeWidth="1.2"
                />
                <text
                  x={Math.max(94, peakPoint.x)}
                  y={Math.max(32, peakPoint.y - 27)}
                  textAnchor="middle"
                  className="fill-[var(--accent-orange)] text-[9px] font-semibold uppercase tracking-[0.14em]"
                >
                  Điểm nổi bật
                </text>
              </>
            ) : null}
            {points.map((point) => (
              <g key={`${point.label}-text`}>
                <text x={point.x} y={point.y - 10} textAnchor="middle" className="fill-[var(--text)] text-[10px] font-semibold">{point.value}</text>
                <text x={point.x} y="206" textAnchor="middle" className="fill-[var(--text-secondary)] text-[10px]">{point.label}</text>
              </g>
            ))}
          </svg>
          <DiagramLegend
            items={[
              { label: seriesLabel, color: primary.accent },
              { label: "Điểm cao nhất", color: secondary.accent, detail: peakPoint?.label || "Peak" },
            ]}
          />
        </div>
      </DiagramStageFrame>

      <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
        <DiagramMetricPill label="Giá trị cao nhất" value={max.toFixed(1)} tone="accent" />
        <DiagramMetricPill label="Trung bình" value={average.toFixed(1)} tone="neutral" />
        <DiagramMetricPill label="Biên độ" value={`${Math.abs(max - min).toFixed(1)}`} tone="success" />
        <DiagramInsightPanel
          tone="accent"
          eyebrow="Điểm nên nhìn"
          title={points[peakIndex]?.label || "Điểm nổi bật"}
          body={<p>{style === "area" ? "Biên độ cho thấy xu hướng tích lũy rõ hơn qua từng mốc." : "Giá trị này là điểm cần tập trung để đọc xu hướng toàn cảnh."}</p>}
          className="sm:col-span-3 xl:col-span-1"
        />
      </div>
    </div>
  </div>;
}

function Timeline({ spec, current }: { spec: Record<string, unknown>; current: number }) {
  const events = asList(spec.events);
  const activeIndex = Math.max(0, Math.min(current - 1, events.length - 1));
  const activeItem = asRecord(events[activeIndex]);
  const activePalette = paletteAt(activeIndex);
  const timelineTitle = asText(spec.title, "Các mốc chính");
  const timelineCaption = asText(spec.caption, "Đọc dòng thay đổi theo thứ tự thời gian.");
  return <div className="space-y-4">
    <DiagramSectionPill tone="neutral">Theo dòng thời gian</DiagramSectionPill>
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
      <DiagramStageFrame eyebrow="Dòng thời gian" title={timelineTitle} caption={timelineCaption}>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <DiagramStatusPill label="Mốc đang mở" detail={asText(activeItem.title, `Milestone ${activeIndex + 1}`)} tone="accent" />
            <DiagramStatusPill label="Tổng mốc" detail={String(events.length)} tone="neutral" />
          </div>
          <div className="grid gap-3">
          {events.map((event, index) => {
            const item = asRecord(event);
            const active = current === index + 1;
            const palette = paletteAt(index);
            const tone = active ? "accent" : index < activeIndex ? "success" : "neutral";
            const statusLabel = active ? "Đang mở" : index < activeIndex ? "Đã đi qua" : "Sắp tới";
            return <div key={index} className="grid gap-3 md:grid-cols-[auto_1fr]">
              <div className="grid place-items-start justify-items-center pt-1">
                <div className="grid h-8 w-8 place-items-center rounded-full text-xs font-bold text-white shadow-[var(--shadow-sm)]" style={{ background: active ? palette.accent : "rgba(148,163,184,0.68)" }}>
                  {index + 1}
                </div>
                {index < events.length - 1 && <div className="mt-2 h-full min-h-12 w-px bg-[linear-gradient(180deg,rgba(174,86,48,0.28),rgba(148,163,184,0.22))]" />}
              </div>
              <div className="rounded-[20px] border bg-white/92 p-5 shadow-[var(--shadow-sm)]" style={{ borderColor: palette.line, opacity: active ? 1 : 0.52 }}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: palette.ink }}>{asText(item.date, `Milestone ${index + 1}`)}</p>
                  <DiagramStatusPill label={statusLabel} tone={tone} />
                </div>
                <h4 className="mt-2 font-serif text-2xl text-text">{asText(item.title, `Milestone ${index + 1}`)}</h4>
                {asText(item.description) && <p className="mt-3 text-sm leading-6 text-text-secondary">{asText(item.description)}</p>}
              </div>
            </div>;
          })}
          </div>
        </div>
      </DiagramStageFrame>
      {events.length > 0 ? (
        <DiagramCalloutPanel
          palette={activePalette}
          eyebrow="Mốc đang xem"
          title={asText(activeItem.title, `Milestone ${activeIndex + 1}`)}
          accentLabel={activeIndex + 1}
          body={asText(activeItem.description) ? <p>{asText(activeItem.description)}</p> : undefined}
        />
      ) : null}
    </div>
  </div>;
}

function MapLite({ spec, focusId }: { spec: Record<string, unknown>; focusId: string }) {
  const regions = asList(spec.regions);
  const activeIndex = focusId === "all" ? 0 : Math.max(0, regions.findIndex((_, index) => `region-${index + 1}` === focusId));
  const activeRecord = asRecord(regions[activeIndex]);
  const activePalette = paletteAt(activeIndex);
  const mapTitle = asText(spec.title, "Cụm khu vực cần theo dõi");
  const mapCaption = asText(spec.caption, "Tập trung vào từng khu vực để đọc tín hiệu nổi bật.");
  return <div className="space-y-4">
    <DiagramSectionPill tone="neutral">Theo từng khu vực</DiagramSectionPill>
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
      <DiagramStageFrame eyebrow="Bản đồ rút gọn" title={mapTitle} caption={mapCaption}>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <DiagramStatusPill label="Khu vực đang xem" detail={asText(activeRecord.title) || asText(activeRecord.name) || asText(activeRecord.label, `Region ${activeIndex + 1}`)} tone="accent" />
            <DiagramStatusPill label="Tổng cụm" detail={String(regions.length)} tone="neutral" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
          {regions.map((region, index) => {
            const record = asRecord(region);
            const palette = paletteAt(index);
            const regionId = `region-${index + 1}`;
            const active = focusId === "all" ? index === activeIndex : focusId === regionId;
            return (
              <div
                key={regionId}
                className="rounded-[22px] border px-4 py-4 shadow-[var(--shadow-sm)] transition-[opacity,transform] duration-300"
                style={{
                  borderColor: palette.line,
                  background: `linear-gradient(180deg, ${palette.soft}, rgba(255,255,255,0.95))`,
                  opacity: active ? 1 : 0.58,
                  transform: active ? "translateY(-2px)" : "translateY(0)",
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: palette.ink }}>
                        Khu vực {index + 1}
                      </p>
                      <DiagramStatusPill label={active ? "Tập trung" : "Theo dõi"} tone={active ? "accent" : "neutral"} />
                    </div>
                    <h4 className="mt-1 font-serif text-[1.35rem] leading-tight text-text">{asText(record.title) || asText(record.name) || asText(record.label, `Region ${index + 1}`)}</h4>
                  </div>
                  <span className="h-3 w-3 rounded-full" style={{ background: palette.accent }} aria-hidden="true" />
                </div>
                {(asText(record.content) || asText(record.description)) && (
                  <p className="mt-3 text-sm leading-6 text-text-secondary">{asText(record.content) || asText(record.description)}</p>
                )}
                {record.items ? <div className="mt-4">{renderItems(asList(record.items), !active)}</div> : null}
              </div>
            );
          })}
          </div>
        </div>
      </DiagramStageFrame>
      {regions.length > 0 ? (
        <DiagramCalloutPanel
          palette={activePalette}
          eyebrow="Khu vực đang xem"
          title={asText(activeRecord.title) || asText(activeRecord.name) || asText(activeRecord.label, `Region ${activeIndex + 1}`)}
          accentLabel={activeIndex + 1}
          body={(asText(activeRecord.content) || asText(activeRecord.description)) ? <p>{asText(activeRecord.content) || asText(activeRecord.description)}</p> : undefined}
        />
      ) : null}
    </div>
  </div>;
}

/* Structured template fallback. Still used when renderer_kind === "template". */
function renderStructured(visual: VisualPayload, session: VisualSessionState | undefined, reduced: boolean) {
  const spec = asRecord(visual.spec);
  let content: ReactNode = null;
  switch (visual.type) {
    case "comparison": content = <Comparison spec={spec} focus={String(controlValueOf(session, visual.controls.find((item) => item.id === "focus_side") || { id: "focus_side", type: "chips", label: "Focus", value: "both" }))} />; break;
    case "process": content = <Process spec={spec} reduced={reduced} currentStep={Number(controlValueOf(session, visual.controls.find((item) => item.id === "current_step") || { id: "current_step", type: "range", label: "Step", value: 1 }))} />; break;
    case "matrix": content = <Matrix spec={spec} showValues={Boolean(controlValueOf(session, visual.controls.find((item) => item.id === "show_values") || { id: "show_values", type: "toggle", label: "Show", value: false }))} />; break;
    case "architecture": content = <Architecture spec={spec} focusId={String(controlValueOf(session, visual.controls.find((item) => item.id === "active_layer") || { id: "active_layer", type: "chips", label: "Layer", value: "all" }))} />; break;
    case "concept": content = <Concept spec={spec} focusId={String(controlValueOf(session, visual.controls.find((item) => item.id === "active_branch") || { id: "active_branch", type: "chips", label: "Branch", value: "all" }))} />; break;
    case "infographic": content = <div className="space-y-5">{asList(spec.stats).length > 0 && <Cards items={asList(spec.stats)} keyName="stat" focusId="all" labelPrefix="Stat" />}<Cards items={asList(spec.sections)} keyName="section" focusId={String(controlValueOf(session, visual.controls.find((item) => item.id === "active_section") || { id: "active_section", type: "chips", label: "Section", value: "all" }))} labelPrefix="Section" /></div>; break;
    case "chart": content = <Chart spec={spec} style={String(controlValueOf(session, visual.controls.find((item) => item.id === "chart_style") || { id: "chart_style", type: "chips", label: "Chart style", value: "bar" }))} />; break;
    case "timeline": content = <Timeline spec={spec} current={Number(controlValueOf(session, visual.controls.find((item) => item.id === "current_event") || { id: "current_event", type: "range", label: "Current", value: 1 }))} />; break;
    case "map_lite": content = <MapLite spec={spec} focusId={String(controlValueOf(session, visual.controls.find((item) => item.id === "active_region") || { id: "active_region", type: "chips", label: "Region", value: "all" }))} />; break;
    default: return null;
  }
  return <motion.div variants={staggerItem}>{content}</motion.div>;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function ControlBar({
  visual,
  session,
  onChange,
  embedded = false,
}: {
  visual: VisualPayload;
  session?: VisualSessionState;
  onChange: (controlId: string, value: string | number | boolean, focusedNodeId?: string) => void;
  embedded?: boolean;
}) {
  if (!visual.controls.length) return null;
  return <div className={`visual-control-bar mb-6 flex flex-col gap-4 rounded-[24px] border border-[color-mix(in_srgb,var(--border)_72%,white)] bg-[linear-gradient(180deg,rgba(255,255,255,0.82),rgba(249,246,239,0.74))] p-4 shadow-[var(--shadow-sm)] ${embedded ? "visual-control-bar--embedded" : ""}`.trim()}>{visual.controls.map((control) => {
    const value = controlValueOf(session, control);
    if (control.type === "toggle") return <label key={control.id} className="flex items-center justify-between gap-3 text-sm font-medium text-text"><span>{controlLabel(control)}</span><button type="button" aria-pressed={Boolean(value)} className={`min-h-[40px] rounded-full px-3.5 py-1.5 text-xs font-semibold ${value ? "bg-[var(--accent-orange)] text-white" : "border border-[var(--border)] bg-white text-text-secondary"}`} onClick={() => onChange(control.id, !Boolean(value))}>{value ? "Bật" : "Tắt"}</button></label>;
    if (control.type === "range") return <label key={control.id} className="space-y-2 text-sm font-medium text-text"><div className="flex items-center justify-between gap-3"><span>{controlLabel(control)}</span><span className="text-xs text-text-tertiary">{String(value ?? control.min ?? 0)}</span></div><input type="range" min={control.min} max={control.max} step={control.step} value={Number(value ?? control.min ?? 0)} className="w-full accent-[var(--accent-orange)]" onChange={(event) => onChange(control.id, Number(event.currentTarget.value), `${control.id}:${event.currentTarget.value}`)} /></label>;
    if (control.type === "select") return <label key={control.id} className="space-y-2 text-sm font-medium text-text"><span>{controlLabel(control)}</span><select value={String(value ?? "")} onChange={(event) => onChange(control.id, event.currentTarget.value)} className="min-h-[42px] rounded-[14px] border border-[var(--border)] bg-white px-3 py-2 text-sm text-text shadow-[var(--shadow-sm)]">{(control.options || []).map((option) => <option key={option.value} value={option.value}>{controlOptionLabel(control, option.value, option.label)}</option>)}</select></label>;
    return <div key={control.id} className="space-y-2"><p className="text-sm font-medium text-text">{controlLabel(control)}</p><div className="flex flex-wrap gap-2">{(control.options || []).map((option) => { const selected = String(value ?? "") === option.value; return <button key={option.value} type="button" aria-pressed={selected} className={`min-h-[40px] rounded-full px-3.5 py-1.5 text-xs font-semibold ${selected ? "bg-[var(--accent-orange)] text-white shadow-[var(--shadow-sm)]" : "border border-[var(--border)] bg-white text-text-secondary"}`} onClick={() => onChange(control.id, option.value, option.value)}>{controlOptionLabel(control, option.value, option.label)}</button>; })}</div></div>;
  })}</div>;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function Details({
  visual,
  sessionId,
  session,
  embedded = false,
}: {
  visual: VisualPayload;
  sessionId: string;
  session?: VisualSessionState;
  embedded?: boolean;
}) {
  const update = useChatStore((state) => state.updateVisualSessionInteraction);
  const annotations = getVisibleAnnotations(visual);
  const panels = getVisiblePanels(visual);
  const focusedAnnotation = annotations.find((annotation) => annotation.id === session?.focusedAnnotationId);
  const focusedAnnotationBodyId = `${sessionId}-annotation-body`;
  return <>
    {annotations.length > 0 && (
      <div
        className={`visual-detail-shell mt-5 space-y-3 ${embedded ? "visual-detail-shell--embedded" : ""}`.trim()}
        data-focus-active={focusedAnnotation ? "true" : "false"}
      >
        <DiagramSectionPill tone="neutral" className="visual-detail-shell__label">Điểm nhấn đang mở</DiagramSectionPill>
        <div className="visual-detail-shell__rail flex flex-wrap gap-2">
          {annotations.map((annotation, index) => {
            const selected = session?.focusedAnnotationId === annotation.id;
            return (
              <DiagramAnnotationChip
                key={annotation.id}
                title={annotation.title}
                index={index}
                tone={annotation.tone || "accent"}
                selected={selected}
                controls={selected ? focusedAnnotationBodyId : undefined}
                onClick={() => {
                  update(sessionId, { focusedAnnotationId: selected ? undefined : annotation.id, interactionDelta: 1 });
                  trackVisualTelemetry("visual_interacted", {
                    visual_id: visual.id,
                    visual_session_id: sessionId,
                    visual_type: visual.type,
                    control_id: "annotation_focus",
                    value: selected ? "clear" : annotation.id,
                  });
                }}
              />
            );
          })}
        </div>
        {focusedAnnotation && (
          <DiagramInsightPanel
            className="visual-detail-shell__body"
            tone={focusedAnnotation.tone || "accent"}
            eyebrow="Giải thích nhanh"
            title={focusedAnnotation.title}
            body={focusedAnnotation.body ? <p id={focusedAnnotationBodyId}>{focusedAnnotation.body}</p> : undefined}
          />
        )}
      </div>
    )}
    {!!panels.length && (
      <div className={`visual-panel-grid mt-5 grid gap-3 md:grid-cols-2 ${embedded ? "visual-panel-grid--embedded" : ""}`.trim()}>
        {panels.map((panel, index) => (
          <DiagramInsightPanel
            key={panel.id}
            tone={index % 2 === 0 ? "neutral" : "accent"}
            eyebrow="Gợi ý đọc"
            title={panel.title}
            body={panel.body ? <p>{panel.body}</p> : undefined}
          />
        ))}
      </div>
    )}
  </>;
}

function getHtmlPayload(visual: VisualPayload): string | null {
  if (visual.fallback_html) return visual.fallback_html;
  // Also check code_html in spec (LLM may pass it there)
  const spec = asRecord(visual.spec);
  for (const key of ["code_html", "html", "markup", "custom_html", "template_html", "app_html"]) {
    const value = spec[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function getFormulaChips(visual: VisualPayload): string[] {
  const spec = asRecord(visual.spec);
  const metadata = asRecord(visual.metadata);
  const direct = asList(spec.formulas).concat(asList(spec.equations)).concat(asList(metadata.formula_chips));
  return direct
    .map((item) => typeof item === "string" ? item.trim() : "")
    .filter(Boolean)
    .slice(0, 4);
}


export function VisualBlock({
  block,
  embedded = false,
  onSuggestedQuestion,
}: {
  block: VisualBlockData;
  embedded?: boolean;
  onSuggestedQuestion?: (prompt: string) => void;
}) {
  const initialVisual = block.visual;
  const sessionId = sessionIdOf(initialVisual);
  const session = useChatStore((state) => state.visualSessions[sessionId]);
  const update = useChatStore((state) => state.updateVisualSessionInteraction);
  const recordWidgetFeedback = useChatStore((state) => state.recordWidgetFeedback);
  const reduced = useReducedMotion();
  const figureRef = useRef<HTMLElement | null>(null);
  const previousRevisionRef = useRef<number | null>(null);
  const titleId = useId();
  const visibleSummaryId = useId();
  const srSummaryId = useId();
  const [stageCue, setStageCue] = useState<"idle" | "open" | "patch">("idle");
  const activeVisual = (session?.latestVisual || initialVisual) as VisualPayload;
  const visual = {
    ...activeVisual,
    scene: activeVisual.scene || { kind: activeVisual.type, nodes: [], panels: [] },
    controls: activeVisual.controls || [],
    annotations: activeVisual.annotations || [],
    interaction_mode: activeVisual.interaction_mode || "static",
    renderer_kind: activeVisual.renderer_kind || "template",
    shell_variant: activeVisual.shell_variant || (activeVisual.renderer_kind === "app" ? "immersive" : "editorial"),
    patch_strategy: activeVisual.patch_strategy || (activeVisual.renderer_kind === "app" ? "app_state" : activeVisual.renderer_kind === "inline_html" ? "replace_html" : "spec_merge"),
    figure_group_id: activeVisual.figure_group_id || activeVisual.visual_session_id || activeVisual.id,
    figure_index: activeVisual.figure_index || 1,
    figure_total: activeVisual.figure_total || 1,
    pedagogical_role: activeVisual.pedagogical_role || "mechanism",
    chrome_mode: activeVisual.chrome_mode || (activeVisual.renderer_kind === "app" ? "app" : "editorial"),
    claim: activeVisual.claim || cleanVisualSummary(activeVisual) || activeVisual.title,
    narrative_anchor: activeVisual.narrative_anchor || "after-lead",
  };

  // Inline visuals can be structured, inline_html, or app-backed. Keep the render path honest.
  const htmlPayload = getHtmlPayload(visual);
  const cleanedSummary = cleanVisualSummary(visual);
  const accessibleSummary = cleanedSummary || getVisibleAnnotations(visual)[0]?.body || visual.title;
  const describedById = embedded && cleanedSummary
    ? visibleSummaryId
    : accessibleSummary
      ? srSummaryId
      : undefined;
  const status = session?.status || block.status || "committed";
  // Template path REMOVED — all visuals go through inline_html or recharts
  const isTemplateVisual = false; // was: visual.renderer_kind === "template"
  void getFormulaChips; // Available but badges removed from UI
  const artifactHandoffPrompt = typeof visual.artifact_handoff_prompt === "string"
    ? visual.artifact_handoff_prompt.trim()
    : "";
  const canRequestArtifact = Boolean(
    visual.artifact_handoff_available
    && visual.artifact_handoff_mode === "followup_prompt"
    && artifactHandoffPrompt
    && onSuggestedQuestion,
  );

  // Delegate to Code Studio panel when it's open for this visual — avoid duplicate display
  const codeStudioPanelOpen = useUIStore((s) => s.codeStudioPanelOpen);
  const codeStudioActiveSessionId = useCodeStudioStore((s) => s.activeSessionId);
  const hasCodeStudioSessionForThis = useCodeStudioStore((s) => Boolean(s.sessions[sessionId]));
  const delegateToCodeStudioPanel = codeStudioPanelOpen
    && hasCodeStudioSessionForThis
    && codeStudioActiveSessionId === sessionId;

  let renderError: string | null = null;
  let usedFallback = false;
  let body: ReactNode = null;

  const handleStructuredControlChange = (
    controlId: string,
    value: string | number | boolean,
    focusedNodeId?: string,
  ) => {
    update(sessionId, {
      controlValues: { [controlId]: value },
      focusedNodeId,
      interactionDelta: 1,
    });
    trackVisualTelemetry("visual_interacted", {
      visual_id: visual.id,
      visual_session_id: sessionId,
      visual_type: visual.type,
      control_id: controlId,
      value: String(value ?? ""),
      source: "structured_control",
    });
  };

  try {
    const isRechartsVisual = visual.renderer_kind === "recharts"
      || (typeof asRecord(visual.spec).chart_type === "string" && visual.renderer_kind !== "app" && visual.renderer_kind !== "inline_html");

    // Priority: inline_html FIRST (clean SVG/HTML), then Recharts, then template fallback
    const isInlineHtml = visual.renderer_kind === "inline_html" && htmlPayload;

    if (isInlineHtml) {
      body = (
        <InlineVisualFrame
          html={htmlPayload}
          title={visual.title}
          summary={visual.summary}
          sessionId={sessionId}
          shellVariant={visual.shell_variant}
          frameKind="inline_html"
          showFrameIntro={false}
          hostShellMode="force"
        />
      );
    } else if (isRechartsVisual) {
      body = (
        <div className={`visual-block-shell__canvas ${embedded ? "visual-block-shell__canvas--embedded" : ""}`.trim()}>
          <RechartsRenderer spec={asRecord(visual.spec)} />
        </div>
      );
    } else if (isTemplateVisual) {
      const structuredBody = renderStructured(visual, session, reduced);
      if (!structuredBody) throw new Error(`Unsupported structured visual type: ${visual.type}`);
      body = (
        <>
          <ControlBar
            visual={visual}
            session={session}
            onChange={handleStructuredControlChange}
            embedded={embedded}
          />
          <div className={`visual-block-shell__canvas ${embedded ? "visual-block-shell__canvas--embedded" : ""}`.trim()}>
            {structuredBody}
          </div>
          <Details visual={visual} sessionId={sessionId} session={session} embedded={embedded} />
        </>
      );
    } else if (visual.renderer_kind === "app") {
      if (!htmlPayload) throw new Error("Missing html payload for app visual");
      body = (
        <EmbeddedAppFrame
          html={htmlPayload}
          title={visual.title}
          summary={visual.summary}
          sessionId={sessionId}
          shellVariant={visual.shell_variant}
          runtimeManifest={visual.runtime_manifest}
        />
      );
    } else if (htmlPayload) {
      body = (
        <InlineVisualFrame
          html={htmlPayload}
          title={visual.title}
          summary={visual.summary}
          sessionId={sessionId}
          shellVariant={visual.shell_variant}
          frameKind="inline_html"
          showFrameIntro={false}
          hostShellMode="force"
        />
      );
    } else {
      throw new Error("Missing html payload for visual");
    }
  } catch (error) {
    renderError = error instanceof Error ? error.message : "Unknown visual render error";
    body = htmlPayload
      ? <InlineHtmlWidget code={htmlPayload} />
      : <div className="flex items-center gap-3 rounded-2xl border border-border/60 bg-surface-secondary/50 px-5 py-4 text-sm text-text-tertiary">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 opacity-50"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
          Visual đang được chuẩn bị...
        </div>;
    usedFallback = Boolean(htmlPayload);
  }

  useEffect(() => {
    const revision = session?.revisionCount || 1;
    const previousRevision = previousRevisionRef.current;
    const nextCue = previousRevision === null
      ? (visual.lifecycle_event === "visual_patch" ? "patch" : "open")
      : revision !== previousRevision
        ? (visual.lifecycle_event === "visual_patch" ? "patch" : "open")
        : null;

    previousRevisionRef.current = revision;
    if (!nextCue) return;

    setStageCue(nextCue);
    if (reduced) {
      setStageCue("idle");
      return;
    }

    const timeoutId = window.setTimeout(() => setStageCue("idle"), nextCue === "patch" ? 1150 : 900);
    return () => window.clearTimeout(timeoutId);
  }, [reduced, session?.revisionCount, visual.lifecycle_event]);

  useEffect(() => {
    const detail = {
      visual_id: visual.id,
      visual_session_id: sessionId,
      visual_type: visual.type,
      runtime: visual.runtime,
      renderer_kind: visual.renderer_kind,
      shell_variant: visual.shell_variant,
    };
    if (renderError) return void trackVisualTelemetry("visual_render_error", { ...detail, error: renderError });
    if (usedFallback) return void trackVisualTelemetry("visual_fallback_used", detail);
    trackVisualTelemetry("visual_rendered", detail);
  }, [renderError, sessionId, usedFallback, visual.id, visual.renderer_kind, visual.runtime, visual.shell_variant, visual.type]);

  useEffect(() => {
    const handleFrameEvent = (event: Event) => {
      const detail = (event as CustomEvent<Record<string, unknown>>).detail || {};
      if (detail.sessionId !== sessionId) return;

      if (detail.bridgeType === "control" && typeof detail.controlId === "string") {
        update(sessionId, {
          controlValues: { [detail.controlId]: detail.value as string | number | boolean },
          focusedNodeId: typeof detail.focusedNodeId === "string" && detail.focusedNodeId ? detail.focusedNodeId : undefined,
          interactionDelta: 1,
        });
        trackVisualTelemetry("visual_interacted", {
          visual_id: visual.id,
          visual_session_id: sessionId,
          visual_type: visual.type,
          control_id: detail.controlId,
          value: String(detail.value ?? ""),
          source: "frame_control",
        });
        return;
      }

      if (detail.bridgeType === "focus" && typeof detail.annotationId === "string") {
        update(sessionId, {
          focusedAnnotationId: detail.annotationId || undefined,
          interactionDelta: 1,
        });
        trackVisualTelemetry("visual_interacted", {
          visual_id: visual.id,
          visual_session_id: sessionId,
          visual_type: visual.type,
          control_id: "annotation_focus",
          value: detail.annotationId || "clear",
          source: "frame_focus",
        });
        return;
      }

      if (detail.bridgeType === "interaction") {
        const frameDetail = asRecord(detail.detail);
        update(sessionId, {
          focusedNodeId: asText(frameDetail.focusedNodeId) || undefined,
          interactionDelta: 1,
        });
        trackVisualTelemetry("visual_interacted", {
          visual_id: visual.id,
          visual_session_id: sessionId,
          visual_type: visual.type,
          source: "frame_interaction",
          ...frameDetail,
        });
        return;
      }

      if (detail.bridgeType === "telemetry" && typeof detail.name === "string" && detail.name.startsWith("visual_")) {
        trackVisualTelemetry(detail.name as `visual_${string}`, {
          visual_id: visual.id,
          visual_session_id: sessionId,
          visual_type: visual.type,
          source: "frame_telemetry",
          ...asRecord(detail.detail),
        });
        return;
      }

      if (detail.bridgeType === "result") {
        const payload = asRecord(detail.payload);
        recordWidgetFeedback({
          widget_id: String(detail.sessionId || sessionId),
          widget_kind: typeof detail.kind === "string" ? detail.kind : `${visual.type}_result`,
          summary: typeof detail.summary === "string" ? detail.summary : undefined,
          status: typeof detail.status === "string" && detail.status ? detail.status : status,
          title: typeof detail.title === "string" && detail.title ? detail.title : visual.title,
          visual_session_id: sessionId,
          score: typeof payload.score === "number" ? payload.score : undefined,
          correct_count: typeof payload.correct_count === "number" ? payload.correct_count : undefined,
          total_count: typeof payload.total_count === "number" ? payload.total_count : undefined,
          source: visual.renderer_kind,
          data: payload,
        });
      }
    };

    window.addEventListener("wiii:visual-frame", handleFrameEvent as EventListener);
    return () => window.removeEventListener("wiii:visual-frame", handleFrameEvent as EventListener);
  }, [recordWidgetFeedback, sessionId, status, update, visual.id, visual.renderer_kind, visual.title, visual.type]);

  useEffect(() => {
    if (!embedded || typeof window === "undefined") return;
    const element = figureRef.current;
    if (!element || typeof element.scrollIntoView !== "function") return;

    const rect = element.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const topBuffer = 88;
    const bottomBuffer = 120;
    const isMostlyVisible = rect.top >= topBuffer / 2 && rect.bottom <= viewportHeight - bottomBuffer / 2;
    if (isMostlyVisible) return;

    const rafId = window.requestAnimationFrame(() => {
      element.scrollIntoView({
        block: "center",
        inline: "nearest",
        behavior: reduced ? "auto" : "smooth",
      });
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [embedded, reduced, visual.lifecycle_event, visual.title, visual.summary, visual.type]);

  // Inline visual shell stays shared even when body switches between structured, inline_html, and app runtimes.
  // Progressive reveal: decorative skeleton overlay during "open" cue, content always rendered
  const isBuilding = stageCue === "open" && !reduced && status === "open";
  const figureClassName = [
    "visual-block-shell",
    "visual-block-shell--article",
    embedded ? "visual-block-shell--embedded" : "",
    embedded ? "" : "my-6",
  ].filter(Boolean).join(" ");

  if (delegateToCodeStudioPanel) {
    return (
      <figure data-testid="visual-block" className="my-4">
        <button
          type="button"
          className="flex items-center gap-2.5 w-full rounded-xl border border-border/60 bg-surface-secondary/40 px-4 py-3 text-left text-sm text-text-secondary hover:bg-surface-secondary transition-colors"
          onClick={() => {
            useCodeStudioStore.getState().setActiveSession(sessionId);
            useUIStore.getState().openCodeStudio();
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-[var(--accent)]"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          <span className="truncate font-medium">{visual.title}</span>
          <span className="ml-auto text-xs text-text-tertiary shrink-0">Đang mở trong Code Studio</span>
        </button>
      </figure>
    );
  }

  // Inline visuals: render directly without shell header/badge/artifact chrome
  // Skip full shell for inline_html, recharts, and template (converted to inline_html)
  const skipShellChrome = visual.renderer_kind !== "app" && body;
  if (skipShellChrome) {
    return <figure
      ref={figureRef}
      data-testid="visual-block"
      className={figureClassName}
      aria-labelledby={titleId}
      data-visual-status={status}
      data-visual-lifecycle={visual.lifecycle_event}
      data-visual-embedded={embedded ? "true" : "false"}
    >
      <div className={`visual-block-shell__body ${embedded ? "visual-block-shell__body--embedded" : ""}`.trim()}>
        {body}
      </div>
      <figcaption className="sr-only">{visual.summary || visual.title}</figcaption>
    </figure>;
  }

  return <figure
    ref={figureRef}
    data-testid="visual-block"
    className={figureClassName}
    aria-labelledby={titleId}
    aria-describedby={describedById}
    data-visual-status={status}
    data-visual-lifecycle={visual.lifecycle_event}
    data-visual-cue={stageCue}
    data-visual-embedded={embedded ? "true" : "false"}
  >
    <div className={`visual-block-shell__header ${embedded ? "visual-block-shell__header--embedded" : ""}`.trim()}>
      <div className="space-y-4">
        {/* Badge/pill removed — visual_type/pedagogical_role are internal metadata */}
        <div className="space-y-2">
          <h3 id={titleId} className="font-serif text-[clamp(1.55rem,4vw,2.25rem)] leading-tight text-text">
            {visual.title}
          </h3>
          {embedded && cleanedSummary ? (
            <p
              id={visibleSummaryId}
              className="visual-block-shell__lede"
            >
              {cleanedSummary}
            </p>
          ) : null}
          {!embedded && visual.claim && normalizeNaturalText(visual.claim) !== normalizeNaturalText(visual.title) ? (
            <p className="visual-block-shell__claim">{visual.claim}</p>
          ) : null}
        </div>
      </div>
    </div>
    <div className={`visual-block-shell__body ${embedded ? "visual-block-shell__body--embedded" : ""}`.trim()}>
    <div className="visual-block-reveal" style={{ position: "relative" }}>
      <motion.div
        variants={staggerContainer}
        initial={reduced ? "visible" : "hidden"}
        animate="visible"
      >
        {body}
      </motion.div>
      {/* Building skeleton overlay — decorative, fades out when visual is ready */}
      <AnimatePresence>
        {isBuilding && (
          <motion.div
            className="visual-block-reveal__skeleton"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.35, ease: "easeOut" } }}
            style={{ position: "absolute", inset: 0, zIndex: 2, pointerEvents: "none" }}
          >
            <div className="visual-block-reveal__skeleton-bar" />
            <div className="visual-block-reveal__skeleton-bar" style={{ width: "25%" }} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
    {(htmlPayload || canRequestArtifact) && (
      <VisualActionBar
        htmlPayload={htmlPayload}
        title={visual.title}
        sessionId={sessionId}
        artifactHandoffLabel={visual.artifact_handoff_label || undefined}
        artifactHandoffPrompt={canRequestArtifact ? artifactHandoffPrompt : undefined}
        onSuggestedQuestion={onSuggestedQuestion}
      />
    )}
    </div>
    <figcaption id={srSummaryId} className="sr-only">{accessibleSummary}</figcaption>
  </figure>;
}

/** Action bar below visual — includes Code Studio link when session exists. */
function VisualActionBar({
  htmlPayload,
  title,
  sessionId,
  artifactHandoffLabel,
  artifactHandoffPrompt,
  onSuggestedQuestion,
}: {
  htmlPayload?: string | null;
  title: string;
  sessionId: string;
  artifactHandoffLabel?: string;
  artifactHandoffPrompt?: string;
  onSuggestedQuestion?: (prompt: string) => void;
}) {
  const hasCodeStudioSession = useCodeStudioStore((s) => Boolean(s.sessions[sessionId]));
  const isStreaming = useChatStore((state) => state.isStreaming);

  const openInCodeStudio = () => {
    useCodeStudioStore.getState().setActiveSession(sessionId);
    useUIStore.getState().openCodeStudio();
  };

  const requestArtifactHandoff = () => {
    if (!artifactHandoffPrompt || !onSuggestedQuestion || isStreaming) return;
    trackVisualTelemetry("visual_artifact_handoff_requested", {
      visual_session_id: sessionId,
      source: "visual_action_bar",
    });
    onSuggestedQuestion(artifactHandoffPrompt);
  };

  return (
    <div className="visual-action-bar">
      {artifactHandoffPrompt && onSuggestedQuestion && (
        <button
          type="button"
          className="visual-action-bar__button visual-action-bar__button--artifact"
          onClick={requestArtifactHandoff}
          disabled={isStreaming}
          aria-label={artifactHandoffLabel || "Mo thanh Artifact"}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l1.8 4.5L18 9.3l-4.2 1.8L12 15.6l-1.8-4.5L6 9.3l4.2-1.8L12 3z"/><path d="M19 14l.9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14z"/><path d="M5 14l.6 1.5L7 16l-1.4.5L5 18l-.6-1.5L3 16l1.4-.5L5 14z"/></svg>
          {artifactHandoffLabel || "Mo thanh Artifact"}
        </button>
      )}
      {hasCodeStudioSession && (
        <button
          type="button"
          className="visual-action-bar__button visual-action-bar__button--studio"
          onClick={openInCodeStudio}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          Code Studio
        </button>
      )}
      {htmlPayload && (
        <>
          <button
            type="button"
            className="visual-action-bar__button"
            onClick={() => {
              const blob = new Blob([htmlPayload], { type: "text/html" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `${(title || "visual").replace(/[^a-zA-Z0-9\u00C0-\u024F]/g, "_").substring(0, 40)}.html`;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Tải HTML
          </button>
          <button
            type="button"
            className="visual-action-bar__button"
            onClick={() => { navigator.clipboard.writeText(htmlPayload); }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
            Sao chép
          </button>
        </>
      )}
    </div>
  );
}
