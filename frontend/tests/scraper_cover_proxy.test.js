import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useScraperStore } from "@/stores/scraper";

beforeEach(() => {
  setActivePinia(createPinia());
  vi.stubGlobal("fetch", vi.fn());
});

describe("scraper cover proxy", () => {
  it("proxies cover urls for search results", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "a1",
          title: "Example",
          url: "https://toongod.org/manga/example",
          cover_url: "https://toongod.org/wp-content/uploads/cover.jpg"
        }
      ]
    });

    const store = useScraperStore();
    store.state.keyword = "example";
    await store.search();

    expect(store.results.length).toBe(1);
    expect(store.results[0].cover_url).toContain("/api/v1/scraper/image?");
  });

  it("proxies cover urls for parser list items", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        page_type: "list",
        recognized: true,
        site: "toongod",
        downloadable: true,
        items: [
          {
            id: "m1",
            title: "Parser Manga",
            url: "https://toongod.org/webtoon/parser-manga",
            cover_url: "https://toongod.org/wp-content/uploads/parser.jpg"
          },
          {
            id: "m2",
            title: "Parser Manga 2",
            url: "https://toongod.org/webtoon/parser-manga-2",
            cover_url: "https://toongod.org/wp-content/uploads/parser2.jpg"
          }
        ],
        warnings: []
      })
    });

    const store = useScraperStore();
    store.parser.url = "https://toongod.org/webtoon/";
    await store.parseUrl();

    expect(store.parser.result).toBeTruthy();
    expect(store.parser.result.items.length).toBe(2);
    expect(store.parser.result.items[0].cover_url).toContain("/api/v1/scraper/image?");
    expect(store.parser.result.items[1].cover_url).toContain("/api/v1/scraper/image?");
  });

  it("keeps external cover urls direct when host is unsupported by backend proxy", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "a2",
          title: "External Cover",
          url: "https://example.com/manga/external",
          cover_url: "https://cdn.example.com/cover.jpg"
        }
      ]
    });

    const store = useScraperStore();
    store.state.keyword = "external";
    await store.search();

    expect(store.results.length).toBe(1);
    expect(store.results[0].cover_url).toBe("https://cdn.example.com/cover.jpg");
  });
});
