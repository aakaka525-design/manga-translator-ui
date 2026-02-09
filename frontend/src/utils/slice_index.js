export function isSliceIndex(url) {
  return typeof url === "string" && url.endsWith("_slices.json");
}

export function sliceBaseDir(url) {
  return url.replace("_slices.json", "_slices/");
}

export function sliceFallback(url) {
  return url.replace("_slices.json", ".webp");
}
