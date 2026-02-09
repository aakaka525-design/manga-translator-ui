import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { mangaApi } from '@/api'

export const useMangaStore = defineStore('manga', () => {
    const mangas = ref([])
    const currentManga = ref(null)
    const chapters = ref([])
    const loading = ref(false)
    const error = ref(null)

    // Getters
    const hasMangas = computed(() => mangas.value.length > 0)

    // Actions
    async function fetchMangas() {
        loading.value = true
        error.value = null
        try {
            mangas.value = await mangaApi.list()
        } catch (err) {
            error.value = err.message
            console.error('Failed to fetch mangas:', err)
        } finally {
            loading.value = false
        }
    }

    async function openManga(mangaId) {
        loading.value = true
        error.value = null
        try {
            // Find manga info from local list if available, or just use ID
            const manga = mangas.value.find(m => m.id === mangaId)
            if (manga) {
                currentManga.value = manga
            }

            const chapData = await mangaApi.getChapters(mangaId)

            // Process chapters logic (e.g. status text)
            chapters.value = chapData.map(c => {
                c.translated_count = c.translated_count || 0;
                c.isComplete = c.page_count > 0 && c.translated_count === c.page_count;
                c.isTranslating = false; // Initial state
                if (c.isComplete) {
                    c.statusText = '已完成';
                } else if (c.has_translated) {
                    c.statusText = `已完成 (${c.translated_count}/${c.page_count})`;
                }
                return c;
            })
        } catch (err) {
            error.value = err.message
            console.error('Failed to fetch chapters:', err)
        } finally {
            loading.value = false
        }
    }

    return {
        mangas,
        currentManga,
        chapters,
        loading,
        error,
        hasMangas,
        fetchMangas,
        openManga
    }
})
