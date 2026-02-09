import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { mount, flushPromises } from "@vue/test-utils";
import MangaView from "@/views/MangaView.vue";
import { useMangaStore } from "@/stores/manga";
import { useTranslateStore } from "@/stores/translate";
import { useToastStore } from "@/stores/toast";
import { mangaApi } from "@/api";

let routeParams = { id: "manga-1" };
const routerPush = vi.fn();

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: routeParams }),
  useRouter: () => ({ push: routerPush }),
}));

vi.mock("@/api", () => ({
  mangaApi: {
    list: vi.fn(),
    getChapters: vi.fn(),
    getChapter: vi.fn(),
    deleteManga: vi.fn(),
    deleteChapter: vi.fn(),
  },
  translateApi: {
    translateChapter: vi.fn(),
  },
}));

function buildChapter(id, overrides = {}) {
  return {
    id,
    name: `Chapter ${id}`,
    page_count: 10,
    translated_count: 0,
    has_translated: false,
    isComplete: false,
    isTranslating: false,
    ...overrides,
  };
}

function mountView() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const mangaStore = useMangaStore();
  const translateStore = useTranslateStore();
  const toastStore = useToastStore();

  mangaStore.currentManga = { id: "manga-1", name: "Demo Manga" };
  mangaStore.chapters = [buildChapter("ch-1"), buildChapter("ch-2")];
  mangaStore.openManga = vi.fn().mockResolvedValue(undefined);
  mangaStore.fetchMangas = vi.fn().mockResolvedValue(undefined);
  translateStore.initSSE = vi.fn();
  translateStore.closeSSE = vi.fn();
  toastStore.show = vi.fn();

  const wrapper = mount(MangaView, {
    global: {
      plugins: [pinia],
      stubs: {
        ComicBackground: true,
        ComicLoading: true,
        GlassNav: {
          template: "<div><slot name='actions' /></div>",
        },
      },
    },
  });

  return { wrapper, mangaStore, toastStore };
}

describe("manga delete actions", () => {
  beforeEach(() => {
    routeParams = { id: "manga-1" };
    routerPush.mockReset();
    vi.clearAllMocks();
  });

  it("renders delete buttons for manga and chapters", async () => {
    const { wrapper } = mountView();
    await flushPromises();

    expect(wrapper.find('[data-test="delete-manga-btn"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="delete-chapter-btn-ch-1"]').exists()).toBe(
      true
    );
  });

  it("opens confirmation dialog when chapter delete button is clicked", async () => {
    const { wrapper } = mountView();
    await flushPromises();

    await wrapper.get('[data-test="delete-chapter-btn-ch-1"]').trigger("click");

    expect(wrapper.find('[data-test="confirm-dialog"]').exists()).toBe(true);
    expect(wrapper.get('[data-test="confirm-dialog"]').text()).toContain(
      "Chapter ch-1"
    );
  });

  it("deletes chapter after confirmation and updates local list", async () => {
    mangaApi.deleteChapter.mockResolvedValue({ message: "ok" });
    const { wrapper, mangaStore, toastStore } = mountView();
    await flushPromises();

    await wrapper.get('[data-test="delete-chapter-btn-ch-1"]').trigger("click");
    await wrapper.get('[data-test="confirm-dialog-confirm"]').trigger("click");
    await flushPromises();

    expect(mangaApi.deleteChapter).toHaveBeenCalledWith("manga-1", "ch-1");
    expect(mangaStore.chapters.map((chapter) => chapter.id)).toEqual(["ch-2"]);
    expect(toastStore.show).toHaveBeenCalledWith(
      expect.stringContaining("章节删除成功"),
      "success"
    );
  });

  it("disables chapter delete button while chapter is translating", async () => {
    const { wrapper, mangaStore } = mountView();
    mangaStore.chapters[0].isTranslating = true;
    await wrapper.vm.$nextTick();
    await flushPromises();

    const btn = wrapper.get('[data-test="delete-chapter-btn-ch-1"]');
    expect(btn.attributes("disabled")).toBeDefined();
  });

  it("deletes manga after confirmation and navigates home", async () => {
    mangaApi.deleteManga.mockResolvedValue({ message: "ok" });
    const { wrapper, mangaStore, toastStore } = mountView();
    await flushPromises();

    await wrapper.get('[data-test="delete-manga-btn"]').trigger("click");
    await wrapper.get('[data-test="confirm-dialog-confirm"]').trigger("click");
    await flushPromises();

    expect(mangaApi.deleteManga).toHaveBeenCalledWith("manga-1");
    expect(mangaStore.fetchMangas).toHaveBeenCalled();
    expect(routerPush).toHaveBeenCalledWith({ name: "home" });
    expect(toastStore.show).toHaveBeenCalledWith(
      expect.stringContaining("漫画删除成功"),
      "success"
    );
  });

  it("shows request id when chapter delete request fails", async () => {
    const err = Object.assign(new Error("bad request"), { requestId: "req-42" });
    mangaApi.deleteChapter.mockRejectedValue(err);
    const { wrapper, mangaStore, toastStore } = mountView();
    await flushPromises();

    await wrapper.get('[data-test="delete-chapter-btn-ch-1"]').trigger("click");
    await wrapper.get('[data-test="confirm-dialog-confirm"]').trigger("click");
    await flushPromises();

    expect(mangaStore.chapters.map((chapter) => chapter.id)).toEqual([
      "ch-1",
      "ch-2",
    ]);
    expect(toastStore.show).toHaveBeenCalledWith(
      expect.stringContaining("#req-42"),
      "error"
    );
  });

  it("uses mobile-friendly action layout and accessible delete labels", async () => {
    const { wrapper } = mountView();
    await flushPromises();

    const mobileActionBar = wrapper.get('[data-test="mobile-manga-actions"]');
    const mangaDeleteBtn = wrapper.get('[data-test="delete-manga-btn"]');
    const chapterDeleteBtn = wrapper.get('[data-test="delete-chapter-btn-ch-1"]');
    const chapterActions = wrapper.get('[data-test="chapter-actions-ch-1"]');
    const chapterTranslateBtn = wrapper.get('[aria-label="翻译章节"]');
    const hiddenChapterLabels = chapterActions
      .findAll("span")
      .filter((el) => el.classes().includes("hidden"));

    expect(mobileActionBar.text()).toContain("删除漫画");
    expect(mobileActionBar.text()).toContain("返回列表");
    expect(mangaDeleteBtn.attributes("aria-label")).toBe("删除漫画");
    expect(chapterDeleteBtn.attributes("aria-label")).toBe("删除章节");
    expect(chapterActions.classes()).toContain("flex-wrap");
    expect(chapterTranslateBtn.classes()).toContain("h-10");
    expect(chapterDeleteBtn.classes()).toContain("h-10");
    expect(hiddenChapterLabels).toHaveLength(0);
  });
});
