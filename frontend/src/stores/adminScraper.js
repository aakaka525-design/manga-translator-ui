import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { getSessionToken } from '@/api'

function _authHeaders() {
  const token = getSessionToken()
  const headers = {}
  if (token) {
    headers['X-Session-Token'] = token
  }
  return headers
}

async function _jsonOrEmpty(response) {
  try {
    return await response.json()
  } catch (_err) {
    return {}
  }
}

export const useAdminScraperStore = defineStore('admin-scraper', () => {
  const state = reactive({
    loading: false,
    error: '',
    tasks: [],
    total: 0,
    limit: 20,
    offset: 0,
    hasMore: false,
    metrics: {
      hours: 24,
      total: 0,
      success: 0,
      partial: 0,
      error: 0,
      success_rate: 0,
      provider_breakdown: {},
      error_code_breakdown: {}
    }
  })

  async function fetchTasks(params = {}) {
    const query = new URLSearchParams()
    if (params.status) query.set('status', params.status)
    if (params.provider) query.set('provider', params.provider)
    query.set('limit', String(params.limit || state.limit || 20))
    query.set('offset', String(params.offset || state.offset || 0))

    const suffix = query.toString() ? `?${query.toString()}` : ''
    const response = await fetch(`/admin/scraper/tasks${suffix}`, {
      headers: _authHeaders()
    })
    if (!response.ok) {
      const payload = await _jsonOrEmpty(response)
      const detail = payload?.detail
      throw new Error(typeof detail === 'string' ? detail : `Scraper 任务获取失败 (${response.status})`)
    }

    const data = await response.json()
    state.tasks = Array.isArray(data?.items) ? data.items : []
    state.total = Number(data?.total || 0)
    state.limit = Number(data?.limit || 20)
    state.offset = Number(data?.offset || 0)
    state.hasMore = Boolean(data?.has_more)
    return data
  }

  async function fetchMetrics(hours = 24) {
    const response = await fetch(`/admin/scraper/metrics?hours=${encodeURIComponent(String(hours))}`, {
      headers: _authHeaders()
    })
    if (!response.ok) {
      const payload = await _jsonOrEmpty(response)
      const detail = payload?.detail
      throw new Error(typeof detail === 'string' ? detail : `Scraper 指标获取失败 (${response.status})`)
    }

    const data = await response.json()
    state.metrics = {
      ...state.metrics,
      ...data,
      provider_breakdown: data?.provider_breakdown || {},
      error_code_breakdown: data?.error_code_breakdown || {}
    }
    return data
  }

  async function refresh() {
    state.loading = true
    state.error = ''
    try {
      await Promise.all([fetchTasks(), fetchMetrics(state.metrics.hours || 24)])
    } catch (err) {
      state.error = err?.message || 'Scraper 监控刷新失败'
    } finally {
      state.loading = false
    }
  }

  return {
    state,
    fetchTasks,
    fetchMetrics,
    refresh
  }
})
