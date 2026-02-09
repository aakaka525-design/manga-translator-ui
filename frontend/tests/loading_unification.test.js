import { describe, it, expect, vi, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import ComicLoading from "../src/components/ui/ComicLoading.vue";
import LazyImage from "../src/components/ui/LazyImage.vue";
import SlicedImage from "../src/components/ui/SlicedImage.vue";
import SkeletonCard from "../src/views/scraper/SkeletonCard.vue";

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const originalFetch = global.fetch;
const originalIntersectionObserver = global.IntersectionObserver;

afterEach(() => {
  if (originalFetch) {
    global.fetch = originalFetch;
  } else {
    delete global.fetch;
  }

  if (originalIntersectionObserver) {
    global.IntersectionObserver = originalIntersectionObserver;
  } else {
    delete global.IntersectionObserver;
  }
});

describe("loading visual unification", () => {
  it("uses unified root and label in ComicLoading", () => {
    const wrapper = mount(ComicLoading, {
      props: { label: "章节加载中" }
    });

    expect(wrapper.find(".comic-loading").exists()).toBe(true);
    expect(wrapper.text()).toContain("章节加载中");
  });

  it("uses shared loading shell in LazyImage placeholder", async () => {
    global.IntersectionObserver = class {
      constructor(callback) {
        this.callback = callback;
      }

      observe() {
        this.callback([{ isIntersecting: true }]);
      }

      disconnect() {}
    };

    const wrapper = mount(LazyImage, {
      props: { src: "/foo.webp" }
    });

    await flush();
    expect(wrapper.find(".loading-shell").exists()).toBe(true);
  });

  it("uses shared loading shell when SlicedImage is loading index", async () => {
    global.fetch = vi.fn(() => new Promise(() => {}));

    const wrapper = mount(SlicedImage, {
      props: { src: "/output/1_slices.json" }
    });

    await flush();
    expect(wrapper.find(".loading-shell").exists()).toBe(true);
  });

  it("uses shared loading skeleton structure in scraper cards", () => {
    const wrapper = mount(SkeletonCard);
    expect(wrapper.find(".loading-shell").exists()).toBe(true);
    expect(wrapper.findAll(".loading-line").length).toBeGreaterThan(0);
  });
});
