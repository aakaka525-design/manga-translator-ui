<script setup>
defineProps({
  chapter: {
    type: Object,
    required: true
  },
  isSelected: {
    type: Boolean,
    default: false
  },
  status: {
    type: String,
    default: null
  },
  isBusy: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle', 'download'])

function statusLabel(s) {
    const map = { queued: '排队中', pending: '排队中', running: '下载中', success: '已完成', partial: '部分成功', error: '失败' }
    return map[s] || s || '暂无任务'
}

function statusClass(s) {
    const map = {
        success: 'bg-green-500/20 text-green-300 border border-green-500/30',
        partial: 'bg-amber-500/20 text-amber-300 border border-amber-500/30',
        error: 'bg-red-500/20 text-red-300 border border-red-500/30',
        running: 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
    }
    return map[s] || 'bg-slate-700/40 text-slate-300 border border-slate-500/30'
}

function downloadedLabel(chapter) {
    if (!chapter.downloaded_count) return ''
    if (chapter.downloaded_total > 0 && chapter.downloaded_count < chapter.downloaded_total) {
        return `已下载 ${chapter.downloaded_count}/${chapter.downloaded_total}`
    }
    return '已下载'
}

function downloadedClass(chapter) {
    if (!chapter.downloaded_count) return ''
    if (chapter.downloaded_total > 0 && chapter.downloaded_count < chapter.downloaded_total) {
        return 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
    }
    return 'bg-green-500/20 text-green-300 border border-green-500/30'
}
</script>

<template>
  <div 
    class="flex items-start justify-between border rounded-xl px-4 py-3 transition group select-none cursor-pointer relative overflow-hidden"
    :class="isSelected 
      ? 'bg-accent-1/10 border-accent-1/50' 
      : 'bg-bg-secondary/50 border-border-subtle hover:border-accent-1/30 hover:bg-bg-secondary/80'"
    @click="(e) => emit('toggle', chapter.id, e)"
  >
    <div class="flex items-center gap-3 overflow-hidden pointer-events-none">
      <!-- Checkbox -->
      <div class="relative flex items-center p-1">
          <input 
            type="checkbox" 
            :checked="isSelected" 
            readonly
            class="peer h-4 w-4 appearance-none rounded border border-border-subtle bg-bg-secondary checked:bg-accent-1 checked:border-accent-1 transition-all"
          />
          <i class="fas fa-check text-white text-[10px] absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 peer-checked:opacity-100"></i>
      </div>

      <!-- Info -->
      <div class="min-w-0">
        <p class="text-sm font-semibold text-text-main truncate transition-colors"
           :class="isSelected ? 'text-accent-1' : 'group-hover:text-accent-1'">
            {{ chapter.title || chapter.id }}
        </p>
        <p class="text-[11px] text-text-secondary truncate mt-0.5 font-mono opacity-70">
            {{ chapter.url }}
        </p>
      </div>
    </div>

    <!-- Actions / Status -->
    <div class="flex items-center gap-2 shrink-0">
      <!-- Downloaded Badge -->
      <span v-if="chapter.downloaded_count"
        class="text-[10px] font-semibold px-2 py-1 rounded-full border opacity-80"
        :class="downloadedClass(chapter)">
        {{ downloadedLabel(chapter) }}
      </span>

      <!-- Task Status Badge -->
      <span v-if="status"
        class="text-[10px] font-semibold px-2 py-1 rounded-full border animate-pulse-slow"
        :class="statusClass(status)">
        {{ statusLabel(status) }}
      </span>

      <!-- Action Button -->
      <button 
        @click.stop="emit('download', chapter)"
        :disabled="loading || isBusy"
        class="px-3 py-1.5 text-xs font-semibold rounded-full transition-all duration-300"
        :class="(loading || isBusy)
          ? 'opacity-40 cursor-not-allowed bg-bg-secondary text-text-secondary' 
          : 'bg-accent-1/10 text-accent-1 hover:bg-accent-1 hover:text-white'"
      >
        <span v-if="isBusy">
            <i class="fas fa-sync fa-spin mr-1"></i> 排队
        </span>
        <span v-else>
            加入队列
        </span>
      </button>
    </div>
  </div>
</template>
