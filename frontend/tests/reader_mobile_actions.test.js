import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ReaderView from "@/views/ReaderView.vue";
import { useMangaStore } from "@/stores/manga";
import { useToastStore } from "@/stores/toast";
import { mangaApi } from "@/api";

let routeParams = { mangaId: "manga-1", chapterId: "ch-1" };
const routerPush = vi.fn();
const routerGo = vi.fn();
const addHistoryEntry = vi.fn();

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: routeParams }),
  useRouter: () => ({ push: routerPush, go: routerGo }),
}));

vi.mock("@/composables/useKeyboard", () => ({
  useKeyboard: vi.fn(),
}));

vi.mock("@/composables/useReadingHistory", () => ({
  useReadingHistory: () => ({ addEntry: addHistoryEntry }),
}));

vi.mock("@/api", () => ({
  mangaApi: {
    getChapter: vi.fn(),
  },
  translateApi: {
    retranslatePage: vi.fn(),
  },
}));

function mountReader(chapterId = "ch-1") {
  routeParams = { mangaId: "manga-1", chapterId };
  const pinia = createPinia();
  setActivePinia(pinia);

  const mangaStore = useMangaStore();
  const toastStore = useToastStore();

  mangaStore.currentManga = { id: "manga-1", name: "Demo Manga" };
  mangaStore.chapters = [
    { id: "ch-1", name: "Chapter 1" },
    { id: "ch-2", name: "Chapter 2" },
  ];
  mangaStore.fetchMangas = vi.fn().mockResolvedValue(undefined);
  mangaStore.openManga = vi.fn().mockResolvedValue(undefined);

  toastStore.show = vi.fn();
  mangaApi.getChapter.mockResolvedValue({
    pages: [
      {
        name: "1.jpg",
        original_url: "/data/raw/manga/ch-1/1.jpg",
        translated_url: "/output/manga/ch-1/1.webp",
        status: "ok",
      },
    ],
  });

  const wrapper = mount(ReaderView, {
    global: {
      plugins: [pinia],
      stubs: {
        CompareSlider: true,
        StatusBadge: true,
        ContextMenu: true,
        ComicLoading: true,
      },
    },
  });

  return { wrapper, toastStore };
}

describe("reader mobile actions", () => {
  beforeEach(() => {
    Object.defineProperty(window, "scrollTo", { value: vi.fn(), writable: true });
    routeParams = { mangaId: "manga-1", chapterId: "ch-1" };
    routerPush.mockReset();
    routerGo.mockReset();
    addHistoryEntry.mockReset();
    vi.clearAllMocks();
  });

  it("renders mobile fixed action bar with visible text actions", async () => {
    const { wrapper } = mountReader("ch-1");
    await flushPromises();

    const actionBar = wrapper.get('[data-test="mobile-reader-actions"]');
    expect(actionBar.text()).toContain("对比：关");
    expect(actionBar.text()).toContain("上一章");
    expect(actionBar.text()).toContain("下一章");
    expect(actionBar.text()).toContain("返回章节");
  });

  it("toggles compare status text in mobile action bar", async () => {
    const { wrapper } = mountReader("ch-1");
    await flushPromises();

    const compareBtn = wrapper.get('[data-test="mobile-compare-toggle"]');
    expect(compareBtn.text()).toContain("对比：关");

    await compareBtn.trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-test="mobile-compare-toggle"]').text()).toContain(
      "对比：开"
    );
  });

  it("disables prev/next buttons at chapter boundaries", async () => {
    const first = mountReader("ch-1");
    await flushPromises();
    expect(
      first.wrapper.get('[data-test="mobile-prev-chapter"]').attributes("disabled")
    ).toBeDefined();
    expect(
      first.wrapper.get('[data-test="mobile-next-chapter"]').attributes("disabled")
    ).toBeUndefined();

    const last = mountReader("ch-2");
    await flushPromises();
    expect(
      last.wrapper.get('[data-test="mobile-next-chapter"]').attributes("disabled")
    ).toBeDefined();
    expect(
      last.wrapper.get('[data-test="mobile-prev-chapter"]').attributes("disabled")
    ).toBeUndefined();
  });
});
