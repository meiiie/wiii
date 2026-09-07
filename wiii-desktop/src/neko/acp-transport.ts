export interface AcpTransport {
  send(line: string): Promise<void>;
  onLine(handler: (line: string) => void): void;
  onExit(handler: (code: number | null) => void): void;
  kill(): Promise<void>;
}
