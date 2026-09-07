/**
 * Presentation-only complete Markdown block buffer.
 *
 * Providers may still stream arbitrary token/delta fragments. The UI does not
 * expose those fragments. It commits only complete Markdown blocks: a full
 * paragraph, list, table, heading, quote group, or fenced code block. A tool
 * or lifecycle boundary calls `drain()` and therefore finalizes the pending
 * block without losing transport content.
 */

export interface SemanticStreamBufferOptions {
  onFlush: (text: string) => void;
}

const BLOCK_SEPARATOR = /\r?\n[\t ]*\r?\n/u;
const ATX_HEADING = /^[\t ]{0,3}#{1,6}(?:[\t ]+|$)/u;
const SETEXT_HEADING = /^[\t ]{0,3}(?:=+|-+)[\t ]*$/u;
const THEMATIC_BREAK = /^[\t ]{0,3}(?:(?:\*[\t ]*){3,}|(?:-[\t ]*){3,}|(?:_[\t ]*){3,})$/u;
const FENCE_OPEN = /^[\t ]{0,3}(`{3,}|~{3,})/u;

interface MarkdownLine {
  text: string;
  end: number;
  terminated: boolean;
}

function readLine(value: string, start: number): MarkdownLine {
  const newline = value.indexOf("\n", start);
  if (newline < 0) {
    return {
      text: value.slice(start).replace(/\r$/u, ""),
      end: value.length,
      terminated: false,
    };
  }
  return {
    text: value.slice(start, newline).replace(/\r$/u, ""),
    end: newline + 1,
    terminated: true,
  };
}

function leadingBlankLinesEnd(value: string): number {
  let cursor = 0;
  while (cursor < value.length) {
    const line = readLine(value, cursor);
    if (!line.terminated || line.text.trim()) break;
    cursor = line.end;
  }
  return cursor;
}

function includeAvailableBlankLines(value: string, start: number): number {
  let cursor = start;
  while (cursor < value.length) {
    const line = readLine(value, cursor);
    if (!line.terminated || line.text.trim()) break;
    cursor = line.end;
  }
  return cursor;
}

function fencedBlockEnd(value: string, opening: MarkdownLine): number {
  const marker = opening.text.match(FENCE_OPEN)?.[1];
  if (!marker || !opening.terminated) return 0;

  const markerCharacter = marker[0];
  let cursor = opening.end;
  while (cursor < value.length) {
    const line = readLine(value, cursor);
    const trimmed = line.text.trim();
    const isClosing =
      trimmed.length >= marker.length &&
      [...trimmed].every((character) => character === markerCharacter);
    if (isClosing) {
      return includeAvailableBlankLines(value, line.end);
    }
    if (!line.terminated) return 0;
    cursor = line.end;
  }
  return 0;
}

/** Return the end offset of the first complete Markdown block, or zero. */
export function findCompleteMarkdownBlockBoundary(value: string): number {
  if (!value) return 0;

  const contentStart = leadingBlankLinesEnd(value);
  if (contentStart >= value.length) return 0;

  const first = readLine(value, contentStart);
  if (FENCE_OPEN.test(first.text)) {
    return fencedBlockEnd(value, first);
  }

  // ATX headings and thematic breaks are complete at the end of their line.
  if (first.terminated && (ATX_HEADING.test(first.text) || THEMATIC_BREAK.test(first.text))) {
    return includeAvailableBlankLines(value, first.end);
  }

  // A Setext heading is exactly two Markdown lines.
  if (first.terminated && first.end < value.length) {
    const second = readLine(value, first.end);
    if (SETEXT_HEADING.test(second.text) && (second.terminated || second.end === value.length)) {
      return includeAvailableBlankLines(value, second.end);
    }
  }

  // Paragraphs, blockquotes, lists, indented code, and tables are finalized by
  // the Markdown blank-line boundary. This deliberately keeps a whole list or
  // table together instead of revealing rows/items as provider tokens arrive.
  const separator = BLOCK_SEPARATOR.exec(value.slice(contentStart));
  return separator
    ? contentStart + (separator.index ?? 0) + separator[0].length
    : 0;
}

export class SemanticStreamBuffer {
  private buffer = "";
  private readonly onFlush: (text: string) => void;

  constructor(options: SemanticStreamBufferOptions) {
    this.onFlush = options.onFlush;
  }

  get pending(): number {
    return this.buffer.length;
  }

  /** Kept for callers/tests that inspect timer state; complete-block mode has none. */
  get running(): boolean {
    return false;
  }

  push(text: string): void {
    if (!text) return;
    this.buffer += text;
    this.flushCompleteBlocks();
  }

  /** Finalize pending transport text at a tool, error, or turn boundary. */
  drain(): void {
    if (!this.buffer) return;
    const text = this.buffer;
    this.buffer = "";
    this.onFlush(text);
  }

  /** Drop presentation-only pending text on rollback or disposal. */
  discard(): void {
    this.buffer = "";
  }

  private flushCompleteBlocks(): void {
    let boundary = findCompleteMarkdownBlockBoundary(this.buffer);
    while (boundary > 0) {
      const text = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary);
      this.onFlush(text);
      boundary = findCompleteMarkdownBlockBoundary(this.buffer);
    }
  }
}
