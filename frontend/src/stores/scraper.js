import { defineStore } from 'pinia'
import { ref, reactive, computed, watch } from 'vue'
import { useToastStore } from '@/stores/toast'
import { getSessionToken } from '@/api'

function authFetch(url, options = {}) {
    const token = getSessionToken()
    const headers = new Headers(options.headers || {})
    if (token && !headers.has('X-Session-Token')) {
        headers.set('X-Session-Token', token)
    }
    return fetch(url, { ...options, headers })
}

const SCRAPER_ERROR_MESSAGE_MAP = {
    SCRAPER_AUTH_CHALLENGE: '站点触发验证，请先到认证页完成验证后重试',
    SCRAPER_CATALOG_UNSUPPORTED: '当前站点不支持目录浏览',
    SCRAPER_STATE_FILE_TYPE_INVALID: '仅支持上传 JSON 状态文件',
    SCRAPER_STATE_FILE_TOO_LARGE: '状态文件过大（最大 2MB）',
    SCRAPER_STATE_JSON_INVALID: '状态文件不是有效 JSON',
    SCRAPER_STATE_COOKIE_MISSING: '状态文件中没有可用 cookie',
    SCRAPER_IMAGE_SOURCE_UNSUPPORTED: '封面来源不受支持，已跳过代理',
    SCRAPER_IMAGE_FETCH_FORBIDDEN: '封面抓取失败，请检查 cookie 是否有效',
    SCRAPER_TASK_NOT_FOUND: '下载任务不存在或已过期'
}

function _withRequestId(message, requestId) {
    if (!requestId) return message
    return `${message} (RID: ${requestId})`
}

function _friendlyErrorMessage({ code, detailMessage, fallbackMessage, requestId }) {
    const mapped = (code && SCRAPER_ERROR_MESSAGE_MAP[code]) || ''
    const base = mapped || detailMessage || fallbackMessage
    return _withRequestId(base, requestId)
}

async function _buildApiError(res, fallbackMessage) {
    let payload = {}
    try {
        payload = await res.json()
    } catch (e) {
        payload = {}
    }
    const detail = payload?.detail
    const detailCode = detail && typeof detail === 'object' ? detail.code : ''
    const detailMessage = detail && typeof detail === 'object'
        ? (detail.message || '')
        : (typeof detail === 'string' ? detail : '')
    const requestId = payload?.error?.request_id || ''
    const code = detailCode || payload?.error?.code || ''

    const message = _friendlyErrorMessage({
        code,
        detailMessage,
        fallbackMessage,
        requestId
    })
    const error = new Error(message)
    error.status = res.status
    error.code = code
    error.requestId = requestId
    error.raw = payload
    return error
}

const api = {
    async search(payload) {
        const res = await authFetch('/api/v1/scraper/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        if (!res.ok) throw await _buildApiError(res, '搜索失败')
        return res.json()
    },
    async chapters(payload) {
        const res = await authFetch('/api/v1/scraper/chapters', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        if (!res.ok) throw await _buildApiError(res, '获取章节失败')
        return res.json()
    },
    async catalog(payload) {
        const res = await authFetch('/api/v1/scraper/catalog', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        if (!res.ok) throw await _buildApiError(res, '加载目录失败')
        return res.json()
    },
    async stateInfo(payload) {
        const res = await authFetch('/api/v1/scraper/state-info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        if (!res.ok) throw await _buildApiError(res, '状态检查失败')
        return res.json()
    },
    async accessCheck(payload) {
        const res = await authFetch('/api/v1/scraper/access-check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        if (!res.ok) throw await _buildApiError(res, '站点访问检测失败')
        return res.json()
    },
    async uploadState(formData) {
        const res = await authFetch('/api/v1/scraper/upload-state', {
            method: 'POST',
            body: formData
        })
        if (!res.ok) throw await _buildApiError(res, '上传状态文件失败')
        return res.json()
    },
    async authUrl() {
        const res = await authFetch('/api/v1/scraper/auth-url')
        if (!res.ok) throw await _buildApiError(res, '认证地址获取失败')
        return res.json()
    },
    async download(payload) {
        const res = await authFetch('/api/v1/scraper/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        if (!res.ok) throw await _buildApiError(res, '提交下载失败')
        return res.json()
    },
    async taskStatus(taskId) {
        const res = await authFetch(`/api/v1/scraper/task/${taskId}`)
        if (!res.ok) throw await _buildApiError(res, '任务状态获取失败')
        return res.json()
    }
}

const parserApi = {
    async parse(url, mode) {
        const res = await authFetch('/api/v1/parser/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, mode })
        })
        if (!res.ok) throw new Error((await res.json()).detail || 'Parse failed')
        return res.json()
    },
    async list(url, mode) {
        const res = await authFetch('/api/v1/parser/list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, mode })
        })
        if (!res.ok) throw new Error((await res.json()).detail || 'Parse list failed')
        return res.json()
    }
}

const SCRAPER_SETTINGS_STORAGE_KEY = 'manhua:scraper:settings:v1'
const SCRAPER_DEFAULT_STATE = {
    site: 'toongod',
    baseUrl: 'https://toongod.org',
    mode: 'headless',
    httpMode: false,
    headless: true,
    manualChallenge: false,
    storageStatePath: 'data/toongod_state.json',
    useProfile: true,
    userDataDir: 'data/toongod_profile',
    lockUserAgent: true,
    userAgent: '',
    useChromeChannel: true,
    concurrency: 6,
    rateLimitRps: 2,
    keyword: '',
    view: 'search'
}
const SCRAPER_PERSISTED_KEYS = Object.keys(SCRAPER_DEFAULT_STATE)

function normalizePersistedSettings(value) {
    if (!value || typeof value !== 'object') return {}
    const out = {}
    for (const key of SCRAPER_PERSISTED_KEYS) {
        if (!(key in value)) continue
        const next = value[key]
        if (typeof SCRAPER_DEFAULT_STATE[key] === 'boolean') {
            out[key] = Boolean(next)
            continue
        }
        if (typeof SCRAPER_DEFAULT_STATE[key] === 'number') {
            const n = Number(next)
            if (!Number.isFinite(n)) continue
            if (key === 'concurrency') out[key] = Math.max(1, Math.min(32, n))
            else if (key === 'rateLimitRps') out[key] = Math.max(0.2, Math.min(20, n))
            else out[key] = n
            continue
        }
        out[key] = String(next)
    }
    return out
}

function loadPersistedSettings() {
    if (typeof window === 'undefined') return {}
    try {
        const raw = window.localStorage.getItem(SCRAPER_SETTINGS_STORAGE_KEY)
        if (!raw) return {}
        return normalizePersistedSettings(JSON.parse(raw))
    } catch (e) {
        return {}
    }
}

function savePersistedSettings(state) {
    if (typeof window === 'undefined') return
    try {
        const payload = {}
        for (const key of SCRAPER_PERSISTED_KEYS) {
            payload[key] = state[key]
        }
        window.localStorage.setItem(SCRAPER_SETTINGS_STORAGE_KEY, JSON.stringify(payload))
    } catch (e) {
        // Ignore storage quota/security errors.
    }
}

function _safeHostname(value) {
    if (!value) return ''
    try {
        return new URL(value).hostname.toLowerCase()
    } catch (e) {
        return ''
    }
}

function _isSubdomain(host, domain) {
    if (!host || !domain) return false
    return host === domain || host.endsWith(`.${domain}`)
}

function _isWpCdnForAllowedSite(url, allowedHosts) {
    try {
        const parsed = new URL(url)
        const host = parsed.hostname.toLowerCase()
        if (!(host === 'wp.com' || host.endsWith('.wp.com'))) return false
        const path = parsed.pathname.toLowerCase()
        return allowedHosts.some(site => path.includes(`/${site}/`))
    } catch (e) {
        return false
    }
}

function _shouldUseImageProxy(url, baseUrl) {
    const host = _safeHostname(url)
    if (!host) return false

    const allowedHosts = new Set(['toongod.org', 'mangaforfree.com'])
    const baseHost = _safeHostname(baseUrl)
    if (baseHost) allowedHosts.add(baseHost)
    const allowedList = Array.from(allowedHosts)

    if (allowedList.some(site => _isSubdomain(host, site))) return true
    if (_isWpCdnForAllowedSite(url, allowedList)) return true
    return false
}

export const useScraperStore = defineStore('scraper', () => {
    const state = reactive({
        ...SCRAPER_DEFAULT_STATE,
        ...loadPersistedSettings()
    })

    watch(
        () => ({
            site: state.site,
            baseUrl: state.baseUrl,
            mode: state.mode,
            httpMode: state.httpMode,
            headless: state.headless,
            manualChallenge: state.manualChallenge,
            storageStatePath: state.storageStatePath,
            useProfile: state.useProfile,
            userDataDir: state.userDataDir,
            lockUserAgent: state.lockUserAgent,
            userAgent: state.userAgent,
            useChromeChannel: state.useChromeChannel,
            concurrency: state.concurrency,
            rateLimitRps: state.rateLimitRps,
            keyword: state.keyword,
            view: state.view
        }),
        () => savePersistedSettings(state),
        { deep: true }
    )

    const loading = ref(false)
    const error = ref('')
    const results = ref([])
    const selectedManga = ref(null)
    const selectedMangaSource = ref('scraper')
    const selectedMangaContext = ref(null)
    const chapters = ref([])
    const selectedIds = ref([])
    const queue = ref([])
    const tasks = reactive({})
    const catalog = reactive({
        items: [],
        page: 1,
        hasMore: false,
        loading: false,
        orderby: null,
        path: null,
        mode: 'all'
    })
    const stateInfo = reactive({
        status: 'idle',
        message: '',
        cookieName: null,
        expiresAt: null,
        expiresAtText: '',
        expiresInSec: null,
        remainingText: ''
    })
    const accessInfo = reactive({
        status: 'idle',
        httpStatus: null,
        message: ''
    })
    const authInfo = reactive({
        url: '',
        status: 'idle',
        message: ''
    })
    const uploadInfo = reactive({
        status: 'idle',
        message: ''
    })
    const parser = reactive({
        url: '',
        mode: 'http',
        loading: false,
        error: '',
        result: null,
        showAll: false,
        context: {
            baseUrl: '',
            host: '',
            site: '',
            recognized: false,
            downloadable: false,
            storageStatePath: null,
            userDataDir: null
        }
    })
    const downloadSummary = computed(() => {
        const total = chapters.value.length
        const done = chapters.value.filter(chapter => chapter.downloaded_count > 0).length
        return { total, done }
    })

    const task = reactive({
        id: null,
        chapterId: null,
        mangaId: null,
        chapterKey: null,
        status: null,
        message: '',
        report: null
    })
    let pollTimer = null

    function chapterTaskKey(chapterId, mangaId = null) {
        return `${mangaId || '__unknown__'}::${chapterId}`
    }

    function activeMangaId() {
        return selectedManga.value?.id || null
    }

    function setSite(site) {
        state.site = site
        error.value = ''
        if (site === 'mangaforfree') {
            state.baseUrl = 'https://mangaforfree.com'
            state.storageStatePath = 'data/mangaforfree_state.json'
            if (!state.userDataDir || state.userDataDir.includes('toongod_profile')) {
                state.userDataDir = 'data/mangaforfree_profile'
            }
        } else if (site === 'toongod') {
            state.baseUrl = 'https://toongod.org'
            state.storageStatePath = 'data/toongod_state.json'
            if (!state.userDataDir || state.userDataDir.includes('mangaforfree_profile')) {
                state.userDataDir = 'data/toongod_profile'
            }
        }
        results.value = []
        chapters.value = []
        selectedManga.value = null
        selectedIds.value = []
        catalog.items = []
        catalog.page = 1
        catalog.hasMore = false
        applyCatalogMode()
        checkStateInfo()
        ensureUserAgent()
        loadCatalog(true)
    }

    function setMode(mode) {
        state.mode = mode
        if (mode === 'headed') {
            state.httpMode = false
            state.headless = false
            state.manualChallenge = true
        } else if (mode === 'headless') {
            state.httpMode = false
            state.headless = true
            state.manualChallenge = false
        } else {
            state.httpMode = true
            state.headless = true
            state.manualChallenge = false
        }
    }

    function getBrowserUserAgent() {
        if (typeof navigator === 'undefined') return ''
        return navigator.userAgent || ''
    }

    function syncUserAgent() {
        const ua = getBrowserUserAgent()
        if (ua) {
            state.userAgent = ua
        }
    }

    function ensureUserAgent() {
        if (!state.lockUserAgent) return
        if (state.userAgent && state.userAgent.trim()) return
        syncUserAgent()
    }

    function getCatalogBasePath() {
        if (state.site === 'toongod') return '/webtoon/'
        return '/manga/'
    }

    function applyCatalogMode() {
        const basePath = getCatalogBasePath()
        if (catalog.mode === 'views') {
            catalog.path = basePath
            catalog.orderby = 'views'
        } else if (catalog.mode === 'new') {
            catalog.path = basePath
            catalog.orderby = 'new-manga'
        } else if (catalog.mode === 'genre-manga') {
            catalog.path = '/manga-genre/manga/'
            catalog.orderby = null
        } else if (catalog.mode === 'genre-webtoon') {
            catalog.path = '/manga-genre/webtoon/'
            catalog.orderby = null
        } else {
            catalog.path = basePath
            catalog.orderby = null
        }
    }

    function setView(view) {
        state.view = view
        if (view === 'catalog' && catalog.items.length === 0) {
            loadCatalog(true)
        }
        if (view === 'settings') {
            ensureUserAgent()
        }
        if (view === 'auth') {
            resolveAuthUrl()
        }
    }

    function setCatalogMode(mode) {
        catalog.mode = mode
        applyCatalogMode()
        loadCatalog(true)
    }

    function getPayload() {
        const rateLimitRps = normalizeRateLimitRps(state.rateLimitRps)
        return {
            base_url: state.baseUrl,
            http_mode: state.httpMode,
            headless: state.headless,
            manual_challenge: state.manualChallenge,
            storage_state_path: state.storageStatePath || null,
            user_data_dir: state.useProfile ? (state.userDataDir || null) : null,
            user_agent: state.lockUserAgent ? (state.userAgent || null) : null,
            browser_channel: (!state.httpMode && state.useChromeChannel) ? 'chrome' : null,
            concurrency: state.concurrency,
            rate_limit_rps: rateLimitRps
        }
    }

    function getParserPayload(context = parser.context) {
        const httpMode = parser.mode === 'http'
        const rateLimitRps = normalizeRateLimitRps(state.rateLimitRps)
        return {
            base_url: context.baseUrl || '',
            http_mode: httpMode,
            headless: !httpMode,
            manual_challenge: false,
            storage_state_path: context.storageStatePath || null,
            user_data_dir: context.userDataDir || null,
            user_agent: null,
            browser_channel: null,
            concurrency: state.concurrency,
            rate_limit_rps: rateLimitRps
        }
    }

    function normalizeRateLimitRps(value) {
        const numeric = Number(value)
        if (!Number.isFinite(numeric)) return 2
        return Math.max(0.2, Math.min(20, numeric))
    }

    function getActivePayload() {
        if (selectedMangaSource.value === 'parser') {
            return getParserPayload(selectedMangaContext.value || parser.context)
        }
        return getPayload()
    }

    function proxyImageUrl(url) {
        if (!url) return ''
        if (url.startsWith('data:') || url.startsWith('blob:')) return url
        if (url.startsWith(window.location.origin)) return url
        if (!_shouldUseImageProxy(url, state.baseUrl)) return url
        const token = getSessionToken()
        const params = new URLSearchParams({
            url,
            base_url: state.baseUrl,
            storage_state_path: state.storageStatePath || ''
        })
        if (token) params.set('token', token)
        if (state.useProfile && state.userDataDir) {
            params.set('user_data_dir', state.userDataDir)
        }
        if (!state.httpMode && state.useChromeChannel) {
            params.set('browser_channel', 'chrome')
        }
        if (state.lockUserAgent && state.userAgent) {
            params.set('user_agent', state.userAgent)
        }
        return `/api/v1/scraper/image?${params.toString()}`
    }

    function proxyParserImageUrl(url) {
        if (!url) return ''
        if (url.startsWith('data:') || url.startsWith('blob:')) return url
        if (url.startsWith(window.location.origin)) return url
        const parserBaseUrl = parser.context.baseUrl || state.baseUrl
        if (!_shouldUseImageProxy(url, parserBaseUrl)) return url
        const token = getSessionToken()
        const params = new URLSearchParams({
            url,
            base_url: parserBaseUrl,
            storage_state_path: parser.context.storageStatePath || ''
        })
        if (token) params.set('token', token)
        if (parser.context.userDataDir) {
            params.set('user_data_dir', parser.context.userDataDir)
        }
        return `/api/v1/scraper/image?${params.toString()}`
    }

    function mapCoverWithProxy(item, proxyFn) {
        if (!item || typeof item !== 'object') return item
        const rawCover = item.cover_url || item.cover
        if (!rawCover) return item
        const proxiedCover = proxyFn(rawCover)
        return {
            ...item,
            cover_url: proxiedCover,
            cover: proxiedCover,
            cover_raw_url: rawCover
        }
    }

    function mapItemsCoverWithProxy(items, proxyFn) {
        if (!Array.isArray(items)) return []
        return items.map(item => mapCoverWithProxy(item, proxyFn))
    }

    function normalizeUrlInput(value) {
        const raw = (value || '').trim()
        if (!raw) return ''
        if (raw.startsWith('http://') || raw.startsWith('https://')) return raw
        return `https://${raw}`
    }

    function getParserDefaults(site) {
        if (site === 'mangaforfree') {
            return {
                storage_state_path: 'data/mangaforfree_state.json',
                user_data_dir: 'data/mangaforfree_profile'
            }
        }
        if (site === 'toongod') {
            return {
                storage_state_path: 'data/toongod_state.json',
                user_data_dir: 'data/toongod_profile'
            }
        }
        return { storage_state_path: null, user_data_dir: null }
    }

    function deriveParserContext(url, listResult) {
        let host = ''
        let baseUrl = ''
        try {
            const parsed = new URL(url)
            host = parsed.hostname || ''
            baseUrl = parsed.origin || ''
        } catch (e) {
            host = ''
            baseUrl = ''
        }
        const site = listResult?.site || listResult?.parser?.site || ''
        const recognized = listResult?.recognized ?? listResult?.parser?.recognized ?? false
        const downloadable = listResult?.downloadable ?? listResult?.parser?.downloadable ?? false
        const defaults = getParserDefaults(site)
        return {
            baseUrl,
            host,
            site,
            recognized,
            downloadable,
            storageStatePath: defaults.storage_state_path,
            userDataDir: defaults.user_data_dir
        }
    }

    function resetParserContext() {
        Object.assign(parser.context, {
            baseUrl: '',
            host: '',
            site: '',
            recognized: false,
            downloadable: false,
            storageStatePath: null,
            userDataDir: null
        })
    }

    async function search() {
        const toast = useToastStore()
        if (state.view !== 'search') {
            state.view = 'search'
        }
        ensureUserAgent()
        checkStateInfo()
        const kw = state.keyword.trim()
        if (!kw) {
            toast.show('请输入关键词', 'warning')
            error.value = '请输入关键词';
            return
        }
        loading.value = true
        error.value = ''
        results.value = []
        chapters.value = []
        selectedManga.value = null
        try {
            if (kw.startsWith('http')) {
                const url = new URL(kw)
                state.baseUrl = url.origin
                const id = url.pathname.split('/').filter(Boolean).pop() || url.hostname
                const manga = { id, title: id, url: kw }
                results.value = [manga]
                await selectManga(manga)
            } else {
                const found = await api.search({ ...getPayload(), keyword: kw })
                results.value = mapItemsCoverWithProxy(found, proxyImageUrl)
            }
        } catch (e) {
            toast.show(e.message, 'error')
            error.value = e.message
        } finally {
            loading.value = false
        }
    }

    async function selectManga(manga) {
        const toast = useToastStore()
        selectedManga.value = manga
        selectedMangaSource.value = 'scraper'
        selectedMangaContext.value = null
        loading.value = true
        error.value = ''
        chapters.value = []
        selectedIds.value = []
        try {
            chapters.value = await api.chapters({ ...getPayload(), manga })
            chapters.value = chapters.value.map(chapter => ({
                ...chapter,
                downloaded: !!chapter.downloaded,
                downloaded_count: chapter.downloaded_count || 0,
                downloaded_total: chapter.downloaded_total || 0
            }))
        } catch (e) {
            toast.show(`获取章节失败: ${e.message}`, 'error')
            error.value = e.message
        } finally {
            loading.value = false
        }
    }

    async function selectMangaFromParser(manga) {
        const toast = useToastStore()
        selectedManga.value = manga
        selectedMangaSource.value = 'parser'
        selectedMangaContext.value = { ...parser.context }
        loading.value = true
        error.value = ''
        chapters.value = []
        selectedIds.value = []
        try {
            chapters.value = await api.chapters({ ...getParserPayload(selectedMangaContext.value), manga })
            chapters.value = chapters.value.map(chapter => ({
                ...chapter,
                downloaded: !!chapter.downloaded,
                downloaded_count: chapter.downloaded_count || 0,
                downloaded_total: chapter.downloaded_total || 0
            }))
        } catch (e) {
            toast.show(`获取章节失败: ${e.message}`, 'error')
            error.value = e.message
        } finally {
            loading.value = false
        }
    }

    async function loadCatalog(reset = false) {
        const toast = useToastStore()
        if (catalog.loading) return
        catalog.loading = true
        error.value = ''
        ensureUserAgent()
        checkStateInfo()
        try {
            if (reset) {
                catalog.page = 1
                catalog.items = []
            }
            const orderby = catalog.orderby || null
            const data = await api.catalog({
                ...getPayload(),
                page: catalog.page,
                orderby,
                path: catalog.path || null
            })
            if (reset) {
                catalog.items = mapItemsCoverWithProxy(data.items, proxyImageUrl)
            } else {
                const mappedItems = mapItemsCoverWithProxy(data.items, proxyImageUrl)
                catalog.items = [...catalog.items, ...mappedItems]
            }
            catalog.page = data.page
            catalog.hasMore = data.has_more
        } catch (e) {
            toast.show(`加载目录失败: ${e.message}`, 'error')
            error.value = e.message
        } finally {
            catalog.loading = false
        }
    }

    function loadMoreCatalog() {
        if (catalog.loading || !catalog.hasMore) return
        catalog.page += 1
        loadCatalog(false)
    }

    function formatRemaining(seconds) {
        const total = Math.max(0, Math.floor(seconds || 0))
        const days = Math.floor(total / 86400)
        const hours = Math.floor((total % 86400) / 3600)
        const minutes = Math.floor((total % 3600) / 60)
        if (days > 0) return `${days}天${hours}小时`
        if (hours > 0) return `${hours}小时${minutes}分钟`
        if (minutes > 0) return `${minutes}分钟`
        return '即将过期'
    }

    async function checkStateInfo() {
        const path = (state.storageStatePath || '').trim()
        if (!path) {
            stateInfo.status = 'missing'
            stateInfo.message = '未填写状态文件'
            return
        }
        stateInfo.status = 'checking'
        stateInfo.message = '检测中...'
        try {
            const data = await api.stateInfo({
                base_url: state.baseUrl,
                storage_state_path: path
            })
            stateInfo.status = data.status || 'unknown'
            stateInfo.message = data.message || ''
            stateInfo.cookieName = data.cookie_name || null
            stateInfo.expiresAt = data.expires_at || null
            stateInfo.expiresAtText = data.expires_at_text || ''
            stateInfo.expiresInSec = data.expires_in_sec ?? null
            if (data.expires_in_sec !== null && data.expires_in_sec !== undefined) {
                stateInfo.remainingText = formatRemaining(data.expires_in_sec)
            } else {
                stateInfo.remainingText = ''
            }
        } catch (e) {
            stateInfo.status = 'error'
            stateInfo.message = e.message || '状态检测失败'
        }
    }

    async function checkAccess() {
        accessInfo.status = 'checking'
        accessInfo.message = '检测中...'
        try {
            const data = await api.accessCheck({
                base_url: state.baseUrl,
                storage_state_path: (state.storageStatePath || '').trim() || null,
                path: catalog.path || null
            })
            accessInfo.status = data.status || 'unknown'
            accessInfo.httpStatus = data.http_status || null
            accessInfo.message = data.message || ''
        } catch (e) {
            accessInfo.status = 'error'
            accessInfo.message = e.message || '检测失败'
        }
    }

    async function uploadStateFile(file) {
        if (!file) return
        uploadInfo.status = 'uploading'
        uploadInfo.message = '上传中...'
        try {
            const formData = new FormData()
            formData.append('base_url', state.baseUrl)
            formData.append('file', file)
            const data = await api.uploadState(formData)
            state.storageStatePath = data.path
            uploadInfo.status = 'success'
            uploadInfo.message = '上传成功'
            await checkStateInfo()
        } catch (e) {
            uploadInfo.status = 'error'
            uploadInfo.message = e.message || '上传失败'
        }
    }

    async function parseUrl() {
        const url = normalizeUrlInput(parser.url)
        if (!url) {
            parser.error = '请输入 URL'
            parser.result = null
            resetParserContext()
            return
        }
        parser.loading = true
        parser.error = ''
        parser.result = null
        parser.showAll = false
        try {
            const toast = useToastStore()
            const listResult = await parserApi.list(url, parser.mode)
            const context = deriveParserContext(url, listResult)
            Object.assign(parser.context, context)
            const items = Array.isArray(listResult?.items) ? listResult.items : []
            const mappedListResult = {
                ...listResult,
                items: mapItemsCoverWithProxy(items, proxyParserImageUrl)
            }
            if (items.length > 1) {
                parser.result = mappedListResult
                parser.showAll = true
            } else if (items.length === 1 && items[0]?.url) {
                parser.result = await parserApi.parse(items[0].url, parser.mode)
            } else {
                parser.result = await parserApi.parse(url, parser.mode)
            }
        } catch (e) {
            const toast = useToastStore()
            toast.show(`解析失败: ${e.message}`, 'error')
            parser.error = e.message || '解析失败'
        } finally {
            parser.loading = false
        }
    }

    function defaultAuthUrl() {
        if (typeof window === 'undefined') return '/auth'
        return new URL('/auth', window.location.origin).toString()
    }

    async function resolveAuthUrl() {
        if (authInfo.status === 'loading') return
        authInfo.status = 'loading'
        authInfo.message = ''
        try {
            const data = await api.authUrl()
            authInfo.url = data.url || defaultAuthUrl()
            authInfo.status = 'ready'
        } catch (e) {
            authInfo.url = defaultAuthUrl()
            authInfo.status = 'ready'
            authInfo.message = '使用默认认证地址'
        }
    }

    function accessInfoLabel() {
        if (accessInfo.status === 'checking') return '站点检测中...'
        if (accessInfo.status === 'ok') return '站点可访问'
        if (accessInfo.status === 'forbidden') return '站点拒绝访问（403）'
        if (accessInfo.status === 'error') return accessInfo.message || '站点检测失败'
        return accessInfo.message || '站点状态未知'
    }

    function accessInfoClass() {
        if (accessInfo.status === 'ok') return 'text-green-300'
        if (accessInfo.status === 'forbidden') return 'text-red-300'
        if (accessInfo.status === 'checking') return 'text-slate-300'
        return 'text-slate-400'
    }

    function stateInfoLabel() {
        if (stateInfo.status === 'checking') return '状态检测中...'
        if (stateInfo.status === 'missing') return '未填写状态文件'
        if (stateInfo.status === 'not_found') return '状态文件不存在'
        if (stateInfo.status === 'invalid') return '状态文件无法解析'
        if (stateInfo.status === 'no_cookie') return '状态文件中没有 cookie'
        if (stateInfo.status === 'no_domain') return '没有匹配域名的 cookie'
        if (stateInfo.status === 'session') return 'Cookie 无过期时间（会话）'
        if (stateInfo.status === 'expired') {
            return `Cookie 已过期 (${stateInfo.expiresAtText || '未知时间'})`
        }
        if (stateInfo.status === 'valid') {
            const expiry = stateInfo.expiresAtText ? `，${stateInfo.expiresAtText} 过期` : ''
            const remaining = stateInfo.remainingText ? `，剩余 ${stateInfo.remainingText}` : ''
            return `Cookie 有效${expiry}${remaining}`
        }
        return stateInfo.message || '状态未知'
    }

    function stateInfoClass() {
        if (stateInfo.status === 'valid') return 'text-green-300'
        if (stateInfo.status === 'expired' || stateInfo.status === 'error') return 'text-red-300'
        if (stateInfo.status === 'checking') return 'text-slate-300'
        return 'text-slate-400'
    }

    function isQueued(chapterId, mangaId = activeMangaId()) {
        const key = chapterTaskKey(chapterId, mangaId)
        return queue.value.some(item => item.chapterKey === key)
    }

    function isChapterBusy(chapterId, mangaId = activeMangaId()) {
        const key = chapterTaskKey(chapterId, mangaId)
        const status = tasks[key]?.status
        if (status && ['queued', 'pending', 'running'].includes(status)) return true
        return task.chapterKey === key && ['pending', 'running'].includes(task.status)
    }

    function updateTaskByKey(key, payload) {
        tasks[key] = { ...(tasks[key] || {}), ...payload }
    }

    function updateTask(chapterId, payload, mangaId = activeMangaId()) {
        const key = chapterTaskKey(chapterId, mangaId)
        updateTaskByKey(key, payload)
        return key
    }

    function enqueue(chapter) {
        const mangaSnapshot = selectedManga.value ? { ...selectedManga.value } : null
        const mangaId = mangaSnapshot?.id || null
        const chapterKey = chapterTaskKey(chapter.id, mangaId)
        if (isQueued(chapter.id, mangaId) || isChapterBusy(chapter.id, mangaId)) return
        queue.value.push({
            chapter: { ...chapter },
            manga: mangaSnapshot,
            payload: { ...getActivePayload() },
            chapterKey,
            mangaId
        })
        updateTaskByKey(chapterKey, { status: 'queued', message: '排队中', report: null })
        processQueue()
    }

    function enqueueMany(items) {
        items.forEach(item => enqueue(item))
    }

    async function startDownload(item) {
        const chapter = item?.chapter ? item.chapter : item
        const manga = item?.manga || selectedManga.value
        const mangaId = item?.mangaId || manga?.id || null
        const chapterKey = item?.chapterKey || chapterTaskKey(chapter.id, mangaId)
        const payload = item?.payload || getActivePayload()

        if (!manga) { error.value = '请先选择漫画'; return }
        stopPolling()
        task.status = 'pending'
        task.message = '提交下载任务中...'
        task.report = null
        task.chapterId = chapter.id
        task.mangaId = mangaId
        task.chapterKey = chapterKey
        error.value = ''
        updateTaskByKey(chapterKey, { status: 'pending', message: '提交下载任务中...', report: null })
        try {
            const data = await api.download({ ...payload, manga, chapter })
            task.id = data.task_id
            task.status = data.status
            task.message = data.message || '已提交下载任务'
            updateTaskByKey(chapterKey, { status: data.status, message: task.message, report: data.report || null })
            schedulePoll()
        } catch (e) {
            error.value = e.message
            task.message = '下载任务提交失败'
            task.status = 'error'
            task.id = null
            updateTaskByKey(chapterKey, { status: 'error', message: task.message })
            processQueue()
        }
    }

    function processQueue() {
        if (task.status === 'running' || task.status === 'pending') return
        if (queue.value.length === 0) return
        const next = queue.value.shift()
        if (!next) return
        startDownload(next)
    }

    function download(chapter) {
        enqueueMany([chapter])
    }

    function downloadSelected() {
        const targets = chapters.value.filter(chapter => selectedIds.value.includes(chapter.id))
        enqueueMany(targets)
    }

    function schedulePoll(delay = 2000) {
        stopPolling()
        pollTimer = setTimeout(poll, delay)
    }

    function stopPolling() {
        if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
    }

    async function poll() {
        if (!task.id) return
        try {
            const data = await api.taskStatus(task.id)
            task.status = data.status
            task.message = data.message || ''
            task.report = data.report || null
            if (task.chapterKey) {
                updateTaskByKey(task.chapterKey, {
                    status: data.status,
                    message: task.message,
                    report: data.report || null
                })
                if (data.report) {
                    const target = chapters.value.find(ch => ch.id === task.chapterId)
                    if (target) {
                        const success = data.report.success_count || 0
                        const failed = data.report.failed_count || 0
                        target.downloaded_count = success
                        target.downloaded_total = success + failed
                        target.downloaded = success > 0
                    }
                }
            }
            if (data.status === 'running' || data.status === 'pending') {
                schedulePoll()
            } else {
                stopPolling()
                processQueue()
            }
        } catch (e) {
            task.message = '任务状态获取失败'
            task.status = 'error'
            task.id = null
            if (task.chapterKey) {
                updateTaskByKey(task.chapterKey, { status: 'error', message: task.message })
            }
            stopPolling()
            processQueue()
        }
    }

    function statusLabel(s) {
        const map = { queued: '排队中', pending: '排队中', running: '下载中', success: '已完成', partial: '部分成功', error: '失败' }
        return map[s] || s || '暂无任务'
    }

    function statusClass(s) {
        const map = {
            success: 'bg-green-500/20 text-green-300 border border-green-500/30',
            partial: 'bg-amber-500/20 text-amber-300 border border-amber-500/30',
            error: 'bg-red-500/20 text-red-300 border border-red-500/30',
            running: 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
        }
        return map[s] || 'bg-slate-700/40 text-slate-300 border border-slate-500/30'
    }

    function toggleSelection(chapterId) {
        if (selectedIds.value.includes(chapterId)) {
            selectedIds.value = selectedIds.value.filter(id => id !== chapterId)
        } else {
            selectedIds.value = [...selectedIds.value, chapterId]
        }
    }

    function selectAll() {
        selectedIds.value = chapters.value.map(chapter => chapter.id)
    }

    function clearSelection() {
        selectedIds.value = []
    }

    function chapterStatus(chapterId) {
        const key = chapterTaskKey(chapterId, activeMangaId())
        return tasks[key]?.status || null
    }

    function downloadedLabel(chapter) {
        if (!chapter.downloaded_count) return ''
        if (chapter.downloaded_total > 0 && chapter.downloaded_count < chapter.downloaded_total) {
            return `已下载 ${chapter.downloaded_count}/${chapter.downloaded_total}`
        }
        return '已下载'
    }

    function downloadedClass(chapter) {
        if (!chapter.downloaded_count) return ''
        if (chapter.downloaded_total > 0 && chapter.downloaded_count < chapter.downloaded_total) {
            return 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
        }
        return 'bg-green-500/20 text-green-300 border border-green-500/30'
    }

    return {
        state,
        loading,
        error,
        results,
        selectedManga,
        selectedMangaSource,
        selectedMangaContext,
        chapters,
        selectedIds,
        queue,
        tasks,
        catalog,
        stateInfo,
        accessInfo,
        uploadInfo,
        authInfo,
        parser,
        downloadSummary,
        task,
        setSite,
        setMode,
        setView,
        setCatalogMode,
        syncUserAgent,
        ensureUserAgent,
        proxyImageUrl,
        proxyParserImageUrl,
        search,
        selectManga,
        selectMangaFromParser,
        loadCatalog,
        loadMoreCatalog,
        checkStateInfo,
        checkAccess,
        uploadStateFile,
        parseUrl,
        resolveAuthUrl,
        stateInfoLabel,
        stateInfoClass,
        accessInfoLabel,
        accessInfoClass,
        getActivePayload,
        download,
        downloadSelected,
        toggleSelection,
        selectAll,
        clearSelection,
        chapterStatus,
        isChapterBusy,
        downloadedLabel,
        downloadedClass,
        statusLabel,
        statusClass,
        stopPolling
    }
})
