import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useScraperStore } from "@/stores/scraper";

beforeEach(() => {
  setActivePinia(createPinia());
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn(async (url) => {
    if (String(url).includes("/api/v1/scraper/download")) {
      return {
        ok: true,
        json: async () => ({
          task_id: "task-1",
          status: "pending",
          message: "queued"
        })
      };
    }
    if (String(url).includes("/api/v1/scraper/task/")) {
      return {
        ok: true,
        json: async () => ({
          task_id: "task-1",
          status: "running",
          message: "running"
        })
      };
    }
    return {
      ok: true,
      json: async () => ({})
    };
  }));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("scraper queue key scope", () => {
  it("isolates chapter queue/status by manga id", async () => {
    const store = useScraperStore();
    const chapter = { id: "chapter-1", title: "Chapter 1" };

    store.selectedManga = { id: "manga-a", title: "A" };
    store.download(chapter);

    await Promise.resolve();
    expect(store.chapterStatus("chapter-1")).toBe("pending");
    expect(fetch).toHaveBeenCalledTimes(1);

    store.selectedManga = { id: "manga-b", title: "B" };
    store.download(chapter);

    expect(store.chapterStatus("chapter-1")).toBe("queued");
    expect(store.queue.length).toBe(1);

    store.selectedManga = { id: "manga-a", title: "A" };
    expect(store.chapterStatus("chapter-1")).toBe("pending");
    store.stopPolling();
  });
});

