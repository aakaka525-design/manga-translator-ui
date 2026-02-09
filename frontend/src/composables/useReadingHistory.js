import { ref, onMounted } from 'vue'

const STORAGE_KEY = 'manhua_reading_history'
const MAX_HISTORY = 10

/**
 * Reading history composable
 * Tracks last read manga/chapter for quick resume
 */
export function useReadingHistory() {
    const history = ref([])
    // { mangaId, mangaName, chapterId, chapterName, timestamp, scrollPosition }

    function load() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY)
            if (saved) {
                history.value = JSON.parse(saved)
            }
        } catch (e) {
            console.error('Failed to load reading history:', e)
        }
    }

    function save() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value))
        } catch (e) {
            console.error('Failed to save reading history:', e)
        }
    }

    function addEntry(entry) {
        // Remove existing entry for same manga/chapter
        history.value = history.value.filter(
            h => !(h.mangaId === entry.mangaId && h.chapterId === entry.chapterId)
        )
        // Add new entry at front
        history.value.unshift({
            ...entry,
            timestamp: Date.now()
        })
        // Limit history size
        if (history.value.length > MAX_HISTORY) {
            history.value = history.value.slice(0, MAX_HISTORY)
        }
        save()
    }

    function updateScrollPosition(mangaId, chapterId, scrollPosition) {
        const entry = history.value.find(
            h => h.mangaId === mangaId && h.chapterId === chapterId
        )
        if (entry) {
            entry.scrollPosition = scrollPosition
            entry.timestamp = Date.now()
            save()
        }
    }

    function getLastRead() {
        return history.value[0] || null
    }

    function getHistoryForManga(mangaId) {
        return history.value.filter(h => h.mangaId === mangaId)
    }

    // Auto-load on init
    load()

    return {
        history,
        addEntry,
        updateScrollPosition,
        getLastRead,
        getHistoryForManga
    }
}
