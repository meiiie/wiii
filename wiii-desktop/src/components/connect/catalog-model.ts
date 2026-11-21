/** Build catalog cards from backend snapshots, provider state and client fallback. */
import {
  Code2,
  Database,
  FileText,
  Globe2,
  type LucideIcon,
  Network,
  Server,
  Workflow,
} from "lucide-react";
import type { WiiiConnectProviderRegistryEntry, WiiiConnectRuntimeSnapshot } from "@/api/types";
import type { CapabilityStatusViewModel } from "@/lib/capability-status";
import {
  categoryLabelById,
  connectionIconBySlug,
  externalCatalogDefinitions,
  nativeCatalogDefinitions,
} from "./catalog-data";
import {
  capabilityCount,
  compactText,
  connectionCounts,
  connectionTone,
  formatDateTime,
  pathList,
  providerKindLabels,
  scopeSummary,
  statusLabel,
} from "./connect-display";
import type {
  CatalogCard,
  CatalogCategory,
  ExternalCatalogDefinition,
  ProviderActivationReadinessState,
  ProviderConnectionListState,
  ProviderFilter,
} from "./connect-types";
import {
  externalActionSummary,
  externalAgentStatusDetail,
  primaryProviderConnection,
  providerConnectionSummary,
  providerConnectionTone,
  readinessGatewayStatus,
  readinessReadyForAction,
} from "./provider-readiness";

function categoryLabel(category: CatalogCategory): string {
  return categoryLabelById[category] ?? "Khác";
}

function toCatalogCategory(value: unknown): Exclude<CatalogCategory, "all"> {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (
    normalized === "runtime" ||
    normalized === "chat" ||
    normalized === "productivity" ||
    normalized === "automation" ||
    normalized === "social" ||
    normalized === "learning" ||
    normalized === "platform"
  ) {
    return normalized;
  }
  return "automation";
}

function toProviderFilter(value: unknown): Exclude<ProviderFilter, "wiii_native"> | null {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (
    normalized === "composio" ||
    normalized === "channels" ||
    normalized === "mcp" ||
    normalized === "workflow"
  ) {
    return normalized;
  }
  return null;
}

function iconForExternalProvider(
  slug: string,
  provider: Exclude<ProviderFilter, "wiii_native">,
): LucideIcon {
  const normalized = slug.toLowerCase();
  if (provider === "mcp") return normalized.includes("local") ? Server : Network;
  if (provider === "workflow") return normalized.includes("script") ? Code2 : Workflow;
  if (provider === "channels") return normalized.includes("email") ? FileText : Network;
  if (normalized.includes("github")) return Code2;
  if (normalized.includes("drive") || normalized.includes("gmail")) return FileText;
  if (normalized.includes("calendar") || normalized.includes("asana")) return Workflow;
  if (normalized.includes("notion") || normalized.includes("airtable")) return Database;
  return Globe2;
}

function registryEntriesToExternalDefinitions(
  entries: WiiiConnectProviderRegistryEntry[] | null,
): ExternalCatalogDefinition[] | null {
  if (!entries || entries.length === 0) return null;
  const definitions = entries
    .map((entry): ExternalCatalogDefinition | null => {
      const provider = toProviderFilter(entry.provider_kind);
      if (!provider) return null;
      return {
        id: entry.slug,
        provider,
        label: entry.label || entry.slug,
        description:
          entry.description ||
          "Provider do backend registry khai báo; adapter vẫn fail-closed cho đến khi có vault, policy và audit.",
        category: toCatalogCategory(entry.category),
        icon: iconForExternalProvider(entry.slug, provider),
        requirements:
          entry.requirements && entry.requirements.length > 0
            ? entry.requirements
            : ["Vault", "Scope policy", "Execution gateway", "Audit ledger"],
        source: "backend",
        authMode: entry.auth_mode,
        actionCount: entry.action_count,
      };
    })
    .filter((definition): definition is ExternalCatalogDefinition => definition !== null);
  return definitions.length > 0 ? definitions : null;
}

function buildNativeCatalogCards(
  snapshot: WiiiConnectRuntimeSnapshot | null,
  fallbackModel: CapabilityStatusViewModel,
): CatalogCard[] {
  const bySlug = new Map((snapshot?.connections ?? []).map((connection) => [connection.slug, connection]));
  const fallbackById = new Map(fallbackModel.items.map((item) => [item.id, item]));

  return nativeCatalogDefinitions.map((definition) => {
    const connection = bySlug.get(definition.slug);
    if (connection) {
      const tone = connectionTone(connection);
      const counts = connectionCounts(connection);
      const detailRows: Array<[string, string]> = [
        ["Provider", providerKindLabels[connection.provider_kind ?? ""] ?? compactText(connection.provider_kind, "Provider")],
        ["Agent-ready", connection.agent_ready ? "Có" : "Chưa"],
        ["Scope", scopeSummary(connection.scopes)],
        ["Capability", capabilityCount(connection)],
        ["Path dùng", pathList(connection.required_for_paths)],
        ["Nguồn", compactText(connection.source)],
        ["Kiểm tra", formatDateTime(connection.last_checked_at)],
      ];
      if (counts) detailRows.push(["Tài nguyên", counts]);
      if (connection.reason) detailRows.push(["Lý do", compactText(connection.reason)]);
      return {
        id: `native-${definition.slug}`,
        providerSlug: definition.slug,
        provider: "wiii_native",
        providerLabel: "Wiii native",
        label: connection.label || definition.label,
        description: definition.description,
        category: definition.category,
        categoryLabel: categoryLabel(definition.category),
        icon: connectionIconBySlug[connection.slug] ?? definition.icon,
        tone,
        status: statusLabel(connection.status),
        statusDetail: connection.agent_ready ? "Sẵn sàng cho agent" : "Chưa đủ điều kiện agent-ready",
        agentReady: Boolean(connection.agent_ready),
        connected: tone === "ok",
        connection,
        detailRows,
      };
    }

    const fallback = definition.fallbackId
      ? fallbackById.get(definition.fallbackId)
      : undefined;
    if (fallback) {
      return {
        id: `native-${definition.slug}`,
        providerSlug: definition.slug,
        provider: "wiii_native",
        providerLabel: "Wiii native",
        label: definition.label,
        description: definition.description,
        category: definition.category,
        categoryLabel: categoryLabel(definition.category),
        icon: definition.icon,
        tone: fallback.tone,
        status: fallback.value,
        statusDetail: "Đang đọc từ fallback client vì chưa có snapshot backend.",
        agentReady: fallback.tone === "ok",
        connected: fallback.tone === "ok",
        detailRows: [
          ["Nguồn", "Fallback client"],
          ["Trạng thái", fallback.value],
          ["Ghi chú", fallback.title],
        ],
      };
    }

    return {
      id: `native-${definition.slug}`,
      providerSlug: definition.slug,
      provider: "wiii_native",
      providerLabel: "Wiii native",
      label: definition.label,
      description: definition.description,
      category: definition.category,
      categoryLabel: categoryLabel(definition.category),
      icon: definition.icon,
      tone: snapshot ? "off" : "pending",
      status: snapshot ? "Chưa khai báo" : "Chưa có snapshot",
      statusDetail: snapshot
        ? "Backend snapshot chưa khai báo connection này."
        : "Chờ chat_lifecycle.wiii_connect từ lượt runtime.",
      agentReady: false,
      connected: false,
      detailRows: [
        ["Nguồn", snapshot ? "Snapshot backend" : "Chưa có snapshot"],
        ["Trạng thái", snapshot ? "Chưa khai báo" : "Đang chờ"],
      ],
    };
  });
}

function buildExternalCatalogCards(
  providerRegistry: WiiiConnectProviderRegistryEntry[] | null,
  providerConnectionLists: Record<string, ProviderConnectionListState> = {},
  providerReadinessStates: Record<string, ProviderActivationReadinessState> = {},
): CatalogCard[] {
  const definitions =
    registryEntriesToExternalDefinitions(providerRegistry) ?? externalCatalogDefinitions;

  return definitions.map((definition) => {
    const fromBackend = definition.source === "backend";
    const connectionResponse = providerConnectionLists[definition.id]?.response;
    const providerConnection = primaryProviderConnection(connectionResponse);
    const tone = providerConnectionTone(providerConnection, connectionResponse);
    const connectionStatus = providerConnection
      ? statusLabel(providerConnection.state)
      : connectionResponse?.status === "blocked"
        ? "Bị chặn"
        : "Chưa nối";
    const readiness = providerReadinessStates[definition.id]?.response;
    const agentReady = readinessReadyForAction(readiness);
    const reason = connectionResponse?.reason;
    const statusDetail = externalAgentStatusDetail(fromBackend, readiness);
    return {
      id: `${definition.provider}-${definition.id}`,
      providerSlug: definition.id,
      provider: definition.provider,
      providerLabel: providerKindLabels[definition.provider] ?? definition.provider,
      label: definition.label,
      description: definition.description,
      category: definition.category,
      categoryLabel: categoryLabel(definition.category),
      icon: definition.icon,
      tone,
      status: connectionStatus,
      statusDetail,
      agentReady,
      connected: tone === "ok",
      registrySource: definition.source ?? "local",
      detailRows: [
        ["Provider", providerKindLabels[definition.provider] ?? definition.provider],
        ["Nguồn", fromBackend ? "Backend registry" : "Local fallback"],
        ["Auth", compactText(definition.authMode, "Chưa khai báo")],
        ["Action", externalActionSummary(readiness, definition.actionCount)],
        ["Trạng thái", connectionStatus],
        ["Account", providerConnectionSummary(providerConnection)],
        ["Vault ref", providerConnection?.vault_ref_present ? "Có" : "Chưa"],
        ["Scope", providerConnection ? scopeSummary(providerConnection.scopes) : "Chưa"],
        ["Agent-ready", agentReady ? "Có" : "Chưa"],
        ["Gateway", readinessGatewayStatus(readiness)],
        ["Mutation", "Write vẫn bị chặn ngoài allowlist"],
        ...(reason ? ([["Lý do", compactText(reason)]] as Array<[string, string]>) : []),
      ],
      requirements: definition.requirements,
      disabledReason: fromBackend
        ? statusDetail
        : "Dịch vụ kết nối chưa sẵn sàng trên máy này. Hãy cấu hình Wiii Service rồi thử lại.",
    };
  });
}

export function buildConnectionCatalogCards(
  snapshot: WiiiConnectRuntimeSnapshot | null,
  fallbackModel: CapabilityStatusViewModel,
  providerRegistry: WiiiConnectProviderRegistryEntry[] | null,
  providerConnectionLists: Record<string, ProviderConnectionListState> = {},
  providerReadinessStates: Record<string, ProviderActivationReadinessState> = {},
): CatalogCard[] {
  return [
    ...buildNativeCatalogCards(snapshot, fallbackModel),
    ...buildExternalCatalogCards(providerRegistry, providerConnectionLists, providerReadinessStates),
  ];
}
