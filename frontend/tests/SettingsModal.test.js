import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SettingsModal from "@/components/SettingsModal.vue";
import { createPinia, setActivePinia } from "pinia";

it("renders upscale controls", () => {
  setActivePinia(createPinia());
  const wrapper = mount(SettingsModal);
  expect(wrapper.find('[data-test="upscale-enable-toggle"]').exists()).toBe(true);
  expect(wrapper.find('[data-test="upscale-model-select"]').exists()).toBe(true);
  expect(wrapper.find('[data-test="upscale-scale-select"]').exists()).toBe(true);
});
