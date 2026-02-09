<script setup>
import { ref, onMounted, onUnmounted, watch, useAttrs, computed } from 'vue'

// We want the parent `class=""` (and other attrs) to apply to the underlying <img>,
// not the wrapper <div>.
defineOptions({ inheritAttrs: false })

const props = defineProps({
  src: String,
  alt: {
    type: String,
    default: ''
  },
  threshold: {
    type: Number,
    default: 0.1
  }
})

const attrs = useAttrs()
const imgClass = computed(() => attrs.class)
const imgAttrs = computed(() => {
  // Remove `class` since we handle it explicitly via `imgClass`.
  // Everything else (e.g. loading/decoding) is forwarded to <img>.
  // eslint-disable-next-line no-unused-vars
  const { class: _klass, ...rest } = attrs
  return rest
})

const imgRef = ref(null)
const isVisible = ref(false)
const isLoaded = ref(false)
const error = ref(false)

let observer = null

onMounted(() => {
  if (!window.IntersectionObserver) {
    isVisible.value = true
    return
  }

  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      isVisible.value = true
      observer.disconnect()
    }
  }, {
    rootMargin: '50% 0px', // Load when within 50% viewport height
    threshold: props.threshold
  })

  if (imgRef.value) {
    observer.observe(imgRef.value)
  }
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

watch(() => props.src, () => {
  isLoaded.value = false
  error.value = false
})

const onLoad = () => {
  isLoaded.value = true
  error.value = false
}

const onError = () => {
  error.value = true
}
</script>

<template>
  <div ref="imgRef" class="relative overflow-hidden bg-bg-secondary/30 w-full h-full flex items-center justify-center">
    <!-- Placeholder / Skeleton -->
    <div v-if="!isLoaded && !error" class="absolute inset-0 loading-shell rounded-none">
      <div class="h-full w-full flex flex-col items-center justify-center gap-3 px-4">
        <i class="fas fa-image text-3xl text-text-secondary/35"></i>
        <span class="loading-line w-20"></span>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="absolute inset-0 flex flex-col items-center justify-center text-text-secondary">
        <i class="fas fa-exclamation-triangle text-2xl mb-2 text-state-error/50"></i>
        <span class="text-xs">加载失败</span>
    </div>

    <!-- Image -->
    <img 
      v-if="isVisible"
      :src="src" 
      :alt="alt"
      v-bind="imgAttrs"
      class="w-full h-full transition-opacity duration-300 block"
      :class="[imgClass, isLoaded ? 'opacity-100' : 'opacity-0']"
      @load="onLoad"
      @error="onError"
    />
  </div>
</template>
