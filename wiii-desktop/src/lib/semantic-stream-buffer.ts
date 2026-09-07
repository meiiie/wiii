export interface SemanticStreamBufferOptions {
  onFlush: (text: string) => void;
}

const ATX_HEADING = /^[\t ]{0,3}#{1,6}(?:[\t ]+|$)/u;
const SETEXT_HEADING = /^[\t ]{0,3}(?:=+|-+)[\t ]*$/u;
const THEMATIC_BREAK = /^[\t ]{0,3}(?:(?:\*[\t ]*){3,}|(?:-[\t ]*){3,}|(?:_[\t ]*){3,})$/u;
const FENCE_OPEN = /^[\t ]{0,3}(`{3,}|~{3,})/u;
const LIST_ITEM = /^[\t ]{0,3}(?:[-+*]|\d{1,9}[.)])[\t ]+/u;

export function findCompleteMarkdownBlockBoundary(value: string): number {
  let boundary = 0;
  const buffer = new SemanticStreamBuffer({
    onFlush: (text) => { boundary ||= text.length; },
  });
  buffer.push(value);
  return boundary;
}

export class SemanticStreamBuffer {
  private chunks: string[] = [];
  private lineChunks: string[] = [];
  private pendingLength = 0;
  private contentLines = 0;
  private fence: string | null = null;
  private inList = false;
  private listSeparator = false;
  private readonly onFlush: (text: string) => void;

  constructor(options: SemanticStreamBufferOptions) {
    this.onFlush = options.onFlush;
  }

  get pending(): number {
    return this.pendingLength;
  }

  get running(): boolean {
    return false;
  }

  push(text: string): void {
    let cursor = 0;
    while (cursor < text.length) {
      const newline = text.indexOf("\n", cursor);
      const end = newline < 0 ? text.length : newline + 1;
      const fragment = text.slice(cursor, end);
      this.lineChunks.push(fragment);
      this.pendingLength += fragment.length;
      cursor = end;
      if (newline < 0) break;
      const completeLine = this.lineChunks.join("");
      const line = completeLine.replace(/\r?\n$/u, "");
      this.lineChunks = [];
      if (this.inList && this.listSeparator && !this.fence && line.trim()
        && !/^[\t ]/u.test(line) && !LIST_ITEM.test(line)) {
        this.pendingLength -= completeLine.length;
        this.drain();
        this.pendingLength = completeLine.length;
      }
      this.chunks.push(completeLine);
      if (this.completesBlock(line)) this.drain();
    }
  }

  drain(): void {
    if (!this.pendingLength) return;
    const text = this.chunks.join("") + this.lineChunks.join("");
    this.discard();
    this.onFlush(text);
  }

  discard(): void {
    this.chunks = [];
    this.lineChunks = [];
    this.pendingLength = 0;
    this.contentLines = 0;
    this.fence = null;
    this.inList = false;
    this.listSeparator = false;
  }

  private completesBlock(line: string): boolean {
    if (this.fence) {
      const trimmed = line.trim();
      const marker = this.fence[0];
      const closed = trimmed.length >= this.fence.length
        && [...trimmed].every((character) => character === marker);
      if (closed) this.fence = null;
      return closed && !this.inList;
    }
    this.fence = line.match(FENCE_OPEN)?.[1] ?? null;
    if (this.fence) return false;
    if (LIST_ITEM.test(line) && !THEMATIC_BREAK.test(line)) this.inList = true;
    if (this.inList) {
      this.listSeparator = !line.trim();
      return false;
    }
    if (this.contentLines === 0) {
      if (!line.trim()) return false;
      this.contentLines = 1;
      return ATX_HEADING.test(line) || THEMATIC_BREAK.test(line);
    }
    this.contentLines += 1;
    return !line.trim() || (this.contentLines === 2 && SETEXT_HEADING.test(line));
  }
}
