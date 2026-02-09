<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ComicBackground from '@/components/ui/ComicBackground.vue'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
    error.value = ''
    if (!username.value || !password.value) {
        error.value = '请输入用户名和密码'
        return
    }

    loading.value = true
    try {
        await authStore.login(username.value, password.value)
        router.replace({ name: 'home' })
    } catch (err) {
        error.value = err.message || '登录失败'
    } finally {
        loading.value = false
    }
}
</script>

<template>
  <div class="min-h-screen relative flex items-center justify-center px-4 py-10">
    <ComicBackground />

    <div class="relative z-10 w-full max-w-md rounded-2xl border border-white/10 bg-black/55 p-6 backdrop-blur-md">
      <h1 class="mb-1 font-heading text-3xl text-white">Manga Translator</h1>
      <p class="mb-6 text-sm text-text-secondary">登录后继续使用 Web 控制台</p>

      <form class="space-y-4" @submit.prevent="submit">
        <label class="block">
          <span class="mb-1 block text-xs text-text-secondary">用户名</span>
          <input
            v-model.trim="username"
            type="text"
            autocomplete="username"
            class="w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2 text-white outline-none transition focus:border-accent-1"
            placeholder="admin"
          />
        </label>

        <label class="block">
          <span class="mb-1 block text-xs text-text-secondary">密码</span>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2 text-white outline-none transition focus:border-accent-1"
            placeholder="••••••"
          />
        </label>

        <p v-if="error" class="text-sm text-red-300">{{ error }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded-lg bg-accent-1 px-4 py-2 text-sm font-bold text-white transition hover:brightness-110 disabled:opacity-60"
        >
          <span v-if="loading">登录中...</span>
          <span v-else>登录</span>
        </button>
      </form>
    </div>
  </div>
</template>
