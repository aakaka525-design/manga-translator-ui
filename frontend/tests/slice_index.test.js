import { describe, it, expect } from "vitest";
import { isSliceIndex, sliceBaseDir, sliceFallback } from "../src/utils/slice_index.js";

describe("slice_index", () => {
  it("detects and derives slice paths", () => {
    expect(isSliceIndex("/output/1_slices.json")).toBe(true);
    expect(isSliceIndex("/output/1.webp")).toBe(false);
    expect(sliceBaseDir("/output/1_slices.json")).toBe("/output/1_slices/");
    expect(sliceFallback("/output/1_slices.json")).toBe("/output/1.webp");
  });
});
