import axios from 'axios'

export const SESSION_TOKEN_KEY = 'mt.session.token'
export const SESSION_USER_KEY = 'mt.session.user'

export function getSessionToken() {
    if (typeof window === 'undefined') return ''
    return window.localStorage.getItem(SESSION_TOKEN_KEY) || ''
}

export function setSessionToken(token) {
    if (typeof window === 'undefined') return
    if (!token) {
        window.localStorage.removeItem(SESSION_TOKEN_KEY)
        return
    }
    window.localStorage.setItem(SESSION_TOKEN_KEY, token)
}

export function clearSessionToken() {
    if (typeof window === 'undefined') return
    window.localStorage.removeItem(SESSION_TOKEN_KEY)
    window.localStorage.removeItem(SESSION_USER_KEY)
}

const api = axios.create({
    baseURL: '/api/v1',
    timeout: 30000
})

function extractApiError(err) {
    const status = err?.response?.status
    const body = err?.response?.data || {}
    const headers = err?.response?.headers || {}

    let message = '请求失败'
    if (typeof body.detail === 'string' && body.detail.trim()) {
        message = body.detail
    } else if (typeof body.error?.message === 'string' && body.error.message.trim()) {
        message = body.error.message
    } else if (typeof err?.message === 'string' && err.message.trim()) {
        message = err.message
    }

    const error = new Error(message)
    error.status = status
    error.code = body.error?.code || err?.code || 'API_ERROR'
    error.requestId = body.error?.request_id || headers['x-request-id'] || null
    error.raw = body
    return error
}

api.interceptors.response.use(
    (response) => response,
    (err) => {
        if (err?.response?.status === 401) {
            clearSessionToken()
            if (typeof window !== 'undefined' && window.location.pathname !== '/signin') {
                window.location.href = '/signin'
            }
        }
        return Promise.reject(extractApiError(err))
    }
)

api.interceptors.request.use((config) => {
    const token = getSessionToken()
    if (token) {
        config.headers = config.headers || {}
        config.headers['X-Session-Token'] = token
    }
    return config
})

export const authApi = {
    login: async (username, password) => {
        const { data } = await axios.post('/auth/login', { username, password })
        return data
    },
    logout: async () => {
        const token = getSessionToken()
        if (!token) return { success: true }
        const { data } = await axios.post('/auth/logout', null, {
            headers: { 'X-Session-Token': token },
        })
        return data
    },
    check: async () => {
        const token = getSessionToken()
        if (!token) return { valid: false }
        const { data } = await axios.get('/auth/check', {
            headers: { 'X-Session-Token': token },
        })
        return data
    }
}

export const mangaApi = {
    // Get all mangas
    list: async () => {
        const { data } = await api.get('/manga')
        return data
    },

    // Get chapters for a manga
    getChapters: async (mangaId) => {
        const { data } = await api.get(`/manga/${mangaId}/chapters`)
        return data
    },

    // Get chapter details (pages)
    getChapter: async (mangaId, chapterId) => {
        const { data } = await api.get(`/manga/${mangaId}/chapter/${chapterId}`)
        return data
    },

    // Delete manga
    deleteManga: async (mangaId) => {
        const { data } = await api.delete(`/manga/${mangaId}`)
        return data
    },

    // Delete chapter
    deleteChapter: async (mangaId, chapterId) => {
        const { data } = await api.delete(`/manga/${mangaId}/chapter/${chapterId}`)
        return data
    }
}

export const translateApi = {
    // Translate a chapter
    translateChapter: async (payload) => {
        const { data } = await api.post('/translate/chapter', payload, { timeout: 60000 })
        return data
    },

    // Re-translate a single page
    retranslatePage: async (payload) => {
        const { data } = await api.post('/translate/page', payload, { timeout: 0 })
        return data
    },

    // Get SSE event source URL
    getEventsUrl: () => {
        const token = getSessionToken()
        if (!token) return '/api/v1/translate/events'
        return `/api/v1/translate/events?token=${encodeURIComponent(token)}`
    }
}

export const systemApi = {
    getLogs: async (lines = 100) => {
        const { data } = await api.get(`/system/logs?lines=${lines}`)
        return data
    }
}

export default api
