<script setup>
const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: "确认操作",
  },
  description: {
    type: String,
    default: "",
  },
  confirmText: {
    type: String,
    default: "确认",
  },
  cancelText: {
    type: String,
    default: "取消",
  },
  danger: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["confirm", "cancel"]);

function onCancel() {
  if (props.loading) return;
  emit("cancel");
}

function onConfirm() {
  if (props.loading) return;
  emit("confirm");
}
</script>

<template>
  <div
    v-if="open"
    data-test="confirm-dialog"
    class="fixed inset-0 z-[110] flex items-center justify-center p-4"
  >
    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="onCancel"></div>
    <div class="relative z-10 w-full max-w-md rounded-2xl border border-border-main bg-surface p-5 shadow-2xl">
      <h3 class="text-lg font-bold text-text-main">{{ title }}</h3>
      <p class="mt-2 text-sm text-text-secondary">{{ description }}</p>
      <div class="mt-5 flex items-center justify-end gap-2">
        <button
          data-test="confirm-dialog-cancel"
          class="rounded-lg border border-border-subtle px-4 py-2 text-sm text-text-secondary transition hover:bg-bg-secondary"
          :disabled="loading"
          @click="onCancel"
        >
          {{ cancelText }}
        </button>
        <button
          data-test="confirm-dialog-confirm"
          class="rounded-lg px-4 py-2 text-sm font-semibold text-white transition"
          :class="danger ? 'bg-state-error hover:bg-state-error/90' : 'bg-accent-1 hover:bg-accent-1/90'"
          :disabled="loading"
          @click="onConfirm"
        >
          <i v-if="loading" class="fas fa-spinner mr-2 animate-spin"></i>
          {{ confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>
