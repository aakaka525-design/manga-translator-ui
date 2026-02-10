import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { SESSION_TOKEN_KEY } from '@/api'
import { useAdminScraperStore } from '@/stores/adminScraper'

describe('admin scraper store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.setItem(SESSION_TOKEN_KEY, 'test-token')
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      const target = String(url)
      if (target.startsWith('/admin/scraper/health')) {
        return {
          ok: true,
          json: async () => ({
            status: 'ok',
            db: { available: true },
            scheduler: { running: true, poll_interval_sec: 30 },
            alerts: { enabled: true, webhook_enabled: false },
            time: '2026-02-10T08:00:00+00:00'
          })
        }
      }
      if (target.startsWith('/admin/scraper/alerts?')) {
        return {
          ok: true,
          json: async () => ({
            items: [{ id: 1, rule: 'backlog_high', severity: 'warning', message: 'backlog high' }],
            total: 1,
            limit: 20,
            offset: 0,
            has_more: false
          })
        }
      }
      if (target.startsWith('/admin/scraper/queue/stats')) {
        return {
          ok: true,
          json: async () => ({
            pending: 1,
            running: 2,
            retrying: 3,
            done: 4,
            failed: 5,
            backlog: 6,
            oldest_pending_age_sec: 7
          })
        }
      }
      if (target.startsWith('/admin/scraper/alerts/test-webhook')) {
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
      if (target.startsWith('/admin/scraper/tasks')) {
        return {
          ok: true,
          json: async () => ({ items: [], total: 0, limit: 20, offset: 0, has_more: false })
        }
      }
      if (target.startsWith('/admin/scraper/metrics')) {
        return {
          ok: true,
          json: async () => ({
            hours: 24,
            total: 0,
            success: 0,
            partial: 0,
            error: 0,
            success_rate: 0,
            provider_breakdown: {},
            error_code_breakdown: {}
          })
        }
      }
      return {
        ok: false,
        status: 500,
        json: async () => ({ detail: 'unexpected url' })
      }
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.localStorage.removeItem(SESSION_TOKEN_KEY)
  })

  it('loads health, alerts, queue stats and can send webhook test', async () => {
    const store = useAdminScraperStore()
    await store.fetchHealth()
    await store.fetchAlerts()
    await store.fetchQueueStats()
    const result = await store.sendTestWebhook('https://example.org/hook')

    expect(store.state.health.status).toBe('ok')
    expect(store.state.alerts.length).toBe(1)
    expect(store.state.queueStats.backlog).toBe(6)
    expect(result.sent).toBe(true)
    expect(fetch).toHaveBeenCalled()
  })

  it('maps scraper alert error codes to friendly messages', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        detail: {
          code: 'SCRAPER_ALERT_STORE_ERROR',
          message: 'db locked'
        }
      })
    })

    const store = useAdminScraperStore()
    await expect(store.fetchAlerts()).rejects.toThrow(/告警存储读取失败/)
  })
})
