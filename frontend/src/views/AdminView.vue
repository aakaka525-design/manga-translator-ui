<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSessionToken } from '@/api'
import { useAuthStore } from '@/stores/auth'
import ComicBackground from '@/components/ui/ComicBackground.vue'
import GlassNav from '@/components/layout/GlassNav.vue'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const error = ref('')
const tasks = ref([])
const timer = ref(null)

const username = computed(() => authStore.user?.username || 'unknown')

async function fetchTasks() {
    loading.value = true
    error.value = ''
    try {
        const token = getSessionToken()
        const response = await fetch('/admin/tasks', {
            headers: {
                'X-Session-Token': token,
            },
        })

        if (!response.ok) {
            const payload = await response.json().catch(() => ({}))
            throw new Error(payload?.detail?.error?.message || payload?.detail || `请求失败 (${response.status})`)
        }

        const data = await response.json()
        tasks.value = Array.isArray(data) ? data : []
    } catch (err) {
        error.value = err.message || '任务获取失败'
    } finally {
        loading.value = false
    }
}

async function logout() {
    await authStore.logout()
    router.replace({ name: 'signin' })
}

onMounted(async () => {
    await fetchTasks()
    timer.value = setInterval(fetchTasks, 5000)
})

onUnmounted(() => {
    if (timer.value) clearInterval(timer.value)
})
</script>

<template>
  <div class="min-h-screen relative pb-10">
    <ComicBackground />
    <GlassNav title="管理控制台">
      <template #actions>
        <router-link
          :to="{ name: 'home' }"
          class="rounded-full px-3 py-1 text-xs font-semibold text-text-secondary transition hover:bg-white/10 hover:text-white"
        >
          返回书架
        </router-link>
        <button
          class="rounded-full bg-red-500/20 px-3 py-1 text-xs font-semibold text-red-200 transition hover:bg-red-500/30"
          @click="logout"
        >
          登出
        </button>
      </template>
    </GlassNav>

    <main class="container mx-auto px-4 py-6 space-y-6">
      <section class="rounded-xl border border-white/10 bg-black/45 p-4">
        <h2 class="mb-3 text-lg font-semibold text-white">系统状态</h2>
        <div class="grid gap-3 text-sm text-text-secondary sm:grid-cols-2">
          <div>当前用户：<span class="text-white">{{ username }}</span></div>
          <div>会话状态：<span class="text-green-300">在线</span></div>
        </div>
      </section>

      <section class="rounded-xl border border-white/10 bg-black/45 p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">任务监控</h2>
          <button
            class="rounded-lg border border-white/20 px-3 py-1 text-xs text-text-secondary transition hover:border-accent-1 hover:text-white"
            @click="fetchTasks"
          >
            刷新
          </button>
        </div>

        <p v-if="error" class="mb-3 text-sm text-red-300">{{ error }}</p>

        <div v-if="loading" class="py-6 text-sm text-text-secondary">加载中...</div>

        <div v-else-if="tasks.length === 0" class="py-6 text-sm text-text-secondary">暂无活动任务</div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-xs sm:text-sm">
            <thead>
              <tr class="text-text-secondary">
                <th class="px-2 py-2">Task ID</th>
                <th class="px-2 py-2">状态</th>
                <th class="px-2 py-2">用户</th>
                <th class="px-2 py-2">翻译器</th>
                <th class="px-2 py-2">时长(s)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in tasks" :key="task.task_id" class="border-t border-white/10">
                <td class="px-2 py-2 text-white">{{ task.task_id }}</td>
                <td class="px-2 py-2">{{ task.status }}</td>
                <td class="px-2 py-2">{{ task.username }}</td>
                <td class="px-2 py-2">{{ task.translator }}</td>
                <td class="px-2 py-2">{{ Number(task.duration || 0).toFixed(1) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>
