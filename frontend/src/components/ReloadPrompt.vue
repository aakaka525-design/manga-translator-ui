<script setup>
import { useRegisterSW } from 'virtual:pwa-register/vue'
import Toast from '@/components/ui/Toast.vue'
import { ref, watch } from 'vue'

const { offlineReady, needRefresh, updateServiceWorker } = useRegisterSW()
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

const close = async () => {
  offlineReady.value = false
  needRefresh.value = false
  showToast.value = false
}

// Watchers for PWA events
watch(offlineReady, (value) => {
  if (value) {
    toastMessage.value = '应用已就绪，可离线使用'
    toastType.value = 'success'
    showToast.value = true
    setTimeout(close, 3000)
  }
})

watch(needRefresh, (value) => {
  if (value) {
    toastMessage.value = '发现新版本，点击刷新'
    toastType.value = 'info'
    showToast.value = true
  }
})

const handleToastClick = () => {
    if (needRefresh.value) {
        updateServiceWorker()
    } else {
        close()
    }
}
</script>

<template>
  <Toast 
    :visible="showToast" 
    :message="toastMessage" 
    :type="toastType"
    @close="close"
    @click="handleToastClick"
    class="cursor-pointer"
  />
</template>
