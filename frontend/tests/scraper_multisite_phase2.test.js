import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useScraperStore } from "@/stores/scraper";

beforeEach(() => {
  setActivePinia(createPinia());
  vi.stubGlobal("fetch", vi.fn(async (url, options) => {
    if (String(url).includes("/api/v1/scraper/providers")) {
      return {
        ok: true,
        json: async () => ({
          items: [
            {
              key: "mangaforfree",
              label: "MangaForFree",
              hosts: ["mangaforfree.com"],
              form_schema: [{ key: "rate_limit_rps", type: "number", default: 2 }],
              features: ["search"]
            },
            {
              key: "toongod",
              label: "ToonGod",
              hosts: ["toongod.org"],
              form_schema: [{ key: "storage_state_path", type: "string", default: "data/toongod_state.json" }],
              features: ["search", "chapters"]
            },
            {
              key: "generic",
              label: "Generic",
              hosts: [],
              form_schema: [{ key: "http_mode", type: "boolean", default: true }],
              features: ["search", "custom_host"]
            }
          ]
        })
      };
    }
    return {
      ok: true,
      json: async () => ([]),
    };
  }));
});

describe("scraper multisite phase2 payload", () => {
  it("sends toongod site hint without forcing playwright", async () => {
    const store = useScraperStore();
    store.state.site = "toongod";
    store.state.baseUrl = "https://toongod.org";
    store.state.keyword = "demo";
    store.state.httpMode = true;

    await store.search();

    const searchCall = fetch.mock.calls.find(([url]) => String(url).includes("/api/v1/scraper/search"));
    expect(searchCall).toBeTruthy();
    const body = JSON.parse(searchCall[1].body);
    expect(body.site_hint).toBe("toongod");
    expect(body.force_engine).toBeNull();
  });

  it("uses generic+playwright for custom site when not in http mode", async () => {
    const store = useScraperStore();
    store.state.site = "custom";
    store.state.baseUrl = "https://example.org";
    store.state.keyword = "demo";
    store.setMode("headless");

    await store.search();

    const searchCall = fetch.mock.calls.find(([url]) => String(url).includes("/api/v1/scraper/search"));
    expect(searchCall).toBeTruthy();
    const body = JSON.parse(searchCall[1].body);
    expect(body.site_hint).toBe("generic");
    expect(body.force_engine).toBe("playwright");
  });

  it("loads provider metadata", async () => {
    const store = useScraperStore();
    await store.loadProviders();
    expect(store.providerMeta.items.map(item => item.key)).toContain("generic");
    expect(store.siteOptions().map(item => item.key)).toContain("toongod");
    store.setSite("toongod");
    expect(store.providerSchemaFields().length).toBeGreaterThan(0);
  });
});
