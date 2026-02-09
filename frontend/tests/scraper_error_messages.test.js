import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useScraperStore } from "@/stores/scraper";

beforeEach(() => {
  setActivePinia(createPinia());
  vi.stubGlobal("fetch", vi.fn());
});

describe("scraper error messages", () => {
  it("maps auth challenge to a friendly message with request id", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        detail: {
          code: "SCRAPER_AUTH_CHALLENGE",
          message: "需要通过 Cloudflare 验证"
        },
        error: {
          code: "HTTP_403",
          request_id: "req-auth-1"
        }
      })
    });

    const store = useScraperStore();
    store.state.keyword = "abc";
    await store.search();

    expect(store.error).toContain("站点触发验证");
    expect(store.error).toContain("RID: req-auth-1");
  });

  it("falls back to detail message for unknown codes", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        detail: {
          code: "SCRAPER_UNKNOWN",
          message: "自定义错误提示"
        },
        error: {
          code: "HTTP_400"
        }
      })
    });

    const store = useScraperStore();
    store.state.keyword = "abc";
    await store.search();

    expect(store.error).toContain("自定义错误提示");
  });
});
