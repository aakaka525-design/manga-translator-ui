import { describe, it, expect, vi, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import SlicedImage from "../src/components/ui/SlicedImage.vue";

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const originalFetch = global.fetch;

afterEach(() => {
  if (originalFetch) {
    global.fetch = originalFetch;
  } else {
    delete global.fetch;
  }
});

describe("SlicedImage", () => {
  it("renders slices when index loads", async () => {
    const payload = {
      version: 1,
      original_width: 800,
      original_height: 1200,
      slice_height: 600,
      overlap: 12,
      slices: [
        { file: "slice_000.webp", y: 0, height: 600 },
        { file: "slice_001.webp", y: 588, height: 600 }
      ]
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(payload)
    });

    const wrapper = mount(SlicedImage, {
      props: { src: "/output/1_slices.json" }
    });

    await flush();
    await flush();

    const imgs = wrapper.findAll("img");
    expect(imgs.length).toBe(2);
    expect(imgs[0].attributes("src")).toBe("/output/1_slices/slice_000.webp");
    expect(imgs[1].attributes("src")).toBe("/output/1_slices/slice_001.webp");
    expect(imgs[1].attributes("style")).toContain("margin-top: -12px");
  });

  it("falls back to webp then original on error", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("nope"));

    const wrapper = mount(SlicedImage, {
      props: {
        src: "/output/1_slices.json",
        fallbackOriginal: "/output/1.png"
      }
    });

    await flush();

    const img = wrapper.find("img");
    expect(img.attributes("src")).toBe("/output/1.webp");

    await img.trigger("error");
    await flush();

    expect(wrapper.find("img").attributes("src")).toBe("/output/1.png");
  });
});
