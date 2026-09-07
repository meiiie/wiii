import type {
  ComputerSemanticActResult,
  ComputerSemanticAction,
  ComputerSemanticSnapshot,
  WorkPlaneDescriptor,
  WorkPlaneTransactionInput,
  WorkPlaneTransactionResult,
} from "./contracts";
import {
  browserProcedure,
  buildProcedureCatalog,
  workPlaneProcedure,
  WIII_BROWSER_NAVIGATE_PROCEDURE,
  WIII_COMPUTER_PROCEDURE_PROTOCOL,
  WIII_WORK_PLANE_SEQUENCE_PROCEDURE,
  type ComputerProcedureCatalog,
  type ComputerProcedureDescriptor,
} from "./procedures";

export interface ProcedureComputer {
  environmentId: string;
  semanticProtocol: string;
}

export interface ProcedureRuntimeContext {
  computer: ProcedureComputer;
  workstationContextVersion: string;
}

export interface ProcedureRunParams {
  operationId: string;
  procedureId: string;
  compatibilityFingerprint: string;
  parameters: Record<string, unknown>;
}

interface ProcedureActInput {
  operationId: string;
  stateVersion: string;
  targetRef: string;
  expectedRole: string;
  expectedName: string;
  action: ComputerSemanticAction;
  text?: string | null;
  returnObservation?: boolean;
}

interface ProcedureWorkTransaction {
  operationId: string;
  capabilityId: string;
  capabilityVersion: string;
  targetRef: string;
  ifRevision: string;
  input: Record<string, unknown>;
}

export interface ProcedureRuntimeHost {
  projectId: string;
  resolveContext(): Promise<ProcedureRuntimeContext>;
  observe(environmentId: string): Promise<ComputerSemanticSnapshot>;
  describeWorkPlane(environmentId: string): Promise<WorkPlaneDescriptor>;
  executeWorkPlane(input: WorkPlaneTransactionInput, operationId: string): Promise<WorkPlaneTransactionResult>;
  hasLease(environmentId: string): boolean;
  acquire(operationId: string): Promise<unknown>;
  act(input: ProcedureActInput): Promise<ComputerSemanticActResult>;
  release(operationId: string): Promise<unknown>;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Wiii Computer procedure parameters must be an object");
  }
  return value as Record<string, unknown>;
}

function requiredString(record: Record<string, unknown>, key: string, maxLength: number): string {
  const value = record[key];
  if (typeof value !== "string" || !value.trim() || value.length > maxLength) {
    throw new Error(`Wiii Computer procedure requires a valid ${key}`);
  }
  return value;
}

export function parseProcedureRun(value: unknown): ProcedureRunParams {
  const params = asRecord(value);
  return {
    operationId: requiredString(params, "operationId", 180),
    procedureId: requiredString(params, "procedureId", 120),
    compatibilityFingerprint: requiredString(params, "compatibilityFingerprint", 4_096),
    parameters: asRecord(params.parameters),
  };
}

function childOperationId(operationId: string, index: number): string {
  return `${operationId}:step-${String(index + 1).padStart(2, "0")}`;
}

function browserTarget(parameters: Record<string, unknown>): string {
  const target = requiredString(parameters, "target", 2_048);
  if (Array.from(target).some((character) => character.codePointAt(0)! < 32)) {
    throw new Error("Wiii Computer procedure target contains control characters");
  }
  if (Object.keys(parameters).some((key) => key !== "target")) {
    throw new Error("Wiii Computer Browser procedure received unsupported parameters");
  }
  return target;
}

function workTransactionFrom(value: unknown, operationId: string): ProcedureWorkTransaction {
  const params = asRecord(value);
  const ifRevision = requiredString(params, "ifRevision", 96);
  if (!ifRevision.startsWith("sha256:")) {
    throw new Error("Wiii Work Plane ifRevision is invalid");
  }
  const input = asRecord(params.input);
  if (new TextEncoder().encode(JSON.stringify(input)).byteLength > 256 * 1024) {
    throw new Error("Wiii Work Plane input exceeds 262144 bytes");
  }
  return {
    operationId,
    capabilityId: requiredString(params, "capabilityId", 120),
    capabilityVersion: requiredString(params, "capabilityVersion", 32),
    targetRef: requiredString(params, "targetRef", 512),
    ifRevision,
    input,
  };
}

function workTransactions(params: ProcedureRunParams): ProcedureWorkTransaction[] {
  if (Object.keys(params.parameters).some((key) => key !== "transactions")) {
    throw new Error("Wiii Computer Work Plane procedure received unsupported parameters");
  }
  const transactions = params.parameters.transactions;
  if (!Array.isArray(transactions) || transactions.length < 1 || transactions.length > 16) {
    throw new Error("Wiii Computer procedure transactions must contain 1 to 16 steps");
  }
  return transactions.map((transaction, index) => (
    workTransactionFrom(transaction, childOperationId(params.operationId, index))
  ));
}

function preflightWorkTransaction(
  descriptor: WorkPlaneDescriptor,
  transaction: ProcedureWorkTransaction,
): void {
  const capability = descriptor.capabilities.find((candidate) => (
    candidate.id === transaction.capabilityId
    && candidate.version === transaction.capabilityVersion
  ));
  if (!capability) {
    throw new Error(`procedure_contract_drift: ${transaction.capabilityId}@${transaction.capabilityVersion} is unavailable`);
  }
  if (!capability.reversible || capability.risk !== "reversible_local_edit") {
    throw new Error(`procedure_risk_rejected: ${transaction.capabilityId} is not a reversible local edit`);
  }
  const inputBytes = new TextEncoder().encode(JSON.stringify(transaction.input)).byteLength;
  if (inputBytes > capability.maxInputBytes) {
    throw new Error(`procedure_input_too_large: ${transaction.capabilityId} exceeds its capability limit`);
  }
  const required = Array.isArray(capability.inputSchema.required)
    ? capability.inputSchema.required
    : [];
  for (const key of required) {
    if (typeof key === "string" && !(key in transaction.input)) {
      throw new Error(`procedure_preflight_failed: ${transaction.capabilityId} requires ${key}`);
    }
  }
}

function requireCompatibility(
  procedure: ComputerProcedureDescriptor | null,
  params: ProcedureRunParams,
): ComputerProcedureDescriptor {
  if (!procedure) {
    throw new Error(`procedure_unavailable: ${params.procedureId} is not promoted for this Computer`);
  }
  if (procedure.compatibilityFingerprint !== params.compatibilityFingerprint) {
    throw new Error("procedure_contract_drift: refresh the catalog before running this procedure");
  }
  return procedure;
}

export class ComputerProcedureRuntime {
  constructor(private readonly host: ProcedureRuntimeHost) {}

  async catalog(): Promise<ComputerProcedureCatalog> {
    const { computer, workstationContextVersion } = await this.host.resolveContext();
    const [snapshotResult, workPlaneResult] = await Promise.allSettled([
      this.host.observe(computer.environmentId),
      this.host.describeWorkPlane(computer.environmentId),
    ]);
    const browserNode = snapshotResult.status === "fulfilled"
      ? snapshotResult.value.nodes.find((node) => node.ref === "app:browser")
      : undefined;
    const workPlaneDescriptor = workPlaneResult.status === "fulfilled"
      ? workPlaneResult.value
      : null;
    return buildProcedureCatalog({
      contextVersion: workstationContextVersion,
      semanticProtocol: computer.semanticProtocol,
      browserNode,
      workPlaneDescriptor,
    });
  }

  async run(params: ProcedureRunParams): Promise<unknown> {
    const startedAt = performance.now();
    const { computer } = await this.host.resolveContext();
    if (params.procedureId === WIII_BROWSER_NAVIGATE_PROCEDURE) {
      return this.runBrowser(computer, params, startedAt);
    }
    if (params.procedureId === WIII_WORK_PLANE_SEQUENCE_PROCEDURE) {
      const descriptor = await this.host.describeWorkPlane(computer.environmentId);
      requireCompatibility(await workPlaneProcedure(descriptor), params);
      return this.runWorkPlane(computer, descriptor, params, startedAt);
    }
    throw new Error(`procedure_unavailable: ${params.procedureId} has no runtime implementation`);
  }

  private async runBrowser(
    computer: ProcedureComputer,
    params: ProcedureRunParams,
    startedAt: number,
  ): Promise<unknown> {
    const target = browserTarget(params.parameters);
    const acquiredHere = !this.host.hasLease(computer.environmentId);
    if (acquiredHere) {
      await this.host.acquire(`${params.operationId}:lease`);
    }
    let result: ComputerSemanticActResult;
    try {
      const snapshot = await this.host.observe(computer.environmentId);
      const node = snapshot.nodes.find((candidate) => candidate.ref === "app:browser");
      requireCompatibility(await browserProcedure(computer.semanticProtocol, node), params);
      if (!node) throw new Error("procedure_contract_drift: the typed Browser launcher is unavailable");
      result = await this.host.act({
        operationId: childOperationId(params.operationId, 0),
        stateVersion: snapshot.stateVersion,
        targetRef: node.ref,
        expectedRole: node.role,
        expectedName: node.name,
        action: "set_text",
        text: target,
        returnObservation: true,
      });
    } finally {
      if (acquiredHere) {
        await this.host.release(`${params.operationId}:release`);
      }
    }
    const completed = result.outcome === "completed" && result.verified;
    return {
      protocolVersion: WIII_COMPUTER_PROCEDURE_PROTOCOL,
      outcome: completed ? "completed" : "rejected",
      code: completed ? null : (result.code ?? "procedure_verification_failed"),
      procedureId: WIII_BROWSER_NAVIGATE_PROCEDURE,
      compatibilityFingerprint: params.compatibilityFingerprint,
      completedSteps: completed ? 1 : 0,
      totalSteps: 1,
      localExecutionMs: Math.max(0, performance.now() - startedAt),
      evidence: result.evidence ?? [],
      steps: [{
        index: 0,
        outcome: result.outcome,
        code: result.code,
        verified: result.verified,
        effect: result.effect ?? null,
        route: result.route ?? null,
        evidence: result.evidence ?? [],
      }],
    };
  }

  private async runWorkPlane(
    computer: ProcedureComputer,
    descriptor: WorkPlaneDescriptor,
    params: ProcedureRunParams,
    startedAt: number,
  ): Promise<unknown> {
    const transactions = workTransactions(params);
    transactions.forEach((transaction) => preflightWorkTransaction(descriptor, transaction));
    const steps: Array<Record<string, unknown>> = [];
    const evidence = new Set<string>();
    for (let index = 0; index < transactions.length; index += 1) {
      const { operationId, ...transaction } = transactions[index];
      const result = await this.host.executeWorkPlane({
        environmentId: computer.environmentId,
        projectId: this.host.projectId,
        ...transaction,
      }, operationId);
      result.evidence.forEach((item) => evidence.add(item));
      steps.push({
        index,
        capabilityId: result.capabilityId,
        outcome: result.outcome,
        code: result.code,
        beforeRevision: result.beforeRevision,
        afterRevision: result.afterRevision,
        evidence: result.evidence,
      });
      if (result.outcome !== "completed") {
        return {
          protocolVersion: WIII_COMPUTER_PROCEDURE_PROTOCOL,
          outcome: "rejected",
          code: result.code ?? "procedure_step_rejected",
          procedureId: WIII_WORK_PLANE_SEQUENCE_PROCEDURE,
          compatibilityFingerprint: params.compatibilityFingerprint,
          completedSteps: index,
          totalSteps: transactions.length,
          localExecutionMs: Math.max(0, performance.now() - startedAt),
          evidence: [...evidence].slice(0, 64),
          steps,
        };
      }
    }
    return {
      protocolVersion: WIII_COMPUTER_PROCEDURE_PROTOCOL,
      outcome: "completed",
      code: null,
      procedureId: WIII_WORK_PLANE_SEQUENCE_PROCEDURE,
      compatibilityFingerprint: params.compatibilityFingerprint,
      completedSteps: steps.length,
      totalSteps: transactions.length,
      localExecutionMs: Math.max(0, performance.now() - startedAt),
      evidence: [...evidence].slice(0, 64),
      steps,
    };
  }
}
