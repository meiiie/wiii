import type { WorkspaceEntry } from "./workspace-files";

export interface WorkspaceTreeNode {
  kind: "folder" | "file";
  name: string;
  path: string;
  entry?: WorkspaceEntry;
  children: WorkspaceTreeNode[];
}

export interface WorkspaceTreeRow {
  node: WorkspaceTreeNode;
  depth: number;
}

interface MutableTreeNode extends WorkspaceTreeNode {
  children: MutableTreeNode[];
}

function compareNodes(left: WorkspaceTreeNode, right: WorkspaceTreeNode): number {
  if (left.kind !== right.kind) return left.kind === "folder" ? -1 : 1;
  return left.name.localeCompare(right.name, undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function sortTree(nodes: MutableTreeNode[]): MutableTreeNode[] {
  nodes.sort(compareNodes);
  for (const node of nodes) sortTree(node.children);
  return nodes;
}

export function buildWorkspaceTree(entries: WorkspaceEntry[]): WorkspaceTreeNode[] {
  const roots: MutableTreeNode[] = [];
  const folders = new Map<string, MutableTreeNode>();

  for (const entry of entries) {
    const parts = entry.path.replace(/\\/g, "/").split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let parentChildren = roots;
    let currentPath = "";

    for (const folderName of parts.slice(0, -1)) {
      currentPath = currentPath ? `${currentPath}/${folderName}` : folderName;
      let folder = folders.get(currentPath);
      if (!folder) {
        folder = {
          kind: "folder",
          name: folderName,
          path: currentPath,
          children: [],
        };
        folders.set(currentPath, folder);
        parentChildren.push(folder);
      }
      parentChildren = folder.children;
    }

    parentChildren.push({
      kind: "file",
      name: parts[parts.length - 1] ?? entry.name,
      path: parts.join("/"),
      entry,
      children: [],
    });
  }

  return sortTree(roots);
}

export function flattenWorkspaceTree(
  nodes: WorkspaceTreeNode[],
  expandedFolders: ReadonlySet<string>,
  depth = 0,
): WorkspaceTreeRow[] {
  const rows: WorkspaceTreeRow[] = [];
  for (const node of nodes) {
    rows.push({ node, depth });
    if (node.kind === "folder" && expandedFolders.has(node.path)) {
      rows.push(...flattenWorkspaceTree(node.children, expandedFolders, depth + 1));
    }
  }
  return rows;
}

export function workspaceAncestorPaths(path: string): string[] {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts.slice(0, -1).map((_, index) => parts.slice(0, index + 1).join("/"));
}
