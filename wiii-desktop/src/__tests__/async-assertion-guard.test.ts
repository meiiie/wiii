import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { expect, it } from "vitest";

function* testFiles(dir: string): Generator<string> {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* testFiles(path);
    else if (/\.(test|spec)\.[cm]?[jt]sx?$/.test(path)) yield path;
  }
}

function visit(node: ts.Node, check: (call: ts.CallExpression) => void) {
  if (ts.isCallExpression(node)) check(node);
  ts.forEachChild(node, (child) => visit(child, check));
}

function audit(source: string, path: string) {
  const file = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true);
  const issues: string[] = [];
  const waitNames = new Set(["vi.waitFor", "vi.waitUntil"]);
  const utilityNames = new Set<string>();
  const sideEffects = new Set(["render", "rerender", "act"]);
  const eventNames = new Set(["fireEvent"]);
  const userEventNames = new Set<string>();
  const userInstances = new Set<string>();

  for (const stmt of file.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier)) continue;
    const from = stmt.moduleSpecifier.text;
    const bindings = stmt.importClause?.namedBindings;
    const defaultBinding = stmt.importClause?.name;
    if (from === "@testing-library/user-event" && defaultBinding) userEventNames.add(defaultBinding.text);
    if (!bindings || !ts.isNamedImports(bindings)) continue;
    for (const specifier of bindings.elements) {
      const original = (specifier.propertyName ?? specifier.name).text;
      const local = specifier.name.text;
      if (from === "@testing-library/user-event" && ["default", "userEvent"].includes(original)) {
        userEventNames.add(local);
      }
      if (from !== "@testing-library/react" && from !== "@testing-library/dom") continue;
      if (original === "waitFor") waitNames.add(local);
      if (original === "waitForElementToBeRemoved") utilityNames.add(local);
      if (original === "fireEvent") eventNames.add(local);
      if (original === "render" || original === "act") sideEffects.add(local);
    }
  }

  const nameOf = (call: ts.CallExpression) => call.expression.getText(file);
  const findQuery = (call: ts.CallExpression) => /(?:^|\.)find(?:All)?By[A-Z]\w*$/.test(nameOf(call));
  const report = (node: ts.Node, message: string) => {
    const { line } = file.getLineAndCharacterOfPosition(node.getStart(file));
    issues.push(`${path}:${line + 1}: ${message}`);
  };

  visit(file, (call) => {
    const [receiver, method] = nameOf(call).split(".");
    if (userEventNames.has(receiver) && method === "setup" && ts.isVariableDeclaration(call.parent)
      && ts.isIdentifier(call.parent.name)) userInstances.add(call.parent.name.text);
  });

  visit(file, (call) => {
    const name = nameOf(call);
    const [receiver, method] = name.split(".");
    const userAction = (userEventNames.has(receiver) || userInstances.has(receiver))
      && Boolean(method) && method !== "setup";
    if (waitNames.has(name) || utilityNames.has(name) || findQuery(call) || userAction) {
      for (let parent = call.parent; parent; parent = parent.parent) {
        if (ts.isAwaitExpression(parent) || ts.isReturnStatement(parent) || ts.isVariableDeclaration(parent)
          || (ts.isArrowFunction(parent) && !ts.isBlock(parent.body))) break;
        if (ts.isExpressionStatement(parent) || ts.isIfStatement(parent)) {
          report(call, `Await or return ${name} so Vitest observes its result.`);
          break;
        }
      }
    }

    const callback = call.arguments[0];
    if (waitNames.has(name) && callback && (ts.isArrowFunction(callback) || ts.isFunctionExpression(callback))) {
      let assertions = 0;
      visit(callback.body, (nested) => {
        const nestedName = nameOf(nested);
        if (nestedName === "expect" && ++assertions === 2) {
          report(nested, "Retry one assertion at a time; assert the rest after completion.");
        }
        if (sideEffects.has(nestedName) || eventNames.has(nestedName.split(".")[0])
          || userEventNames.has(nestedName.split(".")[0]) || userInstances.has(nestedName.split(".")[0])) {
          report(nested, "Move side effects outside the retry callback.");
        }
      });
    }

    if (/^(?:it|test)(?:\.\w+)*$/.test(name) || /^\b(?:it|test)\.each\(/.test(name)) {
      const testBody = call.arguments[1];
      if (!testBody || (!ts.isArrowFunction(testBody) && !ts.isFunctionExpression(testBody))) return;
      visit(testBody.body, (nested) => {
        const nestedName = nameOf(nested);
        if (!/^(?:(?:window|globalThis)\.)?setTimeout$/.test(nestedName)) return;
        for (let parent = nested.parent; parent !== testBody; parent = parent.parent) {
          if (ts.isNewExpression(parent) && parent.expression.getText(file) === "Promise") {
            report(nested, "Wait for the observed outcome or advance fake timers; do not sleep.");
            break;
          }
        }
      });
    }
  });

  function checkSequence(node: ts.Node) {
    if (ts.isBlock(node)) {
      for (let i = 1; i < node.statements.length; i++) {
        const previous = node.statements[i - 1];
        const current = node.statements[i];
        if (!ts.isExpressionStatement(previous) || !ts.isExpressionStatement(current)) continue;
        const prior = previous.expression;
        const next = current.expression;
        if (!ts.isAwaitExpression(prior) && !/\.to(?:BeTruthy|BeInTheDocument|BeDefined)$/.test(
          ts.isCallExpression(prior) ? nameOf(prior) : "",
        )) continue;
        if (!ts.isCallExpression(next) || !nameOf(next).startsWith("expect(")) continue;
        let waitedForPresence = false;
        visit(prior, (call) => {
          if (findQuery(call) && ts.isAwaitExpression(call.parent)) waitedForPresence = true;
        });
        if (!waitedForPresence) continue;
        visit(next, (call) => {
          if (/^screen\.get(?:All)?By[A-Z]\w*$/.test(nameOf(call))) {
            report(call, "Await the element you assert on; finding a different element may only confirm loading.");
          }
        });
      }
    }
    ts.forEachChild(node, checkSequence);
  }
  checkSequence(file);
  return issues;
}

it("rejects racy async assertion patterns in desktop Vitest files", () => {
  const src = join(dirname(fileURLToPath(import.meta.url)), "..");
  const issues = [...testFiles(src)].flatMap((path) =>
    audit(readFileSync(path, "utf8"), relative(src, path))
  );
  expect(issues.join("\n")).toBe("");
});

it("guards dropped waits, intermediate UI, retry side effects, and sleeps", () => {
  const bad = [
    'screen.findByText("ready");',
    'until(() => expect(mock).toHaveBeenCalled());',
    'user.click(button);',
    'await screen.findByRole("heading", { name: "Loading" }); expect(screen.getByText("ready")).toBeTruthy();',
    'await until(() => { fireEvent.click(button); expect(a).toBe(1); expect(b).toBe(2); });',
    'await new Promise(resolve => setTimeout(resolve, 50));',
  ];
  const imports = `
    import { waitFor as until, fireEvent, screen } from "@testing-library/react";
    import userEvent from "@testing-library/user-event";
    const user = userEvent.setup();
  `;
  expect(audit(`${imports} it("bad", async () => { ${bad.join("\n")} });`, "bad.test.ts")).toHaveLength(7);
  const good = `
    ${imports}
    it("good", async () => {
      await user.click(button);
      expect(await screen.findByText("ready")).toBeTruthy();
      expect(await screen.findByText("complete")).toBeTruthy();
      await until(() => expect(mock).toHaveBeenCalled());
      await vi.advanceTimersByTimeAsync(50);
    });
  `;
  expect(audit(good, "good.test.ts")).toEqual([]);
});
