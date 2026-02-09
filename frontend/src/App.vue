<script setup>
import SettingsModal from '@/components/SettingsModal.vue'
import Toast from '@/components/ui/Toast.vue'
import ReloadPrompt from '@/components/ReloadPrompt.vue'
import { useToastStore } from '@/stores/toast'

const toastStore = useToastStore()
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-main">
    <router-view></router-view>
    <SettingsModal />
    <Toast :message="toastStore.message" :type="toastStore.type" :visible="toastStore.visible" @close="toastStore.close()" />
    <ReloadPrompt />
  </div>
</template>

<style>
/* Global styles if needed */
</style>
