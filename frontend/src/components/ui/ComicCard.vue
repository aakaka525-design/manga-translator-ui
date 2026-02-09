<script setup>
import LazyImage from '@/components/ui/LazyImage.vue'

defineProps({
  title: String,
  cover: String,
  chapterCount: {
    type: Number,
    default: 0
  },
  size: {
    type: String,
    default: 'normal' // normal, large, wide
  }
})

const emit = defineEmits(['click'])
</script>

<template>
  <div 
    class="comic-card group cursor-pointer relative"
    :class="size"
    @click="emit('click')"
  >
    <div class="relative overflow-hidden aspect-[3/4]">
      <LazyImage 
        :src="cover || '/static/placeholder.svg'" 
        class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
        :alt="title"
      />
      <!-- Gradient Overlay -->
      <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-80 decoration-slice"></div>
      
      <!-- Content -->
      <div class="absolute bottom-0 left-0 p-4 w-full">
        <h3 class="font-comic text-xl text-white leading-tight mb-1 drop-shadow-md line-clamp-2">{{ title }}</h3>
        <p class="text-xs text-slate-300 font-mono flex items-center gap-1">
          <i class="fas fa-book-open"></i> {{ chapterCount }} Chapters
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.comic-card {
  @apply bg-surface rounded-lg overflow-hidden shadow-comic;
  border-width: var(--card-border-width);
  border-color: var(--card-border-color);
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.comic-card:hover {
  transform: translate(-2px, -2px);
  @apply shadow-comic-hover;
}

/* Bento Grid Sizes */
.comic-card.large {
  grid-column: span 2;
  grid-row: span 2;
}

.comic-card.wide {
  grid-column: span 2;
}
</style>
