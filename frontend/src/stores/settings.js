import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { getSessionToken } from '@/api'

const STORAGE_KEY = 'manhua_settings'

const availableModels = [
    // Gemini 3.x 系列 (最新)
    { id: 'gemini-3-pro-preview', name: 'Gemini 3 Pro', desc: '最新旗舰，高质量翻译' },
    { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash', desc: '最新快速模型' },
    // Gemini 2.5 系列
    { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', desc: '平衡速度与质量' },
    { id: 'gemini-2.5-flash-lite', name: 'Gemini 2.5 Flash-Lite', desc: '轻量级快速' },
    { id: 'gemini-2.5-pro-exp', name: 'Gemini 2.5 Pro Exp', desc: '实验版高质量' },
    // PPIO 模型
    { id: 'zai-org/glm-4.7-flash', name: 'GLM-4.7 Flash', desc: 'PPIO 快速翻译' },
    { id: 'deepseek/deepseek-r1-distill-llama-70b', name: 'DeepSeek R1 70B', desc: 'PPIO 高质量' },
    { id: 'deepseek/deepseek-v3', name: 'DeepSeek V3', desc: 'PPIO 通用模型' },
    // 其他
    { id: 'gpt-4o', name: 'GPT-4o', desc: 'OpenAI 模型' }
]

const availableUpscaleModels = [
    { id: 'realesrgan-x4plus-anime', name: 'RealESRGAN Anime x4', desc: '动漫风格优化 (x4)' },
    { id: 'realesrgan-x4plus', name: 'RealESRGAN x4plus', desc: '通用高清放大 (x4)' },
    { id: 'realesr-animevideov3-x2', name: 'AnimeVideo v3 x2', desc: '视频动漫优化 (x2)' },
    { id: 'realesr-animevideov3-x3', name: 'AnimeVideo v3 x3', desc: '视频动漫优化 (x3)' },
    { id: 'realesr-animevideov3-x4', name: 'AnimeVideo v3 x4', desc: '视频动漫优化 (x4)' }
]

const availableUpscaleModelScales = {
    'realesrgan-x4plus-anime': [4],
    'realesrgan-x4plus': [4],
    'realesr-animevideov3-x2': [2],
    'realesr-animevideov3-x3': [3],
    'realesr-animevideov3-x4': [4]
}
const availableUpscaleModelIds = new Set(availableUpscaleModels.map((model) => model.id))
const defaultUpscaleModel = availableUpscaleModels[0]?.id ?? 'realesrgan-x4plus-anime'
const defaultUpscaleScale = availableUpscaleModelScales[defaultUpscaleModel]?.[0] ?? 4

function isSettingsFallbackStatus(status) {
    return status === 401 || status === 403 || status === 404
}

export const useSettingsStore = defineStore('settings', () => {
    const showModal = ref(false)
    const showLogsModal = ref(false)
    const logsContent = ref('')
    const loading = ref(false)

    const settings = reactive({
        aiModel: 'zai-org/glm-4.7-flash',
        aiModelName: 'GLM-4.7 Flash',
        sourceLang: 'en',
        targetLang: 'zh',
        theme: 'default', // default (dark) or pop (light)
        upscaleModel: 'realesrgan-x4plus-anime',
        upscaleScale: 2,
        upscaleEnabled: true
    })

    function applyTheme() {
        if (settings.theme === 'pop') {
            document.documentElement.setAttribute('data-theme', 'pop')
        } else {
            document.documentElement.removeAttribute('data-theme')
        }
    }

    function toggleTheme() {
        settings.theme = settings.theme === 'default' ? 'pop' : 'default'
        applyTheme()
        saveSettings()
    }

    function loadSettings() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY)
            if (saved) {
                const parsed = JSON.parse(saved)
                Object.assign(settings, parsed)
            }
            const normalized = normalizeUpscaleSettings()
            if (normalized) {
                saveSettings()
            }
            applyTheme()
        } catch (e) {
            console.error('Failed to load settings:', e)
        }
    }

    function normalizeUpscaleSettings() {
        let changed = false

        if (!availableUpscaleModelIds.has(settings.upscaleModel)) {
            settings.upscaleModel = defaultUpscaleModel
            changed = true
        }

        const allowedScales = getUpscaleScalesForModel(settings.upscaleModel)
        const numericScale = Number(settings.upscaleScale)
        if (!allowedScales.includes(numericScale)) {
            settings.upscaleScale = allowedScales[0] ?? defaultUpscaleScale
            changed = true
        } else if (settings.upscaleScale !== numericScale) {
            settings.upscaleScale = numericScale
            changed = true
        }

        if (typeof settings.upscaleEnabled !== 'boolean') {
            settings.upscaleEnabled = true
            changed = true
        }

        return changed
    }

    function getUpscaleScalesForModel(modelId) {
        return availableUpscaleModelScales[modelId] ?? [defaultUpscaleScale]
    }

    function saveSettings() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
        } catch (e) {
            console.error('Failed to save settings:', e)
        }
    }

    function sessionHeaders(extraHeaders = {}) {
        const headers = { ...extraHeaders }
        const token = getSessionToken()
        if (token) {
            headers['X-Session-Token'] = token
        }
        return headers
    }

    async function selectModel(model) {
        settings.aiModel = model.id
        settings.aiModelName = model.name
        saveSettings()
        try {
            const response = await fetch('/api/v1/settings/model', {
                method: 'POST',
                headers: sessionHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ model: model.id })
            })
            if (!response.ok && !isSettingsFallbackStatus(response.status)) {
                throw new Error(`Model update failed: ${response.status}`)
            }
        } catch (e) {
            console.error('Failed to update model:', e)
        }
    }

    async function selectUpscaleModel(model) {
        const previousModel = settings.upscaleModel
        const previousScale = settings.upscaleScale
        settings.upscaleModel = model.id
        const allowedScales = getUpscaleScalesForModel(settings.upscaleModel)
        if (!allowedScales.includes(settings.upscaleScale)) {
            settings.upscaleScale = allowedScales[0]
        }
        saveSettings()
        try {
            await postUpscaleSettings()
        } catch (e) {
            settings.upscaleModel = previousModel
            settings.upscaleScale = previousScale
            saveSettings()
            console.error('Failed to update upscale model:', e)
        }
    }

    async function selectUpscaleScale(scale) {
        const previousScale = settings.upscaleScale
        const allowedScales = getUpscaleScalesForModel(settings.upscaleModel)
        settings.upscaleScale = allowedScales.includes(scale) ? scale : (allowedScales[0] ?? previousScale)
        saveSettings()
        try {
            await postUpscaleSettings()
        } catch (e) {
            settings.upscaleScale = previousScale
            saveSettings()
            console.error('Failed to update upscale scale:', e)
        }
    }

    async function setUpscaleEnabled(enabled) {
        const previousEnabled = settings.upscaleEnabled
        settings.upscaleEnabled = enabled
        saveSettings()
        try {
            await postUpscaleSettings()
        } catch (e) {
            settings.upscaleEnabled = previousEnabled
            saveSettings()
            console.error('Failed to update upscale enabled:', e)
        }
    }

    async function postUpscaleSettings() {
        const response = await fetch('/api/v1/settings/upscale', {
            method: 'POST',
            headers: sessionHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                model: settings.upscaleModel,
                scale: settings.upscaleScale,
                enabled: settings.upscaleEnabled
            })
        })
        if (isSettingsFallbackStatus(response.status)) {
            return
        }
        if (!response.ok) {
            let detail = ''
            try {
                const payload = await response.json()
                if (payload?.detail) detail = ` (${JSON.stringify(payload.detail)})`
            } catch (_) {}
            throw new Error(`Upscale settings update failed: ${response.status}${detail}`)
        }
    }

    async function syncSettingsFromServer() {
        try {
            const response = await fetch('/api/v1/settings', {
                headers: sessionHeaders()
            })
            if (!response.ok) {
                if (isSettingsFallbackStatus(response.status)) {
                    return
                }
                throw new Error(`Settings sync failed: ${response.status}`)
            }

            const remote = await response.json()
            let changed = false
            if (typeof remote.ai_model === 'string' && remote.ai_model) {
                if (settings.aiModel !== remote.ai_model) changed = true
                settings.aiModel = remote.ai_model
                const model = availableModels.find((item) => item.id === remote.ai_model)
                if (model && settings.aiModelName !== model.name) {
                    settings.aiModelName = model.name
                    changed = true
                }
            }

            if (typeof remote.source_language === 'string' && remote.source_language) {
                if (settings.sourceLang !== remote.source_language) changed = true
                settings.sourceLang = remote.source_language
            }
            if (typeof remote.target_language === 'string' && remote.target_language) {
                if (settings.targetLang !== remote.target_language) changed = true
                settings.targetLang = remote.target_language
            }
            if (typeof remote.upscale_model === 'string' && remote.upscale_model) {
                if (settings.upscaleModel !== remote.upscale_model) changed = true
                settings.upscaleModel = remote.upscale_model
            }
            if (Number.isFinite(Number(remote.upscale_scale))) {
                const nextScale = Number(remote.upscale_scale)
                if (settings.upscaleScale !== nextScale) changed = true
                settings.upscaleScale = nextScale
            }
            if (typeof remote.upscale_enable === 'boolean') {
                if (settings.upscaleEnabled !== remote.upscale_enable) changed = true
                settings.upscaleEnabled = remote.upscale_enable
            }

            const normalized = normalizeUpscaleSettings()
            if (normalized || changed) {
                saveSettings()
            }
        } catch (e) {
            console.error('Failed to sync settings from server:', e)
        }
    }

    async function fetchLogs() {
        loading.value = true
        try {
            const res = await fetch('/api/v1/system/logs?lines=200', {
                headers: sessionHeaders()
            })
            if (res.ok) {
                const lines = await res.json()
                logsContent.value = lines.join('\n')
            } else if (res.status === 401 || res.status === 403) {
                logsContent.value = '当前账号没有查看日志权限'
            } else if (res.status === 404) {
                logsContent.value = '日志接口暂不可用'
            } else {
                logsContent.value = '获取日志失败'
            }
        } catch (e) {
            logsContent.value = '网络错误: ' + e.message
        } finally {
            loading.value = false
        }
    }

    function openLogs() {
        showModal.value = false
        showLogsModal.value = true
        fetchLogs()
    }

    // Load on init
    loadSettings()
    // Always align local UI state with backend runtime settings.
    syncSettingsFromServer()

    return {
        showModal,
        showLogsModal,
        logsContent,
        loading,
        settings,
        availableModels,
        availableUpscaleModels,
        getUpscaleScalesForModel,
        saveSettings,
        selectModel,
        selectUpscaleModel,
        selectUpscaleScale,
        setUpscaleEnabled,
        syncSettingsFromServer,
        openLogs,
        fetchLogs,
        toggleTheme
    }
})
