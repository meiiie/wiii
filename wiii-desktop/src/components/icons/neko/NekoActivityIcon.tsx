import {
  CircleAlert,
  CircleCheck,
  CircleX,
  FilePenLine,
  FileText,
  Globe2,
  ListTree,
  PencilLine,
  Search,
  Sparkles,
  SquareTerminal,
  WandSparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";

export type NekoActivityIconKind =
  | "reasoning"
  | "activity"
  | "terminal"
  | "read"
  | "write"
  | "edit"
  | "search"
  | "web"
  | "skill"
  | "success"
  | "warning"
  | "error"
  | "generic";

const ICONS: Record<NekoActivityIconKind, LucideIcon> = {
  reasoning: Sparkles,
  activity: ListTree,
  terminal: SquareTerminal,
  read: FileText,
  write: FilePenLine,
  edit: PencilLine,
  search: Search,
  web: Globe2,
  skill: WandSparkles,
  success: CircleCheck,
  warning: CircleAlert,
  error: CircleX,
  generic: Wrench,
};

export function resolveNekoToolIconKind(toolName: string): NekoActivityIconKind {
  const name = toolName.trim().toLowerCase();
  if (/^(read|cat|open|view|list|ls)\b/.test(name)) return "read";
  if (/^(write|create|save)\b/.test(name)) return "write";
  if (/^(edit|patch|replace|apply)\b/.test(name)) return "edit";
  if (/^(search|grep|rg|find|glob)\b/.test(name)) return "search";
  if (/^(browser|web|fetch|navigate|http|url)\b/.test(name)) return "web";
  if (/^(skill|mcp)\b/.test(name)) return "skill";
  if (/^(update|todo|plan)\b/.test(name)) return "activity";
  if (/^(bash|shell|command|terminal|exec|run)\b/.test(name)) return "terminal";
  return "generic";
}

export function NekoActivityIcon({
  kind,
  className,
}: {
  kind: NekoActivityIconKind;
  className?: string;
}) {
  const Icon = ICONS[kind];
  return <Icon aria-hidden="true" className={className} strokeWidth={1.75} />;
}
