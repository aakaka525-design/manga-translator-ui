import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
    const message = ref('')
    const type = ref('info')
    const visible = ref(false)
    let timer = null

    function show(msg, toastType = 'info', duration = 3000) {
        if (timer) clearTimeout(timer)
        message.value = msg
        type.value = toastType
        visible.value = true
        timer = setTimeout(() => {
            visible.value = false
        }, duration)
    }

    function close() {
        if (timer) clearTimeout(timer)
        visible.value = false
    }

    return { message, type, visible, show, close }
})
