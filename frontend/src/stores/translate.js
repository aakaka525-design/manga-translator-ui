import { defineStore } from 'pinia'
import { ref } from 'vue'
import { translateApi } from '@/api'
import { useMangaStore } from './manga'
import { useToastStore } from './toast'

export const useTranslateStore = defineStore('translate', () => {
    const isConnected = ref(false)
    const eventSource = ref(null)
    const retryCount = ref(0)

    const mangaStore = useMangaStore()
    const toastStore = useToastStore()
    const chapterTrackers = new Map()

    const stageLabels = {
        init: '准备中',
        ocr: '文本识别',
        translator: '文本翻译',
        inpainter: '背景修复',
        renderer: '文字渲染',
        upscaler: '超分处理',
        complete: '完成',
        failed: '失败',
    }

    function stageLabel(stage) {
        return stageLabels[stage] || '处理中'
    }

    function chapterKey(mangaId, chapterId) {
        return `${mangaId}::${chapterId}`
    }

    function resetChapterTracker(mangaId, chapterId) {
        const key = chapterKey(mangaId, chapterId)
        chapterTrackers.set(key, { finalTaskIds: new Set() })
        return chapterTrackers.get(key)
    }

    function getChapterTracker(mangaId, chapterId) {
        const key = chapterKey(mangaId, chapterId)
        if (!chapterTrackers.has(key)) {
            chapterTrackers.set(key, { finalTaskIds: new Set() })
        }
        return chapterTrackers.get(key)
    }

    function clearChapterTracker(mangaId, chapterId) {
        chapterTrackers.delete(chapterKey(mangaId, chapterId))
    }

    function chapterTotal(chapter) {
        const total = Number(chapter.totalPages)
        if (total > 0) return total
        return Number(chapter.page_count) || 0
    }

    function initSSE() {
        if (eventSource.value) return

        const url = translateApi.getEventsUrl()
        eventSource.value = new EventSource(url)

        eventSource.value.onopen = () => {
            console.log('SSE Connected')
            isConnected.value = true
            retryCount.value = 0
        }

        eventSource.value.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                handleEvent(data)
            } catch (e) {
                console.error('SSE Parse Error:', e)
            }
        }

        eventSource.value.onerror = (err) => {
            console.error('SSE Error:', err)
            closeSSE()
            // Simple retry logic
            if (retryCount.value < 5) {
                retryCount.value++
                setTimeout(initSSE, 1000 * retryCount.value)
            }
        }
    }

    function closeSSE() {
        if (eventSource.value) {
            eventSource.value.close()
            eventSource.value = null
            isConnected.value = false
        }
    }

    function markChapterStart(data) {
        const chapter = findChapter(data.manga_id, data.chapter_id)
        if (!chapter) return

        chapter.isTranslating = true
        chapter.progress = 0
        chapter.totalPages = Number(data.total_pages) || Number(chapter.page_count) || 0
        chapter.completedPages = 0
        chapter.failedPages = 0
        chapter.currentStage = 'init'
        chapter.statusText = `进行中 · ${stageLabel('init')}`
        resetChapterTracker(data.manga_id, data.chapter_id)
    }

    function markChapterProgress(data) {
        if (!data.manga_id || !data.chapter_id) return
        const chapter = findChapter(data.manga_id, data.chapter_id)
        if (!chapter) return

        chapter.isTranslating = true
        chapter.currentStage = data.stage || chapter.currentStage || 'init'
        if (!chapter.totalPages) {
            chapter.totalPages = Number(chapter.page_count) || 0
        }

        const tracker = getChapterTracker(data.manga_id, data.chapter_id)
        const taskId = data.task_id ? String(data.task_id) : ''
        const isFinalStage = chapter.currentStage === 'complete' || chapter.currentStage === 'failed'
        const isFinalStatus = data.status === 'completed' || data.status === 'failed'
        const isFinal = isFinalStage || isFinalStatus

        if (isFinal && taskId && !tracker.finalTaskIds.has(taskId)) {
            tracker.finalTaskIds.add(taskId)
            chapter.completedPages = Number(chapter.completedPages || 0) + 1
            if (data.status === 'failed' || chapter.currentStage === 'failed') {
                chapter.failedPages = Number(chapter.failedPages || 0) + 1
            }
        }

        const total = chapterTotal(chapter)
        const completed = Number(chapter.completedPages || 0)
        const failed = Number(chapter.failedPages || 0)

        if (total > 0 && completed >= total) {
            const successCount = Math.max(completed - failed, 0)
            markChapterComplete(
                {
                    manga_id: data.manga_id,
                    chapter_id: data.chapter_id,
                    success_count: successCount,
                    failed_count: failed,
                    total_count: total,
                    status: successCount <= 0 ? 'error' : (failed > 0 ? 'partial' : 'success')
                },
                { silent: true }
            )
            return
        }

        if (total > 0) {
            chapter.progress = Math.min(99, Math.round((completed / total) * 100))
            if (isFinal) {
                const failedSuffix = failed > 0 ? ` · 失败 ${failed}` : ''
                chapter.statusText = `进行中 (${completed}/${total}${failedSuffix})`
            } else {
                chapter.statusText = `进行中 · ${stageLabel(chapter.currentStage)}`
            }
        } else {
            chapter.statusText = `进行中 · ${stageLabel(chapter.currentStage)}`
        }
    }

    function markChapterComplete(data, options = {}) {
        const silent = options.silent === true
        const chapter = findChapter(data.manga_id, data.chapter_id)
        if (!chapter) return
        if (!chapter.isTranslating && Number(chapter.progress || 0) >= 100) return

        const successCount = data.success_count !== undefined ? data.success_count : 0
        const totalCount = data.total_count !== undefined ? data.total_count : chapter.page_count
        const failedCount = data.failed_count !== undefined
            ? data.failed_count
            : Math.max(totalCount - successCount, 0)
        const finalStatus = data.status || (successCount <= 0 ? 'error' : (failedCount > 0 ? 'partial' : 'success'))

        chapter.isTranslating = false
        chapter.has_translated = successCount > 0
        chapter.isComplete = successCount > 0 && successCount === totalCount
        chapter.translated_count = successCount
        chapter.totalPages = totalCount
        chapter.completedPages = successCount + failedCount
        chapter.failedPages = failedCount
        chapter.currentStage = finalStatus === 'error' ? 'failed' : 'complete'

        if (finalStatus === 'error') {
            chapter.statusText = data.error_message ? `失败: ${data.error_message}` : '失败'
            if (!silent) {
                const detail = data.error_message ? ` (${data.error_message})` : ''
                toastStore.show(`章节失败: ${chapter.name}${detail}`, 'error')
            }
        } else if (failedCount > 0) {
            chapter.statusText = `部分完成 (${successCount}/${totalCount})`
            if (!silent) {
                const detail = data.error_message ? `，原因：${data.error_message}` : ''
                toastStore.show(`章节部分完成: ${chapter.name} (${successCount}/${totalCount})${detail}`, 'warning')
            }
        } else {
            chapter.statusText = '已完成'
            if (!silent) {
                toastStore.show(`章节完成: ${chapter.name}`, 'success')
            }
        }
        chapter.progress = 100
        clearChapterTracker(data.manga_id, data.chapter_id)
    }

    function handleEvent(data) {
        if (data.type === 'chapter_start') {
            markChapterStart(data)
        } else if (data.type === 'progress') {
            markChapterProgress(data)
        } else if (data.type === 'chapter_complete') {
            markChapterComplete(data)
        } else if (data.type === 'page_complete') {
            const chapter = findChapter(data.manga_id, data.chapter_id)
            if (chapter) {
                // Update page logic would go here if we had page store accessible
                console.log('Page translated:', data.image_name)
            }
        }
    }

    function findChapter(mangaId, chapterId) {
        // Only update if we are looking at the relevant manga
        if (mangaStore.currentManga && mangaStore.currentManga.id === mangaId) {
            return mangaStore.chapters.find(c => c.id === chapterId)
        }
        return null
    }

    return {
        isConnected,
        stageLabel,
        initSSE,
        closeSSE
    }
})
