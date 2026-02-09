import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useSettingsStore } from "@/stores/settings";

beforeEach(() => {
  setActivePinia(createPinia());
  vi.stubGlobal("fetch", vi.fn());
  localStorage.clear();
});

describe("settings store", () => {
  it("updates upscale settings and calls API", async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const store = useSettingsStore();
    await store.selectUpscaleModel({ id: "realesr-animevideov3-x4", name: "AnimeVideo v3" });
    await store.selectUpscaleScale(4);
    expect(fetch).toHaveBeenCalledWith("/api/v1/settings/upscale", expect.any(Object));
    const payload = JSON.parse(fetch.mock.calls.at(-1)[1].body);
    expect(payload.enabled).toBe(true);
    const saved = JSON.parse(localStorage.getItem("manhua_settings"));
    expect(saved.upscaleModel).toBe("realesr-animevideov3-x4");
    expect(saved.upscaleScale).toBe(4);
  });

  it("toggles upscale enabled state and persists it", async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const store = useSettingsStore();
    await store.setUpscaleEnabled(false);

    const payload = JSON.parse(fetch.mock.calls.at(-1)[1].body);
    expect(payload.enabled).toBe(false);

    const saved = JSON.parse(localStorage.getItem("manhua_settings"));
    expect(saved.upscaleEnabled).toBe(false);
  });

  it("normalizes invalid saved upscale scale before sending update", async () => {
    localStorage.setItem(
      "manhua_settings",
      JSON.stringify({
        upscaleModel: "realesrgan-x4plus-anime",
        upscaleScale: 3,
        upscaleEnabled: true
      })
    );

    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const store = useSettingsStore();
    await store.selectUpscaleModel({ id: "realesrgan-x4plus", name: "RealESRGAN x4plus" });

    const payload = JSON.parse(fetch.mock.calls.at(-1)[1].body);
    expect(payload.scale).toBe(4);
  });

  it("rolls back upscale model when API update fails", async () => {
    fetch.mockResolvedValue({ ok: false, status: 422 });
    const store = useSettingsStore();
    const originalModel = store.settings.upscaleModel;

    await store.selectUpscaleModel({ id: "realesr-animevideov3-x4", name: "AnimeVideo v3" });

    expect(store.settings.upscaleModel).toBe(originalModel);
  });

  it("updates scale to model-supported value when switching model", async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const store = useSettingsStore();
    await store.selectUpscaleScale(4);
    await store.selectUpscaleModel({ id: "realesr-animevideov3-x2", name: "AnimeVideo v3 x2" });

    const payload = JSON.parse(fetch.mock.calls.at(-1)[1].body);
    expect(payload.model).toBe("realesr-animevideov3-x2");
    expect(payload.scale).toBe(2);
  });
});
