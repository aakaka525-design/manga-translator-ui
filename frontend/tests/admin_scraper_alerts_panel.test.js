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

describe('admin scraper alerts panel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.setItem(SESSION_TOKEN_KEY, 'test-token')
    vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
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
            total: 2,
            success: 1,
            partial: 0,
            error: 1,
            success_rate: 0.5,
            provider_breakdown: { generic: 2 },
            error_code_breakdown: { SCRAPER_TASK_STALE: 1 }
          })
        }
      }
      if (target.startsWith('/admin/scraper/health')) {
        return {
          ok: true,
          json: async () => ({
            status: 'degraded',
            db: { path: '/tmp/scraper_tasks.db', available: true, error: null },
            scheduler: { running: true, poll_interval_sec: 30, last_error: null },
            alerts: { enabled: true, cooldown_sec: 300, webhook_enabled: true },
            time: '2026-02-10T08:00:00+00:00'
          })
        }
      }
      if (target.startsWith('/admin/scraper/queue/stats')) {
        return {
          ok: true,
          json: async () => ({
            pending: 0,
            running: 0,
            retrying: 0,
            done: 2,
            failed: 1,
            backlog: 0,
            oldest_pending_age_sec: null
          })
        }
      }
      if (target.startsWith('/admin/scraper/alerts?')) {
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                id: 11,
                rule: 'stale_detected',
                severity: 'error',
                message: 'Detected stale scraper task(s): 1',
                webhook_status: 'failed',
                webhook_attempts: 3,
                created_at: '2026-02-10T08:00:00+00:00'
              }
            ],
            total: 1,
            limit: 20,
            offset: 0,
            has_more: false
          })
        }
      }
      if (target.startsWith('/admin/scraper/alerts/test-webhook')) {
        expect(options.method).toBe('POST')
        return {
          ok: true,
          json: async () => ({
            sent: true,
            attempts: 1,
            status: 'sent',
            message: 'ok'
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

  it('renders alerts and supports webhook test action', async () => {
    const router = createTestRouter()
    router.push('/admin')
    await router.isReady()

    const wrapper = mount(AdminView, {
      global: {
        plugins: [createPinia(), router]
      }
    })

    await flushPromises()
    expect(wrapper.text()).toContain('Scraper 告警')
    expect(wrapper.text()).toContain('stale_detected')

    const button = wrapper
      .findAll('button')
      .find((item) => item.text().includes('测试 Webhook'))
    expect(button).toBeTruthy()
    await button.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Webhook 测试成功')
    expect(fetch.mock.calls.some(([url]) => String(url).startsWith('/admin/scraper/alerts/test-webhook'))).toBe(true)

    wrapper.unmount()
  })
})
