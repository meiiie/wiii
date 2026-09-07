import { describe, expect, it } from "vitest";
import {
  buildWorkspaceTree,
  flattenWorkspaceTree,
  workspaceAncestorPaths,
} from "@/neko-chill/workspace-tree";
import type { WorkspaceEntry } from "@/neko-chill/workspace-files";

function entry(path: string): WorkspaceEntry {
  return {
    path,
    name: path.replace(/\\/g, "/").split("/").at(-1) ?? path,
    size: 1,
    modifiedAt: null,
    language: "text",
  };
}

describe("workspace tree", () => {
  it("keeps a large workspace collapsed until its folders are opened", () => {
    const tree = buildWorkspaceTree([
      entry("README.md"),
      entry("src/zeta.ts"),
      entry("src/components/Button.tsx"),
      entry("docs/guide.md"),
    ]);

    expect(tree.map((node) => `${node.kind}:${node.name}`)).toEqual([
      "folder:docs",
      "folder:src",
      "file:README.md",
    ]);
    expect(flattenWorkspaceTree(tree, new Set()).map((row) => row.node.path)).toEqual([
      "docs",
      "src",
      "README.md",
    ]);
  });

  it("reveals only expanded branches with stable indentation", () => {
    const tree = buildWorkspaceTree([
      entry("src/index.ts"),
      entry("src/components/Button.tsx"),
      entry("src/components/Card.tsx"),
    ]);

    const rows = flattenWorkspaceTree(tree, new Set(["src", "src/components"]));
    expect(rows.map(({ node, depth }) => `${depth}:${node.path}`)).toEqual([
      "0:src",
      "1:src/components",
      "2:src/components/Button.tsx",
      "2:src/components/Card.tsx",
      "1:src/index.ts",
    ]);
  });

  it("normalizes Windows paths when expanding a selected file", () => {
    expect(workspaceAncestorPaths("src\\components\\Button.tsx")).toEqual([
      "src",
      "src/components",
    ]);
  });
});
