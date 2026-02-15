import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useScraperStore } from "@/stores/scraper";

beforeEach(() => {
  setActivePinia(createPinia());
  let searchCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url, options) => {
      const target = String(url);
      if (target.includes("/api/v1/scraper/providers")) {
        return {
          ok: true,
          json: async () => ({
            items: [{ key: "toongod", label: "ToonGod", hosts: ["toongod.org"], form_schema: [] }],
          }),
        };
      }
      if (target.includes("/api/v1/scraper/search")) {
        searchCalls += 1;
        if (searchCalls === 1) {
          return {
            ok: false,
            status: 403,
            json: async () => ({
              detail: {
                code: "SCRAPER_AUTH_CHALLENGE",
                message: "challenge",
                action: "PROMPT_USER_COOKIE",
                payload: {
                  target_url: "https://toongod.org/webtoon/demo/",
                  provider_id: "toongod",
                  cookie_keys: ["cf_clearance"],
                  base_url: "https://toongod.org",
                  storage_state_path: "data/toongod_state.json",
                },
              },
            }),
          };
        }
        return {
          ok: true,
          json: async () => [
            {
              id: "demo",
              title: "Demo",
              url: "https://toongod.org/webtoon/demo/",
            },
          ],
        };
      }
      if (target.includes("/api/v1/scraper/inject_cookies")) {
        const body = JSON.parse(options.body);
        if (!body.cookie_header.includes("cf_clearance")) {
          return {
            ok: false,
            status: 400,
            json: async () => ({
              detail: { code: "SCRAPER_COOKIE_MISSING_REQUIRED", message: "missing" },
            }),
          };
        }
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            path: "data/toongod_state.json",
            updated_cookie_keys: ["cf_clearance"],
          }),
        };
      }
      return {
        ok: true,
        json: async () => ([]),
      };
    }),
  );
});

describe("scraper actionable error flow", () => {
  it("prompts cookie injection and retries search once", async () => {
    const store = useScraperStore();
    store.state.site = "toongod";
    store.state.baseUrl = "https://toongod.org";
    store.state.keyword = "demo";

    await store.search();

    expect(store.actionPrompt.visible).toBe(true);
    expect(store.actionPrompt.action).toBe("PROMPT_USER_COOKIE");

    store.actionPrompt.cookieHeader = "cf_clearance=token-ok";
    await store.submitCookiePrompt();

    expect(store.actionPrompt.visible).toBe(false);
    expect(store.results.length).toBe(1);
    const injectCall = fetch.mock.calls.find(([url]) => String(url).includes("/api/v1/scraper/inject_cookies"));
    expect(injectCall).toBeTruthy();
  });
});
