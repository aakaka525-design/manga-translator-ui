import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
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

describe('admin scraper health queue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.setItem(SESSION_TOKEN_KEY, 'test-token')
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      const target = String(url)
      if (target.startsWith('/admin/tasks')) {
        return { ok: true, json: async () => [] }
      }
      if (target.startsWith('/admin/scraper/tasks')) {
        return { ok: true, json: async () => ({ items: [], total: 0, limit: 20, offset: 0, has_more: false }) }
      }
      if (target.startsWith('/admin/scraper/metrics')) {
        return {
          ok: true,
          json: async () => ({
            hours: 24,
            total: 10,
            success: 7,
            partial: 1,
            error: 2,
            success_rate: 0.7,
            provider_breakdown: { generic: 10 },
            error_code_breakdown: {}
          })
        }
      }
      if (target.startsWith('/admin/scraper/health')) {
        return {
          ok: true,
          json: async () => ({
            status: 'ok',
            db: { path: '/tmp/scraper_tasks.db', available: true, error: null },
            scheduler: { running: true, poll_interval_sec: 30, last_run_at: '2026-02-10T08:00:00+00:00', last_error: null },
            alerts: { enabled: true, cooldown_sec: 300, webhook_enabled: false },
            time: '2026-02-10T08:00:00+00:00'
          })
        }
      }
      if (target.startsWith('/admin/scraper/alerts')) {
        return { ok: true, json: async () => ({ items: [], total: 0, limit: 20, offset: 0, has_more: false }) }
      }
      if (target.startsWith('/admin/scraper/queue/stats')) {
        return {
          ok: true,
          json: async () => ({
            pending: 3,
            running: 2,
            retrying: 1,
            done: 8,
            failed: 2,
            backlog: 6,
            oldest_pending_age_sec: 12
          })
        }
      }
      return { ok: false, status: 404, json: async () => ({ detail: 'not found' }) }
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.localStorage.removeItem(SESSION_TOKEN_KEY)
  })

  it('renders scraper health and queue stats', async () => {
    const router = createTestRouter()
    router.push('/admin')
    await router.isReady()

    const wrapper = mount(AdminView, {
      global: {
        plugins: [createPinia(), router]
      }
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Scraper 健康与队列')
    expect(wrapper.text()).toContain('backlog')
    expect(wrapper.text()).toContain('6')
    expect(wrapper.text()).toContain('running / interval 30s')

    wrapper.unmount()
  })
})
