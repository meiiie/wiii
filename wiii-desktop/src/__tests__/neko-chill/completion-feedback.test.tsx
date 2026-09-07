import { createHash } from "node:crypto";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildNekoCompletionWav, createCompletionPlayer, completionPlayer } from "@/neko-chill/completion-sound";
import { useCompletionNoticeStore as notices } from "@/neko-chill/stores/completion-notice-store";
import { CompletionNotices } from "@/neko-chill/components/CompletionNotices";
import { CompletionPreferences } from "@/neko-chill/components/CompletionPreferences";
import { nekoLayoutStorage } from "@/neko-chill/browser-storage";

beforeEach(() => {
  notices.setState({ enabled: true, sound: true, notices: [] });
});
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });
const notice = (id: string) => ({ id, sessionId: `session-${id}`, title: `Task ${id}` });

describe("Neko completion sound", () => {
  it("matches the approved Neko Bubble v6 PCM bytes exactly", () => {
    const wav = buildNekoCompletionWav();
    expect(wav.length).toBe(44204);
    expect(createHash("sha256").update(wav).digest("hex"))
      .toBe("9cc4c872ab0e55f883755a6d1b73b230ac2a94f987108c7f5018fff75c104787");
  });

  it("requires audio unlock, decodes once, coalesces a burst and closes the context", async () => {
    const source = { connect: vi.fn(), disconnect: vi.fn(), start: vi.fn(), buffer: null, onended: null };
    const context = { resume: vi.fn(async () => {}), state: "running", decodeAudioData: vi.fn(async () => ({})),
      createBufferSource: vi.fn(() => source), close: vi.fn(async () => {}), destination: {} };
    const factory = vi.fn(() => context as unknown as AudioContext);
    const player = createCompletionPlayer(factory);
    expect(await player.play()).toBe(false);
    expect(factory).not.toHaveBeenCalled();
    expect(await player.prepare()).toBe(true);
    expect(await player.prepare()).toBe(true);
    expect(context.decodeAudioData).toHaveBeenCalledOnce();
    await player.play(); await player.play();
    expect(source.start).toHaveBeenCalledOnce();
    player.dispose();
    expect(context.close).toHaveBeenCalledOnce();
    expect(await player.play()).toBe(false);
  });

  it("does not fail a task when audio is unavailable", async () => {
    const player = createCompletionPlayer(() => { throw new Error("Audio unavailable"); });
    expect(await player.prepare()).toBe(false);
    expect(await player.play()).toBe(false);
  });
});

describe("completion feedback", () => {
  it("bounds the queue, deduplicates live results and respects mute", () => {
    const play = vi.spyOn(completionPlayer, "play").mockResolvedValue(true);
    notices.getState().publish(notice("1"));
    notices.getState().publish(notice("1"));
    expect(play).toHaveBeenCalledOnce();
    notices.getState().setSound(false);
    for (const id of ["2", "3", "4"]) notices.getState().publish(notice(id));
    expect(notices.getState().notices.map((item) => item.id)).toEqual(["2", "3", "4"]);
    expect(play).toHaveBeenCalledOnce();
    notices.getState().setEnabled(false);
    notices.getState().publish(notice("5"));
    expect(notices.getState().notices).toEqual([]);
  });

  it("persists preferences but never restores old completion notices", async () => {
    notices.getState().setSound(false);
    notices.getState().publish(notice("1"));
    await notices.persist.rehydrate();
    expect(notices.getState().sound).toBe(false);
    const saved = JSON.parse(nekoLayoutStorage.getItem("wiii-completion-preferences-v1")!);
    expect(saved.state).toEqual({ enabled: true, sound: false });
    notices.setState({ notices: [] });
    await notices.persist.rehydrate();
    expect(notices.getState().notices).toEqual([]);
  });

  it("expires after seven seconds without taking focus from the draft", () => {
    vi.useFakeTimers();
    notices.setState({ sound: false });
    render(<><textarea aria-label="Draft" /><CompletionNotices onOpen={vi.fn()} /></>);
    const draft = screen.getByRole("textbox"); draft.focus();
    act(() => notices.getState().publish(notice("1")));
    expect(document.activeElement).toBe(draft);
    act(() => vi.advanceTimersByTime(6999));
    expect(screen.getByText("Đã trả lời xong")).toBeTruthy();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByText("Đã trả lời xong")).toBeNull();
  });

  it("pauses while hovered or keyboard focused and opens the exact result", () => {
    vi.useFakeTimers();
    notices.setState({ sound: false, notices: [notice("1")] });
    const open = vi.fn(); render(<CompletionNotices onOpen={open} />);
    fireEvent.mouseEnter(screen.getByRole("article"));
    act(() => vi.advanceTimersByTime(9000));
    const result = screen.getByRole("button", { name: "Xem kết quả" });
    fireEvent.focus(result);
    fireEvent.mouseLeave(screen.getByRole("article"));
    act(() => vi.advanceTimersByTime(9000));
    expect(screen.getByText("Đã trả lời xong")).toBeTruthy();
    fireEvent.click(result);
    expect(open).toHaveBeenCalledWith("session-1");
    expect(notices.getState().notices).toEqual([]);
  });

  it("has explicit sound preview and does not play when opening preferences", async () => {
    const prepare = vi.spyOn(completionPlayer, "prepare").mockResolvedValue(true);
    const play = vi.spyOn(completionPlayer, "play").mockResolvedValue(true);
    render(<CompletionPreferences />);
    expect(play).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Nghe thử âm báo" }));
    await vi.waitFor(() => expect(play).toHaveBeenCalledOnce());
    expect(prepare).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("checkbox", { name: "Âm báo Neko Bubble" }));
    expect(notices.getState().sound).toBe(false);
  });
});
