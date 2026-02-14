<script setup>
import { onMounted, onUnmounted, computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMangaStore } from '@/stores/manga'
import { useTranslateStore } from '@/stores/translate'
import { useSettingsStore } from '@/stores/settings'
import { useToastStore } from '@/stores/toast'
import { mangaApi, translateApi } from '@/api'
import ComicBackground from '@/components/ui/ComicBackground.vue'
import ComicLoading from '@/components/ui/ComicLoading.vue'
import GlassNav from '@/components/layout/GlassNav.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const mangaStore = useMangaStore()
const translateStore = useTranslateStore()
const settingsStore = useSettingsStore()
const toast = useToastStore()
const deletingManga = ref(false)
const deletingChapterId = ref(null)
const confirmState = ref({
  open: false,
  type: null,
  chapterId: null,
  chapterName: '',
})

const activeTranslatingChapters = computed(() =>
  mangaStore.chapters.filter((chapter) => chapter.isTranslating)
)
const hasTranslatingChapters = computed(() => activeTranslatingChapters.value.length > 0)
const confirmLoading = computed(() => deletingManga.value || !!deletingChapterId.value)
const deleteMangaDisabled = computed(() => hasTranslatingChapters.value || deletingManga.value || !!deletingChapterId.value)

const translationSummary = computed(() => {
  const totalPages = activeTranslatingChapters.value.reduce((sum, chapter) => {
    return sum + chapterTotalPages(chapter)
  }, 0)
  const successPages = activeTranslatingChapters.value.reduce((sum, chapter) => {
    return sum + chapterSuccessPages(chapter)
  }, 0)
  const processedPages = activeTranslatingChapters.value.reduce((sum, chapter) => {
    return sum + chapterProcessedPages(chapter)
  }, 0)
  const failedPages = activeTranslatingChapters.value.reduce((sum, chapter) => {
    return sum + Number(chapter.failedPages || 0)
  }, 0)
  const progress = totalPages > 0 ? Math.round((successPages / totalPages) * 100) : 0
  return { totalPages, successPages, processedPages, failedPages, progress }
})

onMounted(() => {
  const id = route.params.id
  if (id) {
    mangaStore.openManga(id)
    translateStore.initSSE()
  }
})

onUnmounted(() => {
  translateStore.closeSSE()
})

function goBack() {
  router.push({ name: 'home' })
}

function formatDeleteError(prefix, err) {
  const req = err?.requestId ? ` (#${err.requestId})` : ''
  const msg = err?.message || '请求失败'
  return `${prefix}: ${msg}${req}`
}

function closeConfirmDialog() {
  if (confirmLoading.value) return
  confirmState.value = {
    open: false,
    type: null,
    chapterId: null,
    chapterName: '',
  }
}

function requestDeleteManga() {
  if (hasTranslatingChapters.value) {
    toast.show('请先等待翻译完成或取消任务', 'warning')
    return
  }
  confirmState.value = {
    open: true,
    type: 'manga',
    chapterId: null,
    chapterName: mangaStore.currentManga?.name || '',
  }
}

function requestDeleteChapter(chapter, event) {
  event?.stopPropagation?.()
  if (!chapter) return
  if (chapter.isTranslating) {
    toast.show('该章节正在翻译中，暂不允许删除', 'warning')
    return
  }
  confirmState.value = {
    open: true,
    type: 'chapter',
    chapterId: chapter.id,
    chapterName: chapter.name || chapter.id,
  }
}

async function confirmDelete() {
  if (!confirmState.value.open || !mangaStore.currentManga?.id) return
  if (confirmState.value.type === 'manga') {
    deletingManga.value = true
    try {
      await mangaApi.deleteManga(mangaStore.currentManga.id)
      toast.show(`漫画删除成功: ${mangaStore.currentManga.name}`, 'success')
      await mangaStore.fetchMangas()
      await router.push({ name: 'home' })
    } catch (err) {
      toast.show(formatDeleteError('漫画删除失败', err), 'error')
    } finally {
      deletingManga.value = false
      closeConfirmDialog()
    }
    return
  }

  if (confirmState.value.type === 'chapter' && confirmState.value.chapterId) {
    const chapterId = confirmState.value.chapterId
    deletingChapterId.value = chapterId
    try {
      await mangaApi.deleteChapter(mangaStore.currentManga.id, chapterId)
      mangaStore.chapters = mangaStore.chapters.filter((chapter) => chapter.id !== chapterId)
      toast.show(`章节删除成功: ${confirmState.value.chapterName}`, 'success')
    } catch (err) {
      toast.show(formatDeleteError('章节删除失败', err), 'error')
    } finally {
      deletingChapterId.value = null
      closeConfirmDialog()
    }
  }
}

function openChapter(chapter) {
  router.push({ 
    name: 'reader', 
    params: { 
      mangaId: mangaStore.currentManga.id, 
      chapterId: chapter.id 
    } 
  })
}

function chapterTotalPages(chapter) {
  const total = Number(chapter.totalPages)
  if (total > 0) return total
  return Number(chapter.page_count) || 0
}

function chapterProcessedPages(chapter) {
  const processed = Number(chapter.processedPages)
  if (processed >= 0) return processed
  const done = Number(chapter.completedPages)
  if (done >= 0) return done
  return 0
}

function chapterSuccessPages(chapter) {
  const success = Number(chapter.successPages)
  if (success >= 0) return success
  const translated = Number(chapter.translated_count)
  if (translated >= 0) return translated
  return 0
}

function chapterProgress(chapter) {
  const explicit = Number(chapter.progress)
  if (explicit > 0) return Math.min(100, explicit)
  const total = chapterTotalPages(chapter)
  if (total <= 0) return 0
  return Math.min(99, Math.round((chapterSuccessPages(chapter) / total) * 100))
}

async function translateChapter(chapter, event) {
  event.stopPropagation() // Don't trigger card click
  
  if (chapter.isTranslating) {
    toast.show('该章节正在翻译中', 'warning')
    return
  }
  
  toast.show(`开始翻译: ${chapter.name}`, 'info')
  chapter.isTranslating = true
  
  try {
    await translateApi.translateChapter({
      manga_id: mangaStore.currentManga.id,
      chapter_id: chapter.id,
      source_language: settingsStore.settings.sourceLang,
      target_language: settingsStore.settings.targetLang,
    })
    toast.show('翻译任务已提交，等待处理结果', 'info')
  } catch (e) {
    console.error('Translate failed:', e)
    toast.show('翻译启动失败: ' + e.message, 'error')
    chapter.isTranslating = false
  }
}
</script>

<template>
  <div class="min-h-screen relative pb-24 sm:pb-10">
    <ComicBackground />
    <GlassNav :title="mangaStore.currentManga?.name || 'Loading...'">
      <template #actions>
        <button
          class="flex items-center gap-1.5 rounded-lg border border-border-subtle/60 px-2 py-1.5 text-xs text-text-secondary transition hover:bg-bg-secondary/30 hover:text-text-main sm:gap-2 sm:text-sm"
          title="返回"
          aria-label="返回"
          @click="goBack"
        >
          <i class="fas fa-arrow-left"></i>
          <span class="hidden sm:inline">返回</span>
        </button>
        <button
          data-test="delete-manga-btn"
          class="hidden items-center gap-1.5 rounded-lg border px-2 py-1.5 text-xs font-semibold transition sm:flex sm:px-3"
          :class="deleteMangaDisabled ? 'cursor-not-allowed border-state-error/30 text-state-error/50' : 'border-state-error/60 text-state-error hover:bg-state-error/20'"
          :disabled="deleteMangaDisabled"
          title="删除漫画"
          aria-label="删除漫画"
          @click="requestDeleteManga"
        >
          <i class="fas fa-trash-alt"></i>
          <span class="hidden sm:inline">删除漫画</span>
        </button>
      </template>
    </GlassNav>

    <main class="container mx-auto px-4 py-6">
      <ComicLoading v-if="mangaStore.loading" />

      <div v-else-if="mangaStore.currentManga" class="space-y-3">
        <div v-if="activeTranslatingChapters.length > 0" class="rounded-xl border border-accent-1/30 bg-accent-1/5 px-4 py-3">
          <div class="flex items-center justify-between gap-3">
            <div class="text-sm font-semibold text-text-main">
              正在翻译 {{ activeTranslatingChapters.length }} 章
            </div>
            <div class="text-xs" :class="translateStore.isConnected ? 'text-state-success' : 'text-state-warning'">
              <i class="fas mr-1" :class="translateStore.isConnected ? 'fa-circle' : 'fa-triangle-exclamation'"></i>
              {{ translateStore.isConnected ? '实时连接正常' : '实时连接重连中' }}
            </div>
          </div>
          <div class="mt-2 text-xs text-text-secondary">
            成功 {{ translationSummary.successPages }} / 失败 {{ translationSummary.failedPages }} / 总 {{ translationSummary.totalPages }}
          </div>
          <div class="mt-2 h-1.5 w-full rounded-full bg-bg-secondary overflow-hidden">
            <div class="h-full bg-accent-1 transition-all duration-300" :style="{ width: translationSummary.progress + '%' }"></div>
          </div>
        </div>

        <!-- Chapter List -->
        <div 
          v-for="chapter in mangaStore.chapters" 
          :key="chapter.id"
          class="group flex cursor-pointer flex-col gap-3 rounded-xl border border-border-main bg-surface p-4 transition hover:bg-white/5 sm:flex-row sm:items-center sm:justify-between"
          @click="openChapter(chapter)"
        >
          <div class="flex min-w-0 items-center gap-4">
            <div class="w-10 h-10 rounded-lg bg-bg-secondary flex items-center justify-center text-accent-2 group-hover:scale-110 transition-transform">
              <i class="fas fa-book-open"></i>
            </div>
            <div class="min-w-0">
              <h3 class="truncate font-semibold text-text-main">{{ chapter.name }}</h3>
              <p class="text-xs text-text-secondary opacity-70">{{ chapter.page_count }} 页</p>
              <p v-if="chapter.isTranslating || chapter.statusText" class="text-[11px] text-text-secondary mt-1">
                {{ chapter.statusText || '进行中' }}
              </p>
              <div v-if="chapter.isTranslating" class="mt-1.5 h-1.5 w-40 rounded-full bg-bg-secondary overflow-hidden">
                <div class="h-full bg-accent-1 transition-all duration-300" :style="{ width: chapterProgress(chapter) + '%' }"></div>
              </div>
            </div>
          </div>
          
          <div
            :data-test="`chapter-actions-${chapter.id}`"
            class="flex w-full flex-wrap items-center justify-start gap-2 sm:w-auto sm:justify-end sm:gap-3"
          >
            <!-- Status Badges -->
            <span v-if="chapter.isComplete" class="px-2 py-0.5 bg-state-success/20 text-state-success text-xs rounded border border-state-success/30 font-bold">已完成</span>
            <span v-else-if="chapter.has_translated" class="px-2 py-0.5 bg-state-warning/20 text-state-warning text-xs rounded border border-state-warning/30 font-bold">
              {{ chapter.translated_count }}/{{ chapter.page_count }}
            </span>
            <span v-if="chapter.isTranslating" class="text-xs text-accent-1 animate-pulse">
              翻译中 成功 {{ chapterSuccessPages(chapter) }} / 总 {{ chapterTotalPages(chapter) }}
            </span>
            
            <!-- Translate Button -->
            <button 
              v-if="!chapter.isComplete"
              @click="translateChapter(chapter, $event)"
              :disabled="chapter.isTranslating"
              class="flex h-10 min-w-[7rem] flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition sm:h-8 sm:min-w-0 sm:flex-none sm:px-3 sm:py-1.5"
              :class="chapter.isTranslating 
                ? 'bg-bg-secondary text-text-secondary opacity-50 cursor-not-allowed' 
                : 'bg-accent-1/20 text-accent-1 hover:bg-accent-1 hover:text-white'"
              :title="chapter.isTranslating ? '翻译中' : '翻译章节'"
              :aria-label="chapter.isTranslating ? '翻译中' : '翻译章节'"
            >
              <i class="fas" :class="chapter.isTranslating ? 'fa-spinner animate-spin' : 'fa-language'"></i>
              <span>{{ chapter.isTranslating ? '翻译中' : '翻译' }}</span>
            </button>
            <button
              :data-test="`delete-chapter-btn-${chapter.id}`"
              @click="requestDeleteChapter(chapter, $event)"
              :disabled="chapter.isTranslating || deletingManga || deletingChapterId === chapter.id"
              class="flex h-10 min-w-[7rem] flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold transition sm:h-8 sm:min-w-0 sm:flex-none sm:px-3 sm:py-1.5"
              :class="chapter.isTranslating || deletingManga || deletingChapterId === chapter.id
                ? 'border-state-error/20 text-state-error/40 cursor-not-allowed'
                : 'border-state-error/50 text-state-error hover:bg-state-error/20'"
              title="删除章节"
              aria-label="删除章节"
            >
              <i class="fas" :class="deletingChapterId === chapter.id ? 'fa-spinner animate-spin' : 'fa-trash-alt'"></i>
              <span>删除</span>
            </button>
            
            <i class="fas fa-chevron-right text-text-secondary opacity-50 hidden sm:inline"></i>
          </div>
        </div>
      </div>
    </main>
    <div
      data-test="mobile-manga-actions"
      class="fixed bottom-0 left-0 right-0 z-40 border-t border-border-main bg-bg-primary/95 backdrop-blur sm:hidden"
    >
      <div class="mx-auto flex max-w-4xl gap-2 px-3 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] pt-2">
        <button
          data-test="mobile-back-list-btn"
          class="flex h-11 flex-1 items-center justify-center rounded-lg border border-border-subtle text-sm font-semibold text-text-main transition hover:bg-bg-secondary"
          @click="goBack"
        >
          返回列表
        </button>
        <button
          data-test="mobile-delete-manga-btn"
          class="flex h-11 flex-1 items-center justify-center rounded-lg border text-sm font-semibold transition"
          :class="deleteMangaDisabled
            ? 'cursor-not-allowed border-state-error/30 text-state-error/50'
            : 'border-state-error/60 text-state-error hover:bg-state-error/20'"
          :disabled="deleteMangaDisabled"
          @click="requestDeleteManga"
        >
          删除漫画
        </button>
      </div>
    </div>
    <ConfirmDialog
      :open="confirmState.open"
      :title="confirmState.type === 'manga' ? '删除漫画' : '删除章节'"
      :description="confirmState.type === 'manga'
        ? `确认删除漫画「${confirmState.chapterName}」？该操作会删除该漫画全部章节和翻译结果。`
        : `确认删除章节「${confirmState.chapterName}」？该操作不可撤销。`"
      confirm-text="确认删除"
      cancel-text="取消"
      :danger="true"
      :loading="confirmLoading"
      @confirm="confirmDelete"
      @cancel="closeConfirmDialog"
    />
  </div>
</template>
