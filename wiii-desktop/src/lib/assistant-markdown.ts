const TABLE_SEPARATOR_ROW_RE =
  /\|\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?/;
const TABLE_SEPARATOR_CELL_RE = /^:?-{3,}:?$/;

interface MarkdownSegment {
  text: string;
  fenced: boolean;
}

function splitCodeSafe(content: string): MarkdownSegment[] {
  const segments: MarkdownSegment[] = [];
  let fence: { marker: string; length: number; start: number } | null = null;
  let proseStart = 0;

  for (const match of content.matchAll(/[^\r\n]*(?:\r\n|\n|\r|$)/g)) {
    if (!match[0]) break;
    const lineStart = match.index!;
    const line = match[0].replace(/(?:\r\n|\n|\r)$/, "");

    if (fence) {
      const closing = /^ {0,3}(`+|~+)[ \t]*$/.exec(line);
      if (closing && closing[1][0] === fence.marker && closing[1].length >= fence.length) {
        const fenceEnd = lineStart + line.length;
        segments.push({ text: content.slice(fence.start, fenceEnd), fenced: true });
        proseStart = fenceEnd;
        fence = null;
      }
      continue;
    }

    const opening = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line);
    if (!opening || (opening[1][0] === "`" && opening[2].includes("`"))) continue;
    if (lineStart > proseStart) {
      segments.push({ text: content.slice(proseStart, lineStart), fenced: false });
    }
    fence = { marker: opening[1][0], length: opening[1].length, start: lineStart };
  }

  if (fence) {
    segments.push({ text: content.slice(fence.start), fenced: true });
  } else if (proseStart < content.length) {
    segments.push({ text: content.slice(proseStart), fenced: false });
  }
  return segments;
}

function hasContainerOrIndentedCode(segments: MarkdownSegment[]): boolean {
  let precedingProse = "";

  for (const segment of segments) {
    if (segment.fenced) {
      if (
        /^ {1,3}(`{3,}|~{3,})/.test(segment.text)
        && /^ {0,3}(?:[-+*]|\d{1,9}[.)])[ \t]+\S/m.test(precedingProse)
      ) {
        return true;
      }
      precedingProse = "";
      continue;
    }

    if (
      /^(?: {4}| {0,3}\t)[ \t]*\S/m.test(segment.text)
      || /^ {0,3}(?:>[ \t]*)+(?:(?:[-+*]|\d{1,9}[.)])[ \t]+)?(`{3,}|~{3,})/m.test(segment.text)
      || /^ {0,3}(?:[-+*]|\d{1,9}[.)])[ \t]+(`{3,}|~{3,})/m.test(segment.text)
    ) {
      return true;
    }
    precedingProse = segment.text;
  }

  return false;
}

function hasMultilinePipeTable(segments: MarkdownSegment[]): boolean {
  for (const segment of segments) {
    if (segment.fenced) continue;
    const lines = segment.text.split(/\r\n|\n|\r/);

    for (let index = 1; index < lines.length; index += 1) {
      const header = lines[index - 1];
      const separator = lines[index];
      if (!header.trim() || (!header.includes("|") && !separator.includes("|"))) continue;

      const cells = separator.trim().replace(/^\|/, "").replace(/\|$/, "").split("|");
      if (cells.every((cell) => /^[ \t]*:?-+:?[ \t]*$/.test(cell))) return true;
    }
  }

  return false;
}

function normalizeInlineSeparators(segment: string): string {
  const promoted = segment
    .replace(/(^|\n)(---|\*\*\*|___)[ \t]+(?=\S)/g, "$1$2\n\n")
    .replace(/([^|\n])\s+(---|\*\*\*|___)\s+(?=\S)/g, "$1\n\n$2\n\n")
    .replace(/(>\s+[^\n>]+?)\s+(ho(?:a|ặ)c)[ \t]+>[ \t]+(?=\S)/gi, "$1\n\n$2\n\n> ")
    .replace(/([:.!?)]|ho(?:a|ặ)c)[ \t]+>[ \t]+(?=\S)/gi, "$1\n> ")
    .replace(/[ \t]+([0-9]{1,2}[.)])[ \t]+(?=\S)/g, "\n$1 ")
    .replace(/[ \t]+([-*+])[ \t]+(?=\S)/g, (match, marker, offset, source) => {
      const before = source.slice(Math.max(0, offset - 24), offset);
      if (!/[:.;!?)]\s*$|\n\s*$/.test(before)) return match;
      return `\n${marker} `;
    });

  let next = promoted;
  for (let pass = 0; pass < 4; pass += 1) {
    const previous = next;
    next = next.replace(
      /(\n[ \t]*[-*+][ \t]+[^\n]*?)[ \t]+([-*+])[ \t]+(?=\S)/g,
      (match, prefix: string, marker: string, offset: number, source: string) => {
        const after = source.slice(offset + match.length, offset + match.length + 16);
        if (/^[A-Z]\b/.test(after)) return match;
        return `${prefix}\n${marker} `;
      },
    );
    if (next === previous) break;
  }
  return next;
}

function splitPipeCells(source: string): string[] {
  return source
    .split("|")
    .map((cell) => cell.trim())
    .filter(Boolean);
}

function findSeparatorRun(cells: string[]): { start: number; count: number } | null {
  for (let start = 0; start < cells.length; start += 1) {
    if (!TABLE_SEPARATOR_CELL_RE.test(cells[start])) continue;
    let count = 0;
    while (
      start + count < cells.length
      && TABLE_SEPARATOR_CELL_RE.test(cells[start + count])
    ) {
      count += 1;
    }
    if (count >= 2) return { start, count };
    start += count;
  }
  return null;
}

function splitTrailingInlineRule(source: string): { tableSource: string; trailing: string } {
  const match = source.match(/\|\s+(---|\*\*\*|___)[ \t]+([\s\S]+)$/);
  if (!match || match.index === undefined) {
    return { tableSource: source, trailing: "" };
  }
  return {
    tableSource: `${source.slice(0, match.index)}|`,
    trailing: `\n\n${match[1]}\n\n${match[2].trim()}`,
  };
}

function rebuildCollapsedPipeTable(source: string): string | null {
  const { tableSource, trailing } = splitTrailingInlineRule(source);
  const cells = splitPipeCells(tableSource);
  const separatorRun = findSeparatorRun(cells);
  if (!separatorRun) return null;

  const columnCount = separatorRun.count;
  const headerStart = separatorRun.start - columnCount;
  if (headerStart < 0) return null;

  const header = cells.slice(headerStart, separatorRun.start);
  if (header.length !== columnCount || header.some((cell) => TABLE_SEPARATOR_CELL_RE.test(cell))) {
    return null;
  }

  const separators = cells.slice(separatorRun.start, separatorRun.start + columnCount);
  const bodyCells = cells.slice(separatorRun.start + columnCount);
  const rows: string[][] = [];
  for (let index = 0; index + columnCount <= bodyCells.length; index += columnCount) {
    rows.push(bodyCells.slice(index, index + columnCount));
  }

  const tableRows = [
    header,
    separators,
    ...rows,
  ].map((row) => `| ${row.join(" | ")} |`);

  return `${tableRows.join("\n")}${trailing}`;
}

function normalizeCollapsedPipeTableLine(line: string): string {
  if (!TABLE_SEPARATOR_ROW_RE.test(line)) return line;

  const firstPipe = line.indexOf("|");
  if (firstPipe < 0) return line;

  const prefix = line.slice(0, firstPipe).trimEnd();
  const tableSource = line.slice(firstPipe).trim();
  const rebuiltTable = rebuildCollapsedPipeTable(tableSource);
  const table = rebuiltTable
    || tableSource
      .replace(/\|\s+\|(?=\s*\S)/g, "|\n|")
      .replace(/\|\s+(---|\*\*\*|___)\s+(?=\S)/g, "|\n\n$1\n\n")
      .split("\n")
      .map((row) => row.trim())
      .filter(Boolean)
      .join("\n");

  if (!prefix) return table;
  return `${prefix}\n\n${table}`;
}

function normalizeCollapsedPipeTables(segment: string): string {
  return segment
    .split("\n")
    .map(normalizeCollapsedPipeTableLine)
    .join("\n");
}

function normalizeParagraphSpacing(segment: string): string {
  return segment
    .replace(/\n(---|\*\*\*|___)\n/g, "\n\n$1\n\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]+\n/g, "\n");
}

function normalizeMarkdownSegment(segment: string): string {
  const withTables = normalizeCollapsedPipeTables(segment);
  const withSeparators = normalizeInlineSeparators(withTables);
  return normalizeParagraphSpacing(withSeparators);
}

export function normalizeAssistantMarkdown(content: string): string {
  if (!content) return content;

  const segments = splitCodeSafe(content);
  // Container and indented code need a full block parser; preserve their source.
  if (hasContainerOrIndentedCode(segments)) return content;
  // Existing multiline tables already have their structure and need no repair.
  if (hasMultilinePipeTable(segments)) return content;

  return segments
    .map((segment) =>
      segment.fenced ? segment.text : normalizeMarkdownSegment(segment.text),
    )
    .join("");
}
