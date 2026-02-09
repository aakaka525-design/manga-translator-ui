import { createRouter, createWebHistory } from 'vue-router'
import { getSessionToken } from '@/api'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/signin',
            name: 'signin',
            component: () => import('../views/SignInView.vue'),
            meta: { public: true },
        },
        {
            path: '/',
            name: 'home',
            component: () => import('../views/HomeView.vue'),
        },
        {
            path: '/manga/:id',
            name: 'manga',
            component: () => import('../views/MangaView.vue'),
        },
        {
            path: '/read/:mangaId/:chapterId',
            name: 'reader',
            component: () => import('../views/ReaderView.vue'),
        },
        {
            path: '/scraper',
            name: 'scraper',
            component: () => import('../views/ScraperView.vue'),
        },
        {
            path: '/admin',
            name: 'admin',
            component: () => import('../views/AdminView.vue'),
        },
        {
            path: '/:pathMatch(.*)*',
            redirect: '/',
        }
    ]
})

router.beforeEach((to, _from, next) => {
    const token = getSessionToken()
    if (to.meta.public) {
        if (to.name === 'signin' && token) {
            next({ name: 'home' })
            return
        }
        next()
        return
    }

    if (!token) {
        next({ name: 'signin' })
        return
    }
    next()
})

export default router
