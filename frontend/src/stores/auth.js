import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
    authApi,
    clearSessionToken,
    getSessionToken,
    setSessionToken,
    SESSION_USER_KEY,
} from '@/api'

export const useAuthStore = defineStore('auth', () => {
    const token = ref(getSessionToken())
    const user = ref(null)
    const validating = ref(false)

    if (typeof window !== 'undefined') {
        const raw = window.localStorage.getItem(SESSION_USER_KEY)
        if (raw) {
            try {
                user.value = JSON.parse(raw)
            } catch (_e) {
                user.value = null
            }
        }
    }

    const isAuthenticated = computed(() => !!token.value)
    const isAdmin = computed(() => user.value?.role === 'admin')

    function setUser(nextUser) {
        user.value = nextUser || null
        if (typeof window === 'undefined') return
        if (!nextUser) {
            window.localStorage.removeItem(SESSION_USER_KEY)
            return
        }
        window.localStorage.setItem(SESSION_USER_KEY, JSON.stringify(nextUser))
    }

    async function bootstrap() {
        if (!token.value) return
        validating.value = true
        try {
            const data = await authApi.check()
            if (!data?.valid) {
                clearSession()
                return
            }
            setUser(data.user || null)
        } catch (_err) {
            clearSession()
        } finally {
            validating.value = false
        }
    }

    async function login(username, password) {
        const data = await authApi.login(username, password)
        if (!data?.success || !data?.token) {
            throw new Error(data?.message || '登录失败')
        }
        token.value = data.token
        setSessionToken(data.token)
        setUser(data.user || null)
        return data
    }

    async function logout() {
        try {
            await authApi.logout()
        } catch (_err) {
            // best-effort logout
        }
        clearSession()
    }

    function clearSession() {
        token.value = ''
        setUser(null)
        clearSessionToken()
    }

    return {
        token,
        user,
        validating,
        isAuthenticated,
        isAdmin,
        bootstrap,
        login,
        logout,
        clearSession,
    }
})
