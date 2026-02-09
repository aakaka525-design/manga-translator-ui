<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  message: String,
  type: { type: String, default: 'info' }, // info, success, warning, error
  visible: Boolean
})

const emit = defineEmits(['close'])

const typeClasses = {
  info: 'bg-bg-secondary border-border-subtle text-text-main',
  success: 'bg-state-success/20 border-state-success/30 text-state-success',
  warning: 'bg-state-warning/20 border-state-warning/30 text-state-warning',
  error: 'bg-state-error/20 border-state-error/30 text-state-error'
}

const typeIcons = {
  info: 'fa-info-circle',
  success: 'fa-check-circle',
  warning: 'fa-exclamation-triangle',
  error: 'fa-times-circle'
}
</script>

<template>
  <Transition name="toast">
    <div v-if="visible" 
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-6 py-3 rounded-xl border shadow-xl flex items-center gap-3 min-w-[250px] backdrop-blur"
      :class="typeClasses[type]">
      <i class="fas" :class="typeIcons[type]"></i>
      <span class="text-sm font-medium">{{ message }}</span>
      <button @click="emit('close')" class="ml-auto text-text-secondary hover:text-text-main transition">
        <i class="fas fa-times text-xs"></i>
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 20px);
}
</style>
