import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import AdminView from '@/views/AdminView.vue'
import { SESSION_TOKEN_KEY } from '@/api'

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin', name: 'admin', component: { template: '<div />' } },
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/scraper', name: 'scraper', component: { template: '<div />' } },
      { path: '/signin', name: 'signin', component: { template: '<div />' } }
    ]
  })
}

describe('admin scraper panel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.setItem(SESSION_TOKEN_KEY, 'test-token')

    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (typeof url === 'string' && url.includes('/admin/scraper/tasks')) {
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                task_id: 'task-1',
                status: 'error',
                provider: 'generic',
                retry_count: 2,
                max_retries: 2,
                error_code: 'SCRAPER_RETRY_EXHAUSTED',
                updated_at: '2026-02-10T08:00:00+00:00'
              }
            ],
            total: 1,
            limit: 20,
            offset: 0,
            has_more: false
          })
        }
      }
      if (typeof url === 'string' && url.includes('/admin/scraper/metrics')) {
        return {
          ok: true,
          json: async () => ({
            hours: 24,
            total: 8,
            success: 5,
            partial: 1,
            error: 2,
            success_rate: 0.625,
            provider_breakdown: { generic: 4, toongod: 4 },
            error_code_breakdown: { SCRAPER_RETRY_EXHAUSTED: 2 }
          })
        }
      }
      if (typeof url === 'string' && url.includes('/admin/scraper/health')) {
        return {
          ok: true,
          json: async () => ({
            status: 'ok',
            db: { path: '/tmp/scraper_tasks.db', available: true },
            scheduler: { running: true, poll_interval_sec: 30, last_run_at: '2026-02-10T08:00:00+00:00' },
            alerts: { enabled: true, webhook_enabled: false, cooldown_sec: 300 },
            time: '2026-02-10T08:00:00+00:00'
          })
        }
      }
      if (typeof url === 'string' && url.includes('/admin/scraper/alerts?')) {
        return {
          ok: true,
          json: async () => ({
            items: [],
            total: 0,
            limit: 20,
            offset: 0,
            has_more: false
          })
        }
      }
      if (typeof url === 'string' && url.includes('/admin/scraper/queue/stats')) {
        return {
          ok: true,
          json: async () => ({
            pending: 0,
            running: 1,
            retrying: 0,
            done: 3,
            failed: 2,
            backlog: 1,
            oldest_pending_age_sec: 5
          })
        }
      }
      if (typeof url === 'string' && url.includes('/admin/tasks')) {
        return {
          ok: true,
          json: async () => []
        }
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({ detail: 'not found' })
      }
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.localStorage.removeItem(SESSION_TOKEN_KEY)
  })

  it('renders scraper monitor section and requests scraper endpoints', async () => {
    const router = createTestRouter()
    router.push('/admin')
    await router.isReady()

    const wrapper = mount(AdminView, {
      global: {
        plugins: [createPinia(), router]
      }
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Scraper 任务监控')
    expect(wrapper.text()).toContain('SCRAPER_RETRY_EXHAUSTED')

    const calledUrls = fetch.mock.calls.map(([url]) => String(url))
    expect(calledUrls.some((url) => url.startsWith('/admin/scraper/tasks'))).toBe(true)
    expect(calledUrls.some((url) => url.startsWith('/admin/scraper/metrics?hours=24'))).toBe(true)
    expect(calledUrls.some((url) => url.startsWith('/admin/scraper/health'))).toBe(true)
    expect(calledUrls.some((url) => url.startsWith('/admin/scraper/alerts?'))).toBe(true)
    expect(calledUrls.some((url) => url.startsWith('/admin/scraper/queue/stats'))).toBe(true)

    wrapper.unmount()
  })
})
