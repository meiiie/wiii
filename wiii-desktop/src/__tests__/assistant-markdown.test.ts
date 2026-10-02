import { describe, expect, it } from "vitest";
import { normalizeAssistantMarkdown } from "@/lib/assistant-markdown";

describe("normalizeAssistantMarkdown", () => {
  it("repairs collapsed tables and section separators before rendering", () => {
    const input =
      "So sánh nhanh: | Tiêu chí | Annex I | Annex VI | |------|------|------| | Ô nhiễm | Dầu ra biển | Khí thải | --- Mẹo nhớ: đọc theo từng cột.";

    const normalized = normalizeAssistantMarkdown(input);

    expect(normalized).toContain("So sánh nhanh:\n\n| Tiêu chí | Annex I | Annex VI |");
    expect(normalized).toContain("\n| ------ | ------ | ------ |");
    expect(normalized).toContain("\n| Ô nhiễm | Dầu ra biển | Khí thải |");
    expect(normalized).toContain("\n\n---\n\nMẹo nhớ:");
  });

  it("keeps fenced code blocks byte-stable", () => {
    const input = [
      "Trước code --- có separator",
      "```md",
      "| Không | sửa |",
      "|---|---|",
      "A --- B",
      "```",
      "Sau code --- có separator",
    ].join("\n");

    const normalized = normalizeAssistantMarkdown(input);

    expect(normalized).toContain("```md\n| Không | sửa |\n|---|---|\nA --- B\n```");
    expect(normalized).toContain("Trước code\n\n---\n\ncó separator");
    expect(normalized).toContain("Sau code\n\n---\n\ncó separator");
  });

  it("only promotes inline bullets after punctuation boundaries", () => {
    const input = "Các bước: - Mở lớp - Chọn bài - Áp dụng nhưng câu A - B vẫn là văn xuôi.";

    const normalized = normalizeAssistantMarkdown(input);

    expect(normalized).toContain("Các bước:\n- Mở lớp\n- Chọn bài\n- Áp dụng");
    expect(normalized).toContain("câu A - B vẫn là văn xuôi");
  });
  it("rebuilds dense product-style tables whose rows were collapsed into one line", () => {
    const input =
      "--- 🔍 So sánh nhanh: | Tiêu chí | Annex I | Annex VI |---------|----------|---------| | Ô nhiễm | Dầu ra biển | Khí thải ra không khí | Chất gây hại | Dầu, hydrocarbon | SOx, NOx, PM, CO₂ | Ghi chép | Oil Record Book | FONAR, EIAPP | --- 💡 Mẹo nhớ: đọc theo từng cột.";

    const normalized = normalizeAssistantMarkdown(input);

    expect(normalized).toContain("---\n\n🔍 So sánh nhanh:");
    expect(normalized).toContain("| Tiêu chí | Annex I | Annex VI |");
    expect(normalized).toContain("| --------- | ---------- | --------- |");
    expect(normalized).toContain("| Ô nhiễm | Dầu ra biển | Khí thải ra không khí |");
    expect(normalized).toContain("| Ghi chép | Oil Record Book | FONAR, EIAPP |");
    expect(normalized).toContain("\n\n---\n\n💡 Mẹo nhớ:");
  });

  it("promotes inline blockquotes after Vietnamese quote prompts", () => {
    const input =
      "Cậu chỉ cần nói: > “Mình thấy nút Khóa học” hoặc > “Mình không thấy gì cả”";

    const normalized = normalizeAssistantMarkdown(input);

    expect(normalized).toContain("Cậu chỉ cần nói:\n> “Mình thấy nút Khóa học”");
    expect(normalized).toContain("hoặc\n\n> “Mình không thấy gì cả”");
  });

  it("repairs collapsed Vietnamese maritime tables after prose prefixes", () => {
    const input =
      "Ví dụ đời thường: Giống như bạn không được đốt than trong nhà. --- 🔍 So sánh nhanh: | Tiêu chí | Annex I | Annex VI |---------|----------|---------| | Ô nhiễm | Dầu ra biển | Khí thải ra không khí | Chất gây hại | Dầu, hydrocarbon | SOx, NOx, PM, CO₂ | Giới hạn chính | Không xả dầu | Hàm lượng lưu huỳnh ≤0.50% | --- 💡 Mẹo nhớ: đọc theo từng cột.";

    const normalized = normalizeAssistantMarkdown(input);

    expect(normalized).toContain("Ví dụ đời thường: Giống như bạn không được đốt than trong nhà.");
    expect(normalized).toContain("\n\n---\n\n🔍 So sánh nhanh:");
    expect(normalized).toContain("| Tiêu chí | Annex I | Annex VI |");
    expect(normalized).toContain("| Ô nhiễm | Dầu ra biển | Khí thải ra không khí |");
    expect(normalized).toContain("| Giới hạn chính | Không xả dầu | Hàm lượng lưu huỳnh ≤0.50% |");
    expect(normalized).toContain("\n\n---\n\n💡 Mẹo nhớ:");
  });
  it.each(["```text", "~~~bash", "```", "   ```typescript"])("preserves prefixed open fences byte-for-byte (%s)", (opening) => {
    const code = [
      opening,
      'const message = "A --- B";',
      'const glob = "**/*.ts";',
      "Steps: - first - second",
      "literal 1. first 2. second",
      "| Header | Value | |---|---| | A | B |",
      "",
      "",
      "trailing spaces  \t",
      "",
      "",
      "",
    ].join("\n");

    const normalized = normalizeAssistantMarkdown(`Before --- after\n${code}`);

    expect(normalized).toBe(`Before\n\n---\n\nafter\n${code}`);
  });

  it("keeps the code tail unchanged as a prefixed fence streams into a closed block", () => {
    const code = '```text\n"A --- B"\nSteps: - one - two\n| A | B | |---|---|\n\n\nlast  \t\n```';
    const openingEnd = code.indexOf("\n") + 1;

    for (let end = openingEnd; end <= code.length; end += 1) {
      const streamedCode = code.slice(0, end);
      expect(normalizeAssistantMarkdown(`Before.\n${streamedCode}`)).toBe(`Before.\n${streamedCode}`);
    }
  });

  it.each([
    ["````text", "```"],
    ["~~~~text", "~~~"],
    ["```text", "~~~"],
    ["~~~text", "```"],
    ["```text", "```not a closing fence"],
    ["~~~text", "~~~not a closing fence"],
  ])("does not end %s at an invalid closing line %s", (opening, invalidClosing) => {
    const code = `${opening}\nA --- B\n${invalidClosing}\nSteps: - first - second\n\n\ntrailing  \t\n`;

    expect(normalizeAssistantMarkdown(`Before.\n${code}`)).toBe(`Before.\n${code}`);
  });

  it.each([
    ["````text", "  ````` \t"],
    ["~~~~text", "   ~~~~~ \t"],
  ])("normalizes prose after a sufficiently long matching close for %s", (opening, closing) => {
    const code = `${opening}\nA --- B\n~~~\n\`\`\`\n| A | B | |---|---|\n${closing}`;
    const normalized = normalizeAssistantMarkdown(`Before --- after\n${code}\nAfter --- prose`);

    expect(normalized).toBe(`Before\n\n---\n\nafter\n${code}\nAfter\n\n---\n\nprose`);
  });

  it.each(["```", "~~~"])("recognizes a closing %s fence at end of input", (marker) => {
    const code = `${marker}text\nA --- B\n${marker} \t`;

    expect(normalizeAssistantMarkdown(`Before.\n${code}`)).toBe(`Before.\n${code}`);
  });

  it.each([false, true])("preserves CRLF, blank lines and whitespace inside a fence (closed=%s)", (closed) => {
    const code = "~~~~text\r\nA --- B  \t\r\n\r\n\r\n| A | B | |---|---|\r\ntrailing  \t\r\n"
      + (closed ? "  ~~~~ \t\r\nAfter." : "\r\n\r\n");

    expect(normalizeAssistantMarkdown(`Before.\r\n${code}`)).toBe(`Before.\r\n${code}`);
  });

  it("allows backticks in tilde-fence info without rewriting the body", () => {
    const code = "~~~text `literal`\nA --- B\n~~~";

    expect(normalizeAssistantMarkdown(`Before.\n${code}`)).toBe(`Before.\n${code}`);
  });

  it("does not treat backticks in backtick-fence info as a valid opening fence", () => {
    const input = "Before.\n```text `invalid`\nA --- B";

    expect(normalizeAssistantMarkdown(input)).toBe("Before.\n```text `invalid`\nA\n\n---\n\nB");
  });

  it.each([
    ["blockquote fence", '> ```js\n> const a="x --- y";\n> ```'],
    ["nested blockquote tilde fence", '> > ~~~js\n> > const a="a 1. b";\n> > ~~~'],
    ["list fence with four-space continuation", '- item\n    ```js\n    const a="x --- y";\n    ```'],
    ["list fence with two-space continuation", '- item\n  ```js\n  const a="x --- y";\n  ```'],
    ["ordered-list fence", '1. item\n   ~~~js\n   const a="a 1. b";\n   ~~~'],
    ["fence after list marker", '- ```js\n  const a="x --- y";\n  ```'],
    ["fence after quoted list marker", '> - ```js\n>   const a="x --- y";\n>   ```'],
    ["four-space indented code", '    const a="a 1. b";'],
    ["tab-indented code", '\tconst a="x --- y";'],
    ["mixed-space and tab-indented code", '  \tconst a="a 1. b";'],
  ])("preserves the whole document containing %s", (_kind, code) => {
    const input = `Before --- after\n${code}\nAfter --- prose  \n\n\n`;

    expect(normalizeAssistantMarkdown(input)).toBe(input);
  });

  it.each(["```", "~~~"])("still repairs surrounding prose when complex-looking code is inside a direct %s fence", (marker) => {
    const code = [
      `${marker}text`,
      '    const a="a 1. b";',
      '\tconst b="x --- y";',
      "> ```js",
      "- ```sh",
      "    ```js",
      marker,
    ].join("\n");

    expect(normalizeAssistantMarkdown(`Before --- after\n${code}\nAfter --- prose`))
      .toBe(`Before\n\n---\n\nafter\n${code}\nAfter\n\n---\n\nprose`);
  });

  it("preserves the streamed heading, multiline table and partial C++ fence fixture", () => {
    const input = '### Heading\n\n**unfinished\n\n| Key | Value |\n| --- | --- |\n| path | ./src/**/* |\n\n```c++\nconst a="A --- B";';

    expect(normalizeAssistantMarkdown(input)).toBe(input);
  });

  it("preserves a valid multiline table with prose and a closed direct fence", () => {
    const input = 'Before --- after\n\n| Key | Value |\n| --- | --- |\n| path | ./src/**/* |\n\n```c++\nconst a="A --- B";\n```\nAfter --- prose  \n\n\n';

    expect(normalizeAssistantMarkdown(input)).toBe(input);
  });

  it.each([
    "Key | Value\n:--- | ---:\npath | ./src/**/*",
    "| Key | Value |\n| :-: | - |\n| path | ./src/**/* |",
    "| Key |\n| --- |\n| ./src/**/* |",
    "| Key | Value |\r\n|\t:---\t|\t---:\t|\r\n| path | ./src/**/* |",
  ])("preserves existing multiline table syntax and source whitespace", (table) => {
    const input = `Before --- after\n\n${table}\n\nAfter --- prose`;

    expect(normalizeAssistantMarkdown(input)).toBe(input);
  });

  it("still repairs prose when a multiline table is only a direct-fence literal", () => {
    const code = "```text\n| Key | Value |\n| --- | --- |\n| path | ./src/**/* |\n```";

    expect(normalizeAssistantMarkdown(`Before --- after\n${code}\nAfter --- prose`))
      .toBe(`Before\n\n---\n\nafter\n${code}\nAfter\n\n---\n\nprose`);
  });
});
