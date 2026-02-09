<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: 'processing' },
  reason: { type: String, default: '' },
  warningCounts: { type: Object, default: () => ({}) }
})

const meta = {
  success: { color: 'bg-emerald-500/90', icon: 'fa-check', label: '成功' },
  not_started: { color: 'bg-slate-400/90', icon: 'fa-circle', label: '未开始' },
  no_text: { color: 'bg-slate-400/90', icon: 'fa-circle', label: '无文本' },
  failed: { color: 'bg-red-500/90', icon: 'fa-exclamation', label: '失败' },
  processing: { color: 'bg-blue-500/90', icon: 'fa-spinner', label: '处理中', spin: true },
  warning: { color: 'bg-yellow-400/90', icon: 'fa-triangle-exclamation', label: '警告' }
}

const info = computed(() => meta[props.status] || meta.processing)
</script>

<template>
  <div
    class="px-2 py-1 rounded-full text-[10px] font-semibold text-white shadow flex items-center gap-1"
    :class="info.color"
    :title="reason"
  >
    <i class="fas" :class="[info.icon, info.spin ? 'fa-spin' : '']"></i>
    <span>{{ info.label }}</span>
  </div>
</template>
