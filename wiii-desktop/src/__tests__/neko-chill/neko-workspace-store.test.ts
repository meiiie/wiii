import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  listWorkspaceFiles,
  listWorkspaceChanges,
  readWorkspaceFile,
  readWorkspaceDiff,
} = vi.hoisted(() => ({
  listWorkspaceFiles: vi.fn(),
  listWorkspaceChanges: vi.fn(),
  readWorkspaceFile: vi.fn(),
  readWorkspaceDiff: vi.fn(),
}));

vi.mock("@/neko-chill/workspace-files", () => ({
  listWorkspaceFiles,
  listWorkspaceChanges,
  readWorkspaceFile,
  readWorkspaceDiff,
}));

import { useNekoWorkspaceStore } from "@/neko-chill/stores/neko-workspace-store";

const WORKSPACE = { path: "C:/work/project", name: "project" };

function file(path: string, content = path) {
  return {
    path,
    name: path.split("/").at(-1)!,
    kind: "text" as const,
    language: "typescript",
    mimeType: "text/plain",
    size: content.length,
    modifiedAt: 1,
    content,
    dataUrl: null,
  };
}

describe("neko workspace store", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useNekoWorkspaceStore.getState().clearSession("session-1");
    useNekoWorkspaceStore.setState({ sessions: {} });
    listWorkspaceFiles.mockResolvedValue({
      entries: [{ path: "src/App.tsx", name: "App.tsx", size: 10, modifiedAt: 1, language: "typescript" }],
      truncated: false,
    });
    listWorkspaceChanges.mockResolvedValue({
      isGit: true,
      changes: [{ path: "src/App.tsx", status: "modified", staged: false }],
    });
    readWorkspaceFile.mockImplementation(async (_workspace: string, path: string) =>
      file(path.replace("C:/work/project/", "")),
    );
    readWorkspaceDiff.mockResolvedValue({
      path: "src/App.tsx",
      status: "modified",
      language: "typescript",
      original: "before",
      modified: "after",
      binary: false,
    });
  });

  it("loads files and Git changes for one session", async () => {
    await useNekoWorkspaceStore.getState().refresh("session-1", WORKSPACE);
    const pane = useNekoWorkspaceStore.getState().sessions["session-1"];
    expect(pane.entries.map((entry) => entry.path)).toEqual(["src/App.tsx"]);
    expect(pane.changes).toHaveLength(1);
    expect(pane.isGit).toBe(true);
  });

  it("follows a completed structured ACP file activity", async () => {
    useNekoWorkspaceStore.getState().observeActivity("session-1", WORKSPACE, {
      id: "tool-1",
      title: "Write(src/App.tsx)",
      kind: "file",
      status: "completed",
      operation: "update",
      locations: [{ path: "C:/work/project/src/App.tsx" }],
    });

    await vi.waitFor(() => {
      expect(useNekoWorkspaceStore.getState().sessions["session-1"].selectedFile?.path)
        .toBe("src/App.tsx");
    });
    expect(useNekoWorkspaceStore.getState().sessions["session-1"]).toMatchObject({
      open: true,
      activeTab: "files",
      selectedPath: "src/App.tsx",
    });
  });

  it("keeps a pinned file selected and records unseen activity", async () => {
    await useNekoWorkspaceStore.getState().openFile("session-1", WORKSPACE, "src/App.tsx");
    useNekoWorkspaceStore.getState().setPinned("session-1", true);
    readWorkspaceFile.mockClear();

    useNekoWorkspaceStore.getState().observeActivity("session-1", WORKSPACE, {
      id: "tool-2",
      title: "Write(src/Other.ts)",
      kind: "file",
      status: "completed",
      operation: "update",
      locations: [{ path: "C:/work/project/src/Other.ts" }],
    });

    await vi.waitFor(() => {
      expect(useNekoWorkspaceStore.getState().sessions["session-1"].unseenChanges).toBe(1);
    });
    expect(useNekoWorkspaceStore.getState().sessions["session-1"].selectedPath)
      .toBe("src/App.tsx");
    expect(readWorkspaceFile).not.toHaveBeenCalled();
  });

  it("ignores a stale file response after the user selects another file", async () => {
    let resolveFirst!: (value: ReturnType<typeof file>) => void;
    readWorkspaceFile
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce(file("src/Second.ts", "second"));

    const first = useNekoWorkspaceStore
      .getState()
      .openFile("session-1", WORKSPACE, "src/First.ts");
    const second = useNekoWorkspaceStore
      .getState()
      .openFile("session-1", WORKSPACE, "src/Second.ts");
    await second;
    resolveFirst(file("src/First.ts", "first"));
    await first;

    expect(useNekoWorkspaceStore.getState().sessions["session-1"].selectedFile?.path)
      .toBe("src/Second.ts");
  });

  it("coalesces duplicate refreshes for the same session workspace", async () => {
    let resolveFiles!: (value: { entries: any[]; truncated: boolean }) => void;
    let resolveChanges!: (value: { isGit: boolean; changes: any[] }) => void;
    listWorkspaceFiles.mockImplementationOnce(
      () => new Promise((resolve) => { resolveFiles = resolve; }),
    );
    listWorkspaceChanges.mockImplementationOnce(
      () => new Promise((resolve) => { resolveChanges = resolve; }),
    );

    const first = useNekoWorkspaceStore.getState().refresh("session-1", WORKSPACE);
    const duplicate = useNekoWorkspaceStore.getState().refresh("session-1", WORKSPACE);
    expect(listWorkspaceFiles).toHaveBeenCalledTimes(1);
    expect(listWorkspaceChanges).toHaveBeenCalledTimes(1);

    resolveFiles({ entries: [], truncated: false });
    resolveChanges({ isGit: true, changes: [] });
    await Promise.all([first, duplicate]);
  });

  it("ignores an older workspace refresh after the session changes workspace", async () => {
    let resolveOldFiles!: (value: { entries: any[]; truncated: boolean }) => void;
    let resolveOldChanges!: (value: { isGit: boolean; changes: any[] }) => void;
    listWorkspaceFiles
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOldFiles = resolve; }))
      .mockResolvedValueOnce({
        entries: [{ path: "src/New.ts", name: "New.ts", size: 2, modifiedAt: 2, language: "typescript" }],
        truncated: false,
      });
    listWorkspaceChanges
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOldChanges = resolve; }))
      .mockResolvedValueOnce({ isGit: true, changes: [] });

    const older = useNekoWorkspaceStore.getState().refresh("session-1", WORKSPACE);
    const newer = useNekoWorkspaceStore.getState().refresh(
      "session-1",
      { path: "C:/work/other", name: "other" },
      { force: true },
    );
    await newer;
    resolveOldFiles({
      entries: [{ path: "src/Old.ts", name: "Old.ts", size: 1, modifiedAt: 1, language: "typescript" }],
      truncated: false,
    });
    resolveOldChanges({ isGit: true, changes: [] });
    await older;

    expect(useNekoWorkspaceStore.getState().sessions["session-1"].entries[0].path)
      .toBe("src/New.ts");
  });


  it("dedupes identical files/changes honesty errors", async () => {
    const honesty = "Bản xem trước trong trình duyệt không đọc được workspace trên máy. Hãy dùng app desktop Wiii để mở tệp Project.";
    listWorkspaceFiles.mockRejectedValue(new Error(honesty));
    listWorkspaceChanges.mockRejectedValue(new Error(honesty));
    await useNekoWorkspaceStore.getState().refresh("session-1", WORKSPACE);
    const pane = useNekoWorkspaceStore.getState().sessions["session-1"];
    expect(pane.error).toBe(honesty);
    expect(pane.error?.includes(" · ")).toBe(false);
  });

});


describe("workspace selection identity regressions", () => {
  const deferred = <T,>() => { let resolve!: (v: T) => void; let reject!: (e: Error) => void; const promise = new Promise<T>((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
  const activity = (path: string) => ({id:"edit-b",title:`Update(${path})`,kind:"file" as const,status:"pending" as const,operation:"update" as const,locations:[{path}]});
  beforeEach(() => {
    useNekoWorkspaceStore.getState().clearSession("selection"); vi.clearAllMocks();
    listWorkspaceFiles.mockResolvedValue({entries:[],truncated:false});
    listWorkspaceChanges.mockResolvedValue({isGit:true,changes:[]});
    readWorkspaceFile.mockImplementation(async (_w:string,p:string)=>file(p));
  });
  it("never labels old test contents as a pending edit target", async () => {
    await useNekoWorkspaceStore.getState().openFile("selection", WORKSPACE, "clamp.test.mjs");
    useNekoWorkspaceStore.getState().observeActivity("selection", WORKSPACE, activity("clamp.mjs"));
    const pane=useNekoWorkspaceStore.getState().sessions.selection;
    expect(pane.selectedPath).toBe("clamp.mjs"); expect(pane.selectedFile).toBeNull(); expect(pane.selectedDiff).toBeNull();
  });
  it("invalidates a pending read when an activity selects a different file", async () => {
    const read=deferred<ReturnType<typeof file>>(); readWorkspaceFile.mockImplementationOnce(()=>read.promise);
    const first=useNekoWorkspaceStore.getState().openFile("selection",WORKSPACE,"a.ts");
    useNekoWorkspaceStore.getState().observeActivity("selection",WORKSPACE,activity("b.ts"));
    read.resolve(file("a.ts","OLD-A")); await first;
    expect(useNekoWorkspaceStore.getState().sessions.selection.selectedPath).toBe("b.ts");
    expect(useNekoWorkspaceStore.getState().sessions.selection.selectedFile).toBeNull();
  });
  it("rejects an old generation after clear/recreate with the same session id", async () => {
    const old=deferred<ReturnType<typeof file>>(); readWorkspaceFile.mockImplementationOnce(()=>old.promise).mockResolvedValueOnce(file("new.ts","NEW"));
    const first=useNekoWorkspaceStore.getState().openFile("selection",WORKSPACE,"old.ts");
    useNekoWorkspaceStore.getState().clearSession("selection");
    await useNekoWorkspaceStore.getState().openFile("selection",{path:"C:/work/new",name:"new"},"new.ts");
    old.resolve(file("old.ts","OLD")); await first;
    expect(useNekoWorkspaceStore.getState().sessions.selection.selectedFile?.content).toBe("NEW");
  });
  it("clears previous workspace contents and rejects its late read", async () => {
    await useNekoWorkspaceStore.getState().openFile("selection",WORKSPACE,"old.ts");
    const old=deferred<ReturnType<typeof file>>(); readWorkspaceFile.mockImplementationOnce(()=>old.promise);
    const first=useNekoWorkspaceStore.getState().openFile("selection",WORKSPACE,"later.ts");
    await useNekoWorkspaceStore.getState().refresh("selection",{path:"C:/work/new",name:"new"});
    old.resolve(file("later.ts","OLD-WORKSPACE")); await first;
    const pane=useNekoWorkspaceStore.getState().sessions.selection;
    expect(pane.selectedPath).toBeNull(); expect(pane.selectedFile).toBeNull();
  });
  it("does not accept a late file or error after switching to changes", async () => {
    const old=deferred<ReturnType<typeof file>>(); readWorkspaceFile.mockImplementationOnce(()=>old.promise);
    const first=useNekoWorkspaceStore.getState().openFile("selection",WORKSPACE,"old.ts");
    useNekoWorkspaceStore.getState().setTab("selection","changes");
    old.reject(new Error("OLD-ERROR")); await first;
    const pane=useNekoWorkspaceStore.getState().sessions.selection;
    expect(pane.activeTab).toBe("changes"); expect(pane.selectedFile).toBeNull(); expect(pane.error).toBeNull(); expect(pane.loading).toBe(false);
  });
  it("keeps a canonical file path and contents atomic, including a native alias", async () => {
    readWorkspaceFile.mockResolvedValueOnce(file("real.ts","CANONICAL"));
    await useNekoWorkspaceStore.getState().openFile("selection",WORKSPACE,"alias.ts");
    const pane=useNekoWorkspaceStore.getState().sessions.selection;
    expect(pane.selectedPath).toBe("real.ts");expect(pane.selectedFile?.path).toBe("real.ts");expect(pane.selectedFile?.content).toBe("CANONICAL");
  });
  it("rejects a diff response for a different requested file", async () => {
    readWorkspaceDiff.mockResolvedValueOnce({path:"other.ts",status:"modified",language:"typescript",original:"a",modified:"b",binary:false});
    await useNekoWorkspaceStore.getState().openChange("selection",WORKSPACE,"target.ts");
    const pane=useNekoWorkspaceStore.getState().sessions.selection;
    expect(pane.selectedPath).toBe("target.ts"); expect(pane.selectedDiff).toBeNull(); expect(pane.error).toBeTruthy();
  });
  it("does not follow pending activity while pinned", async () => {
    await useNekoWorkspaceStore.getState().openFile("selection",WORKSPACE,"pinned.ts");
    useNekoWorkspaceStore.getState().setPinned("selection",true);
    useNekoWorkspaceStore.getState().observeActivity("selection",WORKSPACE,activity("b.ts"));
    expect(useNekoWorkspaceStore.getState().sessions.selection.selectedFile?.path).toBe("pinned.ts");
  });
});
