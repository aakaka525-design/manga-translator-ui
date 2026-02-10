<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMangaStore } from '@/stores/manga'
import { useSettingsStore } from '@/stores/settings'
import { useToastStore } from '@/stores/toast'
import { mangaApi, translateApi } from '@/api'
import { useKeyboard } from '@/composables/useKeyboard'
import { useReadingHistory } from '@/composables/useReadingHistory'
import CompareSlider from '@/components/ui/CompareSlider.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import ContextMenu from '@/components/ui/ContextMenu.vue'
import ComicLoading from '@/components/ui/ComicLoading.vue'

const route = useRoute()
const router = useRouter()
const mangaStore = useMangaStore()
const settingsStore = useSettingsStore()
const toast = useToastStore()
const { addEntry } = useReadingHistory()

const pages = ref([])
const loading = ref(true)
const compareMode = ref(false)
const contextMenuRef = ref(null)

const mangaId = computed(() => String(route.params.mangaId || ''))
const chapterId = computed(() => String(route.params.chapterId || ''))

// Chapter navigation
const currentChapterIndex = computed(() => {
  return mangaStore.chapters.findIndex(c => c.id === chapterId.value)
})

const prevChapter = computed(() => {
  const idx = currentChapterIndex.value
  return idx > 0 ? mangaStore.chapters[idx - 1] : null
})

const nextChapter = computed(() => {
  const idx = currentChapterIndex.value
  return idx >= 0 && idx < mangaStore.chapters.length - 1 
    ? mangaStore.chapters[idx + 1] 
    : null
})

function goToChapter(chapter) {
  if (!chapter) return
  router.push({ 
    name: 'reader', 
    params: { mangaId: mangaId.value, chapterId: chapter.id }
  })
}

// Keyboard navigation with chapter support
useKeyboard({
  onEscape: () => router.go(-1),
  onSpace: () => window.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' }),
  onPrev: () => { if (prevChapter.value) goToChapter(prevChapter.value) },
  onNext: () => { if (nextChapter.value) goToChapter(nextChapter.value) }
})

let loadSeq = 0

async function loadChapter() {
  const mid = mangaId.value
  const cid = chapterId.value
  if (!mid || !cid) return

  const seq = ++loadSeq
  loading.value = true
  pages.value = []

  try {
    // Ensure we have the current manga + chapters in store for prev/next navigation.
    if (!mangaStore.currentManga || mangaStore.currentManga.id !== mid) {
      await mangaStore.fetchMangas()
      await mangaStore.openManga(mid)
    }

    const data = await mangaApi.getChapter(mid, cid)
    if (seq !== loadSeq) return
    pages.value = data.pages

    // Record reading history
    const currentChapter = mangaStore.chapters.find(c => c.id === cid)
    addEntry({
      mangaId: mid,
      mangaName: mangaStore.currentManga?.name || mid,
      chapterId: cid,
      chapterName: currentChapter?.name || cid
    })

    // Switching chapters keeps the component mounted; reset scroll for better UX.
    window.scrollTo({ top: 0, behavior: 'auto' })
  } catch (e) {
    console.error(e)
    toast.show('加载失败', 'error')
  } finally {
    if (seq === loadSeq) {
      loading.value = false
    }
  }
}

watch([mangaId, chapterId], () => {
  loadChapter()
}, { immediate: true })

function toggleCompare() {
  compareMode.value = !compareMode.value
}

function showPageMenu(event, page) {
  contextMenuRef.value?.show(event, page)
}

async function handleRetranslate(page) {
  const pageName = page?.name || page
  toast.show('正在重新翻译...', 'info')
  try {
    await translateApi.retranslatePage({
      manga_id: mangaId.value,
      chapter_id: chapterId.value,
      image_name: pageName,
      source_language: settingsStore.settings.sourceLang,
      target_language: settingsStore.settings.targetLang,
    })
    await loadChapter()
    toast.show('翻译请求已提交', 'success')
  } catch (e) {
    console.error(e)
    const message = e?.message ? `翻译失败: ${e.message}` : '翻译失败'
    toast.show(message, 'error')
  }
}

const contextMenuItems = [
  { label: '重新翻译', icon: 'fa-sync-alt', action: handleRetranslate },
  { label: '复制图片链接', icon: 'fa-link', action: (page) => {
    navigator.clipboard?.writeText(window.location.origin + (page.translated_url || page.original_url))
    toast.show('链接已复制', 'success')
  }}
]
</script>

<template>
  <div class="min-h-screen bg-bg-primary pb-28 text-text-main sm:pb-0">
    <!-- Toolbar -->
    <div class="fixed top-0 left-0 right-0 p-4 bg-gradient-to-b from-bg-primary/90 to-transparent z-50 flex justify-between items-start pointer-events-none">
      <button @click="router.go(-1)" class="pointer-events-auto w-10 h-10 rounded-full bg-surface/50 backdrop-blur flex items-center justify-center text-text-main hover:bg-surface border border-transparent hover:border-border-subtle transition">
        <i class="fas fa-arrow-left"></i>
      </button>
      
      <button @click="toggleCompare" 
        class="pointer-events-auto hidden rounded-full border border-transparent px-4 py-2 text-sm font-bold backdrop-blur transition sm:inline-flex"
        :class="compareMode ? 'bg-accent-2/80 text-white' : 'bg-surface/50 text-text-main border-border-subtle'">
        <i class="fas fa-columns mr-2"></i> 对比模式
      </button>
    </div>

    <!-- Reader Content -->
    <div class="max-w-4xl mx-auto min-h-screen pb-24 sm:pb-0">
      <div v-if="loading" class="flex items-center justify-center h-screen">
        <ComicLoading label="章节加载中..." compact />
      </div>
      
      <div v-else class="flex flex-col pt-14 sm:pt-16">
        <div v-for="page in pages" :key="page.name" class="relative group"
          @contextmenu="showPageMenu($event, page)">
          <CompareSlider 
            :original="page.original_url" 
            :translated="page.translated_url || page.original_url" 
            :active="compareMode"
          />

          <StatusBadge
            class="absolute top-2 right-2 z-20 sm:right-12"
            :status="page.status"
            :reason="page.status_reason"
            :warning-counts="page.warning_counts"
          />
          
          <!-- Quick Action Button -->
          <button 
            class="absolute top-2 right-2 hidden h-8 w-8 items-center justify-center rounded-full bg-black/50 text-white opacity-0 transition hover:bg-accent-1 group-hover:opacity-100 sm:flex"
            title="重新翻译"
            @click="handleRetranslate(page)">
            <i class="fas fa-sync-alt text-xs"></i>
          </button>
        </div>
      </div>
      
      <!-- Navigation Footer -->
      <div v-if="!loading" class="space-y-4 p-8 pb-24 text-center sm:pb-20">
        <h3 class="text-text-secondary">章节结束</h3>
        
        <!-- Chapter Navigation -->
        <div class="flex justify-center gap-4 flex-wrap">
          <button v-if="prevChapter" 
            @click="goToChapter(prevChapter)"
            class="px-6 py-3 rounded-full bg-surface border border-border-main hover:bg-bg-secondary flex items-center gap-2 text-text-main">
            <i class="fas fa-chevron-left"></i> 上一章
          </button>
          
          <button class="px-6 py-3 rounded-full bg-surface border border-border-main hover:bg-bg-secondary text-text-main" @click="router.go(-1)">
            返回章节列表
          </button>
          
          <button v-if="nextChapter" 
            @click="goToChapter(nextChapter)"
            class="px-6 py-3 rounded-full bg-accent-1/80 hover:bg-accent-1 text-white flex items-center gap-2">
            下一章 <i class="fas fa-chevron-right"></i>
          </button>
        </div>
        
        <p class="text-xs text-text-secondary opacity-70">提示: 使用 ← → 箭头键切换章节</p>
      </div>
    </div>
    
    <!-- Context Menu -->
    <ContextMenu ref="contextMenuRef" :items="contextMenuItems" />
    <div
      data-test="mobile-reader-actions"
      class="fixed bottom-0 left-0 right-0 z-40 border-t border-border-main bg-bg-primary/95 backdrop-blur sm:hidden"
    >
      <div class="mx-auto max-w-4xl space-y-2 px-3 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] pt-2">
        <button
          data-test="mobile-compare-toggle"
          class="flex h-11 w-full items-center justify-center rounded-lg border border-accent-2/40 bg-accent-2/10 text-sm font-semibold text-text-main transition"
          :class="compareMode ? 'border-accent-2/70 bg-accent-2/20 text-white' : 'hover:bg-accent-2/15'"
          @click="toggleCompare"
        >
          对比：{{ compareMode ? '开' : '关' }}
        </button>
        <div class="grid grid-cols-3 gap-2">
          <button
            data-test="mobile-prev-chapter"
            class="flex h-10 items-center justify-center rounded-lg border border-border-subtle text-xs font-semibold text-text-main transition hover:bg-bg-secondary"
            :class="{ 'cursor-not-allowed opacity-50': !prevChapter }"
            :disabled="!prevChapter"
            @click="goToChapter(prevChapter)"
          >
            上一章
          </button>
          <button
            data-test="mobile-back-chapter-list"
            class="flex h-10 items-center justify-center rounded-lg border border-border-subtle text-xs font-semibold text-text-main transition hover:bg-bg-secondary"
            @click="router.go(-1)"
          >
            返回章节
          </button>
          <button
            data-test="mobile-next-chapter"
            class="flex h-10 items-center justify-center rounded-lg border border-border-subtle text-xs font-semibold text-text-main transition hover:bg-bg-secondary"
            :class="{ 'cursor-not-allowed opacity-50': !nextChapter }"
            :disabled="!nextChapter"
            @click="goToChapter(nextChapter)"
          >
            下一章
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
