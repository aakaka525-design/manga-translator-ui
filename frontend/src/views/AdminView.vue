<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSessionToken } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useAdminScraperStore } from '@/stores/adminScraper'
import ComicBackground from '@/components/ui/ComicBackground.vue'
import GlassNav from '@/components/layout/GlassNav.vue'

const router = useRouter()
const authStore = useAuthStore()
const scraperStore = useAdminScraperStore()

const loading = ref(false)
const error = ref('')
const tasks = ref([])
const timer = ref(null)

const username = computed(() => authStore.user?.username || 'unknown')
const scraperLoading = computed(() => scraperStore.state.loading)
const scraperError = computed(() => scraperStore.state.error)
const scraperTasks = computed(() => scraperStore.state.tasks)
const scraperMetrics = computed(() => scraperStore.state.metrics)
const scraperHealth = computed(() => scraperStore.state.health)
const scraperAlerts = computed(() => scraperStore.state.alerts)
const scraperQueueStats = computed(() => scraperStore.state.queueStats)
const webhookInput = ref('')
const webhookTesting = ref(false)
const webhookResult = ref('')

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

async function refreshAll() {
  await Promise.all([fetchTasks(), scraperStore.refresh()])
}

async function runWebhookTest() {
  webhookTesting.value = true
  webhookResult.value = ''
  try {
    const result = await scraperStore.sendTestWebhook(webhookInput.value)
    if (result.sent) {
      webhookResult.value = `Webhook 测试成功（attempts=${result.attempts}）`
    } else {
      webhookResult.value = `Webhook 测试失败：${result.message || 'unknown'}`
    }
  } catch (err) {
    webhookResult.value = err?.message || 'Webhook 测试失败'
  } finally {
    webhookTesting.value = false
  }
}

onMounted(async () => {
    await refreshAll()
    timer.value = setInterval(refreshAll, 5000)
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
            @click="refreshAll"
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

      <section class="rounded-xl border border-white/10 bg-black/45 p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">Scraper 任务监控</h2>
          <span class="text-xs text-text-secondary">最近 {{ scraperMetrics.hours || 24 }} 小时</span>
        </div>

        <div class="mb-3 grid gap-3 text-xs text-text-secondary sm:grid-cols-4">
          <div>总任务：<span class="text-white">{{ scraperMetrics.total || 0 }}</span></div>
          <div>成功：<span class="text-green-300">{{ scraperMetrics.success || 0 }}</span></div>
          <div>部分成功：<span class="text-yellow-300">{{ scraperMetrics.partial || 0 }}</span></div>
          <div>失败：<span class="text-red-300">{{ scraperMetrics.error || 0 }}</span></div>
        </div>

        <p v-if="scraperError" class="mb-3 text-sm text-red-300">{{ scraperError }}</p>
        <div v-if="scraperLoading" class="py-4 text-sm text-text-secondary">Scraper 指标加载中...</div>

        <div v-else-if="scraperTasks.length === 0" class="py-4 text-sm text-text-secondary">暂无 Scraper 任务</div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-xs sm:text-sm">
            <thead>
              <tr class="text-text-secondary">
                <th class="px-2 py-2">Task ID</th>
                <th class="px-2 py-2">状态</th>
                <th class="px-2 py-2">Provider</th>
                <th class="px-2 py-2">重试</th>
                <th class="px-2 py-2">错误码</th>
                <th class="px-2 py-2">更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in scraperTasks" :key="task.task_id" class="border-t border-white/10">
                <td class="px-2 py-2 text-white">{{ task.task_id }}</td>
                <td class="px-2 py-2">{{ task.status }}</td>
                <td class="px-2 py-2">{{ task.provider || '-' }}</td>
                <td class="px-2 py-2">{{ task.retry_count || 0 }} / {{ task.max_retries || 0 }}</td>
                <td class="px-2 py-2">{{ task.error_code || '-' }}</td>
                <td class="px-2 py-2">{{ task.updated_at || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="rounded-xl border border-white/10 bg-black/45 p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">Scraper 健康与队列</h2>
          <span class="text-xs" :class="scraperHealth.status === 'ok' ? 'text-green-300' : 'text-yellow-300'">
            {{ scraperHealth.status || 'unknown' }}
          </span>
        </div>

        <div class="grid gap-3 text-xs text-text-secondary sm:grid-cols-4">
          <div>pending：<span class="text-white">{{ scraperQueueStats.pending || 0 }}</span></div>
          <div>running：<span class="text-white">{{ scraperQueueStats.running || 0 }}</span></div>
          <div>retrying：<span class="text-white">{{ scraperQueueStats.retrying || 0 }}</span></div>
          <div>backlog：<span class="text-white">{{ scraperQueueStats.backlog || 0 }}</span></div>
          <div>done：<span class="text-green-300">{{ scraperQueueStats.done || 0 }}</span></div>
          <div>failed：<span class="text-red-300">{{ scraperQueueStats.failed || 0 }}</span></div>
          <div class="sm:col-span-2">
            oldest_pending_age_sec：
            <span class="text-white">{{ scraperQueueStats.oldest_pending_age_sec ?? '-' }}</span>
          </div>
        </div>

        <div class="mt-4 rounded-lg border border-white/10 bg-black/35 p-3 text-xs text-text-secondary">
          <div class="mb-2">数据库：<span class="text-white">{{ scraperHealth.db?.path || '-' }}</span></div>
          <div class="mb-2">
            调度器：
            <span class="text-white">
              {{ scraperHealth.scheduler?.running ? 'running' : 'stopped' }} / interval
              {{ scraperHealth.scheduler?.poll_interval_sec ?? '-' }}s
            </span>
          </div>
          <div class="mb-2">最近执行：<span class="text-white">{{ scraperHealth.scheduler?.last_run_at || '-' }}</span></div>
          <div>最近错误：<span class="text-red-300">{{ scraperHealth.scheduler?.last_error || '-' }}</span></div>
        </div>
      </section>

      <section class="rounded-xl border border-white/10 bg-black/45 p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-white">Scraper 告警</h2>
          <span class="text-xs text-text-secondary">最近 {{ scraperAlerts.length }} 条</span>
        </div>

        <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            v-model="webhookInput"
            type="text"
            placeholder="可选：临时 webhook URL"
            class="w-full rounded-lg border border-white/20 bg-black/35 px-3 py-2 text-xs text-white placeholder:text-text-secondary focus:border-accent-1 focus:outline-none"
          />
          <button
            class="rounded-lg border border-accent-1/40 px-3 py-2 text-xs text-white transition hover:border-accent-1 disabled:opacity-50"
            :disabled="webhookTesting"
            @click="runWebhookTest"
          >
            {{ webhookTesting ? '测试中...' : '测试 Webhook' }}
          </button>
        </div>
        <p v-if="webhookResult" class="mb-3 text-xs text-text-secondary">{{ webhookResult }}</p>

        <div v-if="scraperAlerts.length === 0" class="py-4 text-sm text-text-secondary">暂无告警</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-xs sm:text-sm">
            <thead>
              <tr class="text-text-secondary">
                <th class="px-2 py-2">ID</th>
                <th class="px-2 py-2">规则</th>
                <th class="px-2 py-2">级别</th>
                <th class="px-2 py-2">消息</th>
                <th class="px-2 py-2">Webhook</th>
                <th class="px-2 py-2">时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="alert in scraperAlerts" :key="alert.id" class="border-t border-white/10">
                <td class="px-2 py-2 text-white">{{ alert.id }}</td>
                <td class="px-2 py-2">{{ alert.rule }}</td>
                <td class="px-2 py-2" :class="alert.severity === 'error' ? 'text-red-300' : 'text-yellow-300'">
                  {{ alert.severity }}
                </td>
                <td class="px-2 py-2">{{ alert.message }}</td>
                <td class="px-2 py-2">{{ alert.webhook_status }} ({{ alert.webhook_attempts || 0 }})</td>
                <td class="px-2 py-2">{{ alert.created_at || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>
