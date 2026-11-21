import type { LucideIcon } from "lucide-react";
import type {
  WiiiConnectActivationReadinessResponse,
  WiiiConnectEffectiveActionInventoryResponse,
  WiiiConnectFacebookPagesResponse,
  WiiiConnectFacebookPostApplyResponse,
  WiiiConnectFacebookPostPreviewResponse,
  WiiiConnectProviderConnectionListResponse,
  WiiiConnectProviderDisconnectResponse,
  WiiiConnectRuntimeConnection,
} from "@/api/types";
import type { CapabilityStatusItemId, CapabilityStatusTone } from "@/lib/capability-status";

export type ConnectTab = "catalog" | "connections" | "paths" | "runtime";

export type ProviderFilter = "wiii_native" | "composio" | "channels" | "mcp" | "workflow";

export type CatalogCategory =
  | "all"
  | "runtime"
  | "chat"
  | "productivity"
  | "automation"
  | "social"
  | "learning"
  | "platform";

export interface NativeCatalogDefinition {
  slug: string;
  label: string;
  description: string;
  category: Exclude<CatalogCategory, "all">;
  icon: LucideIcon;
  fallbackId?: CapabilityStatusItemId;
}

export interface ExternalCatalogDefinition {
  id: string;
  provider: Exclude<ProviderFilter, "wiii_native">;
  label: string;
  description: string;
  category: Exclude<CatalogCategory, "all">;
  icon: LucideIcon;
  requirements: string[];
  source?: "backend" | "local";
  authMode?: string;
  actionCount?: number;
}

export interface CatalogCard {
  id: string;
  providerSlug: string;
  provider: ProviderFilter;
  providerLabel: string;
  label: string;
  description: string;
  category: Exclude<CatalogCategory, "all">;
  categoryLabel: string;
  icon: LucideIcon;
  tone: CapabilityStatusTone;
  status: string;
  statusDetail: string;
  agentReady: boolean;
  connected: boolean;
  connection?: WiiiConnectRuntimeConnection;
  registrySource?: "backend" | "local";
  detailRows: Array<[string, string]>;
  requirements?: string[];
  disabledReason?: string;
}

export interface ProviderConnectionListState {
  response?: WiiiConnectProviderConnectionListResponse;
  loading: boolean;
  error?: string;
  lastFetchedAt?: string;
}

export interface ProviderActivationReadinessState {
  response?: WiiiConnectActivationReadinessResponse;
  loading: boolean;
  error?: string;
  lastFetchedAt?: string;
}

export interface ProviderActionInventoryState {
  response?: WiiiConnectEffectiveActionInventoryResponse;
  loading: boolean;
  error?: string;
  lastFetchedAt?: string;
}

export interface ProviderDisconnectState {
  response?: WiiiConnectProviderDisconnectResponse;
  loading: boolean;
  error?: string;
  lastUpdatedAt?: string;
}

export interface FacebookPostDraftImage {
  base64: string;
  mediaType: string;
  filename: string;
  previewUrl: string;
}

export interface FacebookPostComposerState {
  pages?: WiiiConnectFacebookPagesResponse;
  pagesLoading: boolean;
  pagesError?: string;
  scopeGrantLoading: boolean;
  scopeGrantError?: string;
  preview?: WiiiConnectFacebookPostPreviewResponse;
  previewLoading: boolean;
  previewError?: string;
  apply?: WiiiConnectFacebookPostApplyResponse;
  applyLoading: boolean;
  applyError?: string;
}

export interface ProviderLifecycleStage {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: CapabilityStatusTone;
}

export type ProviderConnectionFlowStatus =
  | "disconnected"
  | "authorizing"
  | "waiting"
  | "connected"
  | "expired"
  | "error"
  | "disconnecting";

export interface ProviderConnectionFlowView {
  status: ProviderConnectionFlowStatus;
  label: string;
  detail: string;
  tone: CapabilityStatusTone;
}

export interface ProviderNextAction {
  title: string;
  detail: string;
  tone: CapabilityStatusTone;
  items: string[];
}
