import type {
  ComputerSemanticNode,
  WorkPlaneDescriptor,
} from "./contracts";

export const WIII_COMPUTER_PROCEDURE_PROTOCOL = "wiii-computer-procedures.v1" as const;
export const WIII_BROWSER_NAVIGATE_PROCEDURE = "browser.navigate.v1" as const;
export const WIII_WORK_PLANE_SEQUENCE_PROCEDURE = "work-plane.sequence.v1" as const;

export interface ComputerProcedureDescriptor {
  id: string;
  version: "1";
  status: "promoted";
  route: "typed_app" | "work_plane";
  adapterId: string;
  adapterVersion: string;
  compatibilityFingerprint: string;
  risk: "safe_read" | "reversible_write";
  permission: "computer_control" | "project_write";
  displayLeaseRequired: boolean;
  maxSteps: number;
  parameterSchema: Record<string, unknown>;
  evidence: string[];
}

export interface ComputerProcedureCatalog {
  protocolVersion: typeof WIII_COMPUTER_PROCEDURE_PROTOCOL;
  contextVersion: string;
  procedures: ComputerProcedureDescriptor[];
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entry]) => [key, canonical(entry)]),
  );
}

async function contractFingerprint(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(canonical(value)));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `sha256:${hex}`;
}

export async function browserProcedure(
  semanticProtocol: string,
  browserNode: ComputerSemanticNode | undefined,
): Promise<ComputerProcedureDescriptor | null> {
  const adapter = browserNode?.adapter;
  if (
    browserNode?.ref !== "app:browser"
    || browserNode.role !== "browser"
    || !browserNode.actions.includes("set_text")
    || !adapter
    || adapter.id !== "wiii.chrome.v1"
    || !adapter.capabilities.includes("navigate")
  ) {
    return null;
  }
  const actions = [...browserNode.actions].sort();
  const capabilities = [...adapter.capabilities].sort();
  return {
    id: WIII_BROWSER_NAVIGATE_PROCEDURE,
    version: "1",
    status: "promoted",
    route: "typed_app",
    adapterId: adapter.id,
    adapterVersion: adapter.version,
    compatibilityFingerprint: await contractFingerprint({
      semanticProtocol,
      target: { ref: browserNode.ref, role: browserNode.role },
      adapter: { id: adapter.id, version: adapter.version, capabilities },
      actions,
    }),
    risk: "safe_read",
    permission: "computer_control",
    displayLeaseRequired: true,
    maxSteps: 1,
    parameterSchema: {
      type: "object",
      required: ["target"],
      properties: {
        target: { type: "string", minLength: 1, maxLength: 2_048 },
      },
      additionalProperties: false,
    },
    evidence: ["navigation_target_reached", "post_action_observation"],
  };
}

export async function workPlaneProcedure(
  descriptor: WorkPlaneDescriptor | null,
): Promise<ComputerProcedureDescriptor | null> {
  if (!descriptor || descriptor.capabilities.length === 0) return null;
  const capabilityContract = descriptor.capabilities
    .map((capability) => `${capability.id}@${capability.version}`)
    .sort();
  return {
    id: WIII_WORK_PLANE_SEQUENCE_PROCEDURE,
    version: "1",
    status: "promoted",
    route: "work_plane",
    adapterId: "wiii.work-plane",
    adapterVersion: descriptor.protocolVersion,
    compatibilityFingerprint: await contractFingerprint({
      protocolVersion: descriptor.protocolVersion,
      sourceAuthority: descriptor.sourceAuthority,
      resourceModel: descriptor.resourceModel,
      transactionModel: descriptor.transactionModel,
      capabilityContract,
      capabilities: descriptor.capabilities,
    }),
    risk: "reversible_write",
    permission: "project_write",
    displayLeaseRequired: false,
    maxSteps: 16,
    parameterSchema: {
      type: "object",
      required: ["transactions"],
      properties: {
        transactions: { type: "array", minItems: 1, maxItems: 16 },
      },
      additionalProperties: false,
    },
    evidence: ["source_revision", "transaction_readback"],
  };
}

export async function buildProcedureCatalog(input: {
  contextVersion: string;
  semanticProtocol: string;
  browserNode?: ComputerSemanticNode;
  workPlaneDescriptor: WorkPlaneDescriptor | null;
}): Promise<ComputerProcedureCatalog> {
  const procedures = (await Promise.all([
    browserProcedure(input.semanticProtocol, input.browserNode),
    workPlaneProcedure(input.workPlaneDescriptor),
  ])).filter((procedure): procedure is ComputerProcedureDescriptor => procedure !== null);
  return {
    protocolVersion: WIII_COMPUTER_PROCEDURE_PROTOCOL,
    contextVersion: input.contextVersion,
    procedures,
  };
}
