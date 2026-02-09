import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import MangaListItem from "../src/views/scraper/MangaListItem.vue";

describe("scraper loading visuals", () => {
  it("uses unified loading shell in grid card overlay", () => {
    const wrapper = mount(MangaListItem, {
      props: {
        manga: { id: "m1", title: "Demo", url: "https://example.com" },
        variant: "grid",
        loading: true
      }
    });

    expect(wrapper.find(".loading-shell").exists()).toBe(true);
    expect(wrapper.find(".loading-line").exists()).toBe(true);
  });
});
