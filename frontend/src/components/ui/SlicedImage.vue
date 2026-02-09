<script setup>
import { ref, watch, computed } from "vue";
import { isSliceIndex, sliceBaseDir, sliceFallback } from "../../utils/slice_index.js";

const props = defineProps({
  src: String,
  fallbackOriginal: String
});

const mode = ref("single");
const slices = ref([]);
const overlap = ref(0);
const singleSrc = ref(props.src || "");

let requestId = 0;

const baseDir = computed(() => {
  if (!props.src) return "";
  return sliceBaseDir(props.src);
});

const isLoading = computed(() => mode.value === "loading");

function sliceStyle(index) {
  const overlapPx = Math.max(0, Number(overlap.value) || 0);
  if (index === 0 || overlapPx <= 0) return {};
  // Use white (not black) for the opaque region so the mask works in both alpha and luminance modes
  // across browsers. Some browsers interpret CSS masks via luminance where black means fully masked.
  const gradient = `linear-gradient(to bottom, transparent 0px, white ${overlapPx}px, white 100%)`;
  return {
    marginTop: `-${overlapPx}px`,
    maskImage: gradient,
    WebkitMaskImage: gradient,
    maskRepeat: "no-repeat",
    WebkitMaskRepeat: "no-repeat",
    maskSize: "100% 100%",
    WebkitMaskSize: "100% 100%"
  };
}

function onImageError() {
  if (mode.value === "fallback" && props.fallbackOriginal) {
    mode.value = "original";
    singleSrc.value = props.fallbackOriginal;
  }
}

async function loadIndex() {
  const src = props.src;
  if (!isSliceIndex(src)) {
    mode.value = "single";
    singleSrc.value = src || "";
    slices.value = [];
    overlap.value = 0;
    return;
  }

  const current = ++requestId;
  mode.value = "loading";
  slices.value = [];
  overlap.value = 0;

  try {
    const res = await fetch(src);
    if (!res.ok) {
      throw new Error(`Failed to load slice index: ${res.status}`);
    }
    const data = await res.json();
    if (current !== requestId) return;

    if (!data || !Array.isArray(data.slices) || data.slices.length === 0) {
      throw new Error("Invalid slice index");
    }

    slices.value = data.slices;
    overlap.value = Number(data.overlap) || 0;
    mode.value = "slices";
  } catch (err) {
    if (current !== requestId) return;
    mode.value = "fallback";
    singleSrc.value = sliceFallback(src);
  }
}

watch(
  () => props.src,
  () => {
    singleSrc.value = props.src || "";
    loadIndex();
  },
  { immediate: true }
);
</script>

<template>
  <div class="w-full">
    <div v-if="isLoading" class="w-full pb-[140%] loading-shell">
      <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 px-4">
        <i class="fas fa-images text-2xl text-text-secondary/30"></i>
        <span class="loading-line w-24"></span>
      </div>
    </div>

    <div v-else-if="mode === 'slices'" class="w-full">
      <img
        v-for="(slice, index) in slices"
        :key="slice.file"
        :src="baseDir + slice.file"
        :style="sliceStyle(index)"
        class="w-full h-auto block"
        :loading="index < 2 ? 'eager' : 'lazy'"
        decoding="async"
        draggable="false"
      />
    </div>

    <img
      v-else-if="singleSrc"
      :src="singleSrc"
      class="w-full h-auto block"
      loading="eager"
      decoding="async"
      draggable="false"
      @error="onImageError"
    />
  </div>
</template>
