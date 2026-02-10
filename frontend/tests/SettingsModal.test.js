import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import SettingsModal from "@/components/SettingsModal.vue";
import { createPinia, setActivePinia } from "pinia";
import { SESSION_TOKEN_KEY } from "@/api";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    }),
  );
  localStorage.setItem(SESSION_TOKEN_KEY, "settings-modal-test-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

it("renders upscale controls", () => {
  setActivePinia(createPinia());
  const wrapper = mount(SettingsModal);
  expect(wrapper.find('[data-test="upscale-enable-toggle"]').exists()).toBe(true);
  expect(wrapper.find('[data-test="upscale-model-select"]').exists()).toBe(true);
  expect(wrapper.find('[data-test="upscale-scale-select"]').exists()).toBe(true);
});
