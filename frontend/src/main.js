import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from '@/stores/auth'
import '@fontsource/bangers'
import '@fontsource/bebas-neue'
import '@fontsource/inter'
import '@fontsource/space-grotesk'
import '@fortawesome/fontawesome-free/css/all.css'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const authStore = useAuthStore(pinia)
await authStore.bootstrap()

app.mount('#app')
