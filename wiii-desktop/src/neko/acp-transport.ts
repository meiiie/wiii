export type AcpExitDetail = {
  /** Bounded provider stderr tail from native exit notice; absent when empty. */
  stderrTail?: string | null;
};

export interface AcpTransport {
  send(line: string): Promise<void>;
  onLine(handler: (line: string) => void): void;
  onExit(handler: (code: number | null, detail?: AcpExitDetail) => void): void;
  kill(): Promise<void>;
}
