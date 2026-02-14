import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useMangaStore } from "@/stores/manga";
import { useTranslateStore } from "@/stores/translate";

class MockEventSource {
  constructor(url) {
    this.url = url;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    MockEventSource.instance = this;
  }

  close() {}
}

describe("translate progress semantics", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    MockEventSource.instance = null;
    vi.stubGlobal("EventSource", MockEventSource);
  });

  it("counts only successful pages toward progress", () => {
    const mangaStore = useMangaStore();
    mangaStore.currentManga = { id: "manga-1" };
    mangaStore.chapters = [
      {
        id: "chapter-1",
        page_count: 4,
        isTranslating: false,
        has_translated: false,
        translated_count: 0,
      },
    ];

    const translateStore = useTranslateStore();
    translateStore.initSSE();

    MockEventSource.instance.onmessage({
      data: JSON.stringify({
        type: "chapter_start",
        manga_id: "manga-1",
        chapter_id: "chapter-1",
        total_pages: 4,
      }),
    });

    MockEventSource.instance.onmessage({
      data: JSON.stringify({
        type: "progress",
        manga_id: "manga-1",
        chapter_id: "chapter-1",
        task_id: "task-1",
        stage: "complete",
        status: "completed",
      }),
    });

    MockEventSource.instance.onmessage({
      data: JSON.stringify({
        type: "progress",
        manga_id: "manga-1",
        chapter_id: "chapter-1",
        task_id: "task-2",
        stage: "failed",
        status: "failed",
      }),
    });

    const chapter = mangaStore.chapters[0];
    expect(chapter.successPages).toBe(1);
    expect(chapter.failedPages).toBe(1);
    expect(chapter.processedPages).toBe(2);
    expect(chapter.progress).toBe(25);
    expect(chapter.statusText).toContain("成功 1");
    expect(chapter.statusText).toContain("失败 1");
  });
});
