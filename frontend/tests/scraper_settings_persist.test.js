import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useScraperStore } from "@/stores/scraper";

beforeEach(() => {
  setActivePinia(createPinia());
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: true,
    json: async () => ({})
  })));
});

describe("scraper settings persistence", () => {
  it("restores settings from localStorage on new store instance", async () => {
    const store = useScraperStore();
    store.state.site = "mangaforfree";
    store.state.baseUrl = "https://mangaforfree.com";
    store.state.mode = "http";
    store.state.httpMode = true;
    store.state.headless = true;
    store.state.concurrency = 9;
    store.state.rateLimitRps = 3.5;
    store.state.storageStatePath = "data/mff_state.json";
    store.state.userDataDir = "data/mff_profile";
    store.state.useProfile = true;
    store.state.useChromeChannel = false;
    store.state.lockUserAgent = false;

    await Promise.resolve();

    setActivePinia(createPinia());
    const restored = useScraperStore();

    expect(restored.state.site).toBe("mangaforfree");
    expect(restored.state.baseUrl).toBe("https://mangaforfree.com");
    expect(restored.state.mode).toBe("http");
    expect(restored.state.httpMode).toBe(true);
    expect(restored.state.concurrency).toBe(9);
    expect(restored.state.rateLimitRps).toBe(3.5);
    expect(restored.state.storageStatePath).toBe("data/mff_state.json");
    expect(restored.state.userDataDir).toBe("data/mff_profile");
    expect(restored.state.useChromeChannel).toBe(false);
    expect(restored.state.lockUserAgent).toBe(false);
  });
});

