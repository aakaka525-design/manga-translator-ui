<script setup>
const props = defineProps({
  label: {
    type: String,
    default: "加载中..."
  },
  compact: {
    type: Boolean,
    default: false
  }
});
</script>

<template>
  <div class="comic-loading" :class="compact ? 'py-6' : 'py-20'">
    <div class="comic-loading__rings">
      <div class="comic-loading__ring"></div>
      <div class="comic-loading__ring comic-loading__ring--accent"></div>
      <div class="comic-loading__core">
        <i class="fas fa-bolt"></i>
      </div>
    </div>
    <span class="font-comic tracking-wider" :class="compact ? 'text-sm' : 'text-lg'">
      {{ label }}
    </span>
  </div>
</template>
