import { useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  Clock3,
  FileSearch,
  Globe2,
  Search,
  TerminalSquare,
  Wrench,
} from "lucide-react";
import type { ToolExecutionBlockData } from "@/api/types";
import { TOOL_LABELS } from "@/lib/reasoning-labels";

interface ToolExecutionStripProps {
  block: ToolExecutionBlockData;
}

const ABSOLUTE_PATH_PATTERN = /(?:[A-Za-z]:)?(?:[\\/][^\\/\s"'`]+)+/g;
const MARKDOWN_FENCE_PATTERN = /```[\s\S]*?```/g;

export function resolveToolExecutionIcon(name: string) {
  if (name.includes("browser") || name.includes("web")) return Globe2;
  if (name.includes("search")) return Search;
  if (name.includes("python") || name.includes("exec") || name.includes("code")) return TerminalSquare;
  if (name.includes("generate") || name.includes("file")) return FileSearch;
  return Wrench;
}

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function extractFilename(value: string): string {
  const trimmed = value.trim().replace(/[)"'`,]+$/g, "");
  const segments = trimmed.split(/[\\/]/).filter(Boolean);
  return segments[segments.length - 1] || trimmed;
}

function sanitizeInlineText(value: string): string {
  return normalizeWhitespace(
    value.replace(ABSOLUTE_PATH_PATTERN, (match) => extractFilename(match)),
  );
}

function sanitizeTechnicalDetail(value: string): string {
  return value
    .replace(/\r\n/g, "\n")
    .replace(ABSOLUTE_PATH_PATTERN, (match) => extractFilename(match))
    .replace(MARKDOWN_FENCE_PATTERN, (match) => match.replace(/```/g, "").trim())
    .trim();
}

function clampNaturalText(value: string, maxLength = 180): string {
  if (value.length <= maxLength) return value;
  const sliced = value.slice(0, maxLength);
  const lastSpace = sliced.lastIndexOf(" ");
  return `${(lastSpace > 80 ? sliced.slice(0, lastSpace) : sliced).trim()}...`;
}

function inferPythonArtifactName(code: string): string | undefined {
  const savefigMatch = code.match(/savefig\(\s*['"`]([^'"`]+)['"`]/i);
  if (savefigMatch) return extractFilename(savefigMatch[1]);

  const fileMatch = code.match(/['"`]([^'"`]+\.(?:png|jpg|jpeg|webp|svg|pdf|html|xlsx|docx|csv|json|txt))['"`]/i);
  if (fileMatch) return extractFilename(fileMatch[1]);

  return undefined;
}

function describePythonIntent(code: string): string {
  const lowered = code.toLowerCase();
  if (lowered.includes("savefig") || lowered.includes("matplotlib") || lowered.includes("plot(")) {
    const artifactName = inferPythonArtifactName(code);
    return artifactName
      ? `Script Python de tao bieu do ${artifactName}`
      : "Script Python de tao bieu do";
  }
  if (/\.(xlsx|xlsm|csv)\b/i.test(code) || lowered.includes("dataframe")) {
    return "Script Python de xu ly bang du lieu";
  }
  if (/\.(docx|doc)\b/i.test(code)) {
    return "Script Python de tao tai lieu";
  }
  if (/\.(html|htm)\b/i.test(code)) {
    return "Script Python de tao giao dien HTML";
  }
  return "Script Python de tao dau ra ky thuat";
}

function summarizeArgs(toolName: string, args?: Record<string, unknown>): string {
  if (!args) return "";
  if (toolName === "tool_generate_visual" || toolName === "tool_generate_rich_visual") {
    const title = typeof args.title === "string" ? sanitizeInlineText(args.title) : "";
    return title ? `Dang phac thao minh hoa cho: ${clampNaturalText(title, 90)}` : "Dang phac thao mot minh hoa de giai thich ro hon";
  }
  if (toolName === "tool_execute_python") {
    const code = typeof args.code === "string"
      ? args.code
      : typeof args.script === "string"
        ? args.script
        : "";
    if (code.trim()) {
      return describePythonIntent(code);
    }
    return "Script Python dang duoc chuan bi";
  }

  const preferredKeys = ["query", "q", "url", "title", "filename", "file_name", "prompt"];
  for (const key of preferredKeys) {
    const value = args[key];
    if (typeof value === "string" && value.trim()) return clampNaturalText(sanitizeInlineText(value.trim()), 120);
  }

  const firstEntry = Object.entries(args).find(([, value]) => typeof value === "string" && value.trim());
  if (firstEntry && typeof firstEntry[1] === "string") {
    return clampNaturalText(sanitizeInlineText(firstEntry[1].trim()), 120);
  }

  return "";
}

function extractArtifactNames(result: string): string[] {
  const names = new Set<string>();
  const bulletMatches = result.matchAll(/-\s*([^\s]+?\.(?:png|jpg|jpeg|webp|svg|pdf|html|xlsx|docx|csv|json|txt))/gi);
  for (const match of bulletMatches) {
    names.add(extractFilename(match[1]));
  }
  return [...names];
}

function extractOutputSummary(result: string): string | undefined {
  const outputMatch = result.match(/Output:\s*([\s\S]+?)(?:Artifacts?:|$)/i);
  if (!outputMatch) return undefined;
  const cleaned = sanitizeInlineText(outputMatch[1]);
  return cleaned ? clampNaturalText(cleaned, 120) : undefined;
}

function buildPythonTechnicalDetail(args?: Record<string, unknown>, result?: string): string {
  const parts: string[] = [];
  const code = typeof args?.code === "string"
    ? args.code.trim()
    : typeof args?.script === "string"
      ? args.script.trim()
      : "";
  if (code) {
    parts.push(`Script Python\n${code}`);
  }
  if (result?.trim()) {
    parts.push(`Ket qua\n${sanitizeTechnicalDetail(result)}`);
  }
  return parts.join("\n\n").trim();
}

function summarizeResult(
  toolName: string,
  result?: string,
  args?: Record<string, unknown>,
): { line: string; technicalDetail?: string; detailLabel?: string } {
  if (!result) return { line: "" };

  if (toolName === "tool_generate_visual" || toolName === "tool_generate_rich_visual") {
    return {
      line: "Da chen minh hoa ngay trong cau tra loi",
      technicalDetail: sanitizeTechnicalDetail(result) || undefined,
      detailLabel: "Chi tiet tao minh hoa",
    };
  }

  if (toolName === "tool_execute_python") {
    const artifactNames = extractArtifactNames(result);
    const outputSummary = extractOutputSummary(result);
    const line = artifactNames.length > 0
      ? `Da tao ${artifactNames.length} tep: ${artifactNames.join(", ")}`
      : outputSummary || "Script Python da chay xong";
    const technicalDetail = buildPythonTechnicalDetail(args, result);
    return {
      line: clampNaturalText(line, 160),
      technicalDetail: technicalDetail || undefined,
      detailLabel: "Chi tiet script",
    };
  }

  const normalized = clampNaturalText(sanitizeInlineText(result).replace(/[{}[\]"]/g, ""), 180);
  return {
    line: normalized,
    technicalDetail: sanitizeTechnicalDetail(result) || undefined,
    detailLabel: "Chi tiet cong cu",
  };
}

function normalizeForCompare(value: string): string {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}

export function ToolExecutionStrip({ block }: ToolExecutionStripProps) {
  const [expanded, setExpanded] = useState(false);
  const toolName = block.tool.name;
  const Icon = resolveToolExecutionIcon(toolName);
  const label = TOOL_LABELS[toolName] || toolName.replace(/^tool_/, "").replace(/_/g, " ");
  const isPending = block.status === "pending";
  const argsLine = useMemo(
    () => summarizeArgs(toolName, block.tool.args),
    [toolName, block.tool.args],
  );
  const { line: rawResultLine, technicalDetail, detailLabel } = useMemo(
    () => summarizeResult(toolName, block.tool.result, block.tool.args),
    [toolName, block.tool.result, block.tool.args],
  );
  const resultLine = normalizeForCompare(rawResultLine) === normalizeForCompare(argsLine) ? "" : rawResultLine;
  const showDetailsToggle = Boolean(technicalDetail && !isPending);

  return (
    <div className={`tool-strip ${isPending ? "tool-strip--pending" : "tool-strip--complete"}`}>
      <div className="tool-strip__rail" aria-hidden="true">
        <span className="tool-strip__dot">
          <Icon size={12} />
        </span>
      </div>

      <div className="tool-strip__body">
        <div className="tool-strip__header">
          <span className="tool-strip__label">{label}</span>
          <span className="tool-strip__state">
            {isPending ? <Clock3 size={12} /> : <CheckCircle2 size={12} />}
            {isPending ? "Dang chay" : "Da xong"}
          </span>
        </div>

        {argsLine && <div className="tool-strip__query">{argsLine}</div>}
        {resultLine && <div className="tool-strip__result">{resultLine}</div>}

        {showDetailsToggle && (
          <button
            type="button"
            className="tool-strip__toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            <span>{expanded ? "An chi tiet" : detailLabel || "Xem chi tiet"}</span>
            <ChevronDown
              size={12}
              className={`tool-strip__toggle-chevron ${expanded ? "tool-strip__toggle-chevron--open" : ""}`}
            />
          </button>
        )}

        {expanded && technicalDetail && (
          <div className="tool-strip__detail" role="region" aria-label={detailLabel || "Chi tiet ky thuat"}>
            <pre className="tool-strip__detail-pre">
              <code>{technicalDetail}</code>
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export function summarizeToolExecutionBlock(block: ToolExecutionBlockData) {
  const toolName = block.tool.name;
  const label = TOOL_LABELS[toolName] || toolName.replace(/^tool_/, "").replace(/_/g, " ");
  const argsLine = summarizeArgs(toolName, block.tool.args);
  const summary = summarizeResult(toolName, block.tool.result, block.tool.args);
  return {
    label,
    argsLine,
    resultLine: summary.line,
    technicalDetail: summary.technicalDetail,
    detailLabel: summary.detailLabel,
    isPending: block.status === "pending",
    Icon: resolveToolExecutionIcon(toolName),
  };
}
