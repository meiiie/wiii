import type { NekoSession } from "./stores/neko-session-store";

export type ClientCommandName = "new" | "project" | "search" | "info";
export type WorkbenchActionName = "new" | "project" | "info" | "toggle-sidebar";

export interface ClientCommandDefinition {
  name: string;
  description: string;
  source: "Neko Chill";
  inputHint?: string;
  clientCommand: ClientCommandName;
}

export const CLIENT_COMMANDS: ClientCommandDefinition[] = [
  { name: "new", description: "Tạo một phiên mới", source: "Neko Chill", clientCommand: "new" },
  { name: "project", description: "Gắn hoặc xem thư mục dự án", source: "Neko Chill", clientCommand: "project" },
  { name: "search", description: "Mở trung tâm lệnh và lịch sử", source: "Neko Chill", clientCommand: "search" },
  { name: "info", description: "Mở thông tin phiên", source: "Neko Chill", clientCommand: "info" },
];

interface CommandItemBase {
  id: string;
  label: string;
  description: string;
  searchText: string;
}

export interface ActionCommandItem extends CommandItemBase {
  kind: "action";
  action: WorkbenchActionName;
}

export interface AgentCommandItem extends CommandItemBase {
  kind: "command";
  commandText: string;
  source: "Agent";
}

export interface SessionCommandItem extends CommandItemBase {
  kind: "session";
  sessionId: string;
  active: boolean;
  status: NekoSession["status"];
  transcriptSearchText: (query: string) => boolean;
}

export type NekoCommandItem = ActionCommandItem | AgentCommandItem | SessionCommandItem;

function normalize(value: string): string {
  return value
    .toLocaleLowerCase("vi")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/đ/g, "d");
}

function sessionMetadataSearchableText(session: NekoSession): string {
  return normalize([
    session.title,
    session.agentName,
    session.workspace?.name ?? "",
    session.workspace?.path ?? "",
    session.launchProfile?.provider ?? "",
    session.launchProfile?.model ?? "",
    session.backendSessionId ?? "",
  ].join(" "));
}

function sessionTranscriptIncludes(session: NekoSession, query: string): boolean {
  for (const message of session.messages) {
    if (message.text && normalize(message.text).includes(query)) return true;
    for (const block of message.blocks ?? []) {
      if (
        "content" in block
        && typeof block.content === "string"
        && normalize(block.content).includes(query)
      ) {
        return true;
      }
    }
  }
  return false;
}

export function sessionSearchableText(session: NekoSession): string {
  return normalize([
    sessionMetadataSearchableText(session),
    ...session.messages.flatMap((message) => [
      message.text ?? "",
      ...(message.blocks ?? []).flatMap((block) =>
        "content" in block && typeof block.content === "string" ? [block.content] : [],
      ),
    ]),
  ].join(" "));
}

function actionItem(
  action: WorkbenchActionName,
  label: string,
  description: string,
): ActionCommandItem {
  return {
    id: `action:${action}`,
    kind: "action",
    action,
    label,
    description,
    searchText: normalize(`${label} ${description}`),
  };
}

export function buildNekoCommandItems(
  sessions: NekoSession[],
  activeSession: NekoSession | null,
  sidebarOpen: boolean,
): NekoCommandItem[] {
  const actions: ActionCommandItem[] = [
    actionItem("new", "Phiên mới", "Soạn lời nhắn trong Project hiện tại"),
    actionItem(
      "toggle-sidebar",
      sidebarOpen ? "Ẩn cây dự án và phiên" : "Hiện cây dự án và phiên",
      "Mở rộng hoặc thu gọn vùng làm việc",
    ),
  ];
  if (activeSession) {
    actions.push(
      actionItem(
        "project",
        activeSession.workspace ? "Xem dự án hiện tại" : "Gắn dự án cho phiên",
        activeSession.workspace?.path ?? "Chọn ranh giới làm việc của agent",
      ),
      actionItem("info", "Thông tin phiên", "Agent, model, trạng thái và điều khiển"),
    );
  }

  const commands: AgentCommandItem[] = (activeSession?.commands ?? []).map((command) => ({
    id: `command:${encodeURIComponent(command.name)}`,
    kind: "command",
    label: `/${command.name}`,
    description: command.description,
    commandText: `/${command.name}${command.inputHint ? " " : ""}`,
    source: "Agent",
    searchText: normalize(`${command.name} ${command.description} agent slash command`),
  }));

  const sessionItems: SessionCommandItem[] = [...sessions]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .map((session) => ({
      id: `session:${session.id}`,
      kind: "session",
      sessionId: session.id,
      label: session.title,
      description: `${session.workspace?.name ?? "Chưa gắn dự án"} · ${session.agentName}`,
      active: session.id === activeSession?.id,
      status: session.status,
      searchText: sessionMetadataSearchableText(session),
      transcriptSearchText: (query) => sessionTranscriptIncludes(session, query),
    }));

  return [...actions, ...commands, ...sessionItems];
}

export function filterNekoCommandItems(
  items: NekoCommandItem[],
  query: string,
): NekoCommandItem[] {
  const metadataMatches = filterNekoCommandMetadata(items, query);
  if (metadataMatches.length > 0 || !query.trim()) return metadataMatches;
  const normalized = normalize(query.trim());
  return items.filter((item) =>
    item.kind === "session" && item.transcriptSearchText(normalized),
  );
}

export function filterNekoCommandMetadata(
  items: NekoCommandItem[],
  query: string,
): NekoCommandItem[] {
  const normalized = normalize(query.trim());
  if (!normalized) return items;
  return items.filter((item) => item.searchText.includes(normalized));
}
