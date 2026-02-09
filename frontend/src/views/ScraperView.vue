<script setup>
import { onUnmounted, onMounted, ref, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useScraperStore } from '@/stores/scraper'
import ComicBackground from '@/components/ui/ComicBackground.vue'
import GlassNav from '@/components/layout/GlassNav.vue'
import ScraperConfig from '@/views/scraper/ScraperConfig.vue'
import MangaListItem from '@/views/scraper/MangaListItem.vue'
import ChapterListItem from '@/views/scraper/ChapterListItem.vue'
import SkeletonCard from '@/views/scraper/SkeletonCard.vue'
import gsap from 'gsap'
import { useVirtualList } from '@vueuse/core'

const router = useRouter()
const scraper = useScraperStore()
const mobileTab = ref('browse')
const mobileConfigOpen = ref(true)

// Parser Logic
const parserParagraphs = computed(() => {
  const paragraphs = scraper.parser?.result?.paragraphs || []
  if (scraper.parser?.showAll) return paragraphs
  return paragraphs.slice(0, 6)
})

const hasMoreParagraphs = computed(() => {
  const paragraphs = scraper.parser?.result?.paragraphs || []
  return paragraphs.length > 6
})

const parserListSource = computed(() => scraper.parser?.listResult || scraper.parser?.result || null)
const parserListItems = computed(() => parserListSource.value?.items || [])
const parserListAvailable = computed(() => parserListSource.value?.page_type === 'list' && parserListItems.value.length > 0)
const parserListRecognized = computed(() => parserListSource.value?.recognized === true)
const parserListDownloadable = computed(() => parserListSource.value?.downloadable === true)

async function copyText(text) {
  if (!text) { alert('没有可复制内容'); return }
  try {
    await navigator.clipboard.writeText(text)
  } catch (e) {
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
}

const copyParserJson = () => copyText(scraper.parser?.result ? JSON.stringify(scraper.parser.result, null, 2) : '')
const copyParserText = () => copyText((scraper.parser?.result?.paragraphs || []).join('\n\n'))

// Animation
const animateList = () => {
    nextTick(() => {
        gsap.fromTo('.manga-item', 
            { opacity: 0, y: 20 },
            { opacity: 1, y: 0, duration: 0.4, stagger: 0.05, ease: 'power2.out' }
        )
    })
}

// Watchers
watch(() => scraper.results, animateList)
watch(() => scraper.catalog.items, animateList)

// Infinite Scroll for Catalog
const sentinel = ref(null)
const observer = ref(null)

const setupIntersectionObserver = () => {
    if (observer.value) observer.value.disconnect()
    
    observer.value = new IntersectionObserver((entries) => {
        const entry = entries[0]
        if (entry.isIntersecting && scraper.catalog.hasMore && !scraper.catalog.loading) {
            scraper.loadMoreCatalog()
        }
    }, { rootMargin: '200px' })
    
    if (sentinel.value) observer.value.observe(sentinel.value)
}

watch(sentinel, (el) => {
    if (el) setupIntersectionObserver()
})

watch(() => scraper.catalog.hasMore, (hasMore) => {
    if (hasMore) nextTick(setupIntersectionObserver)
})

watch(() => scraper.state.view, (view) => {
    if (view === 'catalog') nextTick(setupIntersectionObserver)
})

watch(() => scraper.selectedManga, (manga) => {
    if (manga) {
        mobileTab.value = 'chapters'
    }
})

// Range Selection Logic
const lastSelectedIndex = ref(-1)

const handleToggle = (id, index, event) => {
    if (event && event.shiftKey && lastSelectedIndex.value !== -1) {
        const start = Math.min(lastSelectedIndex.value, index)
        const end = Math.max(lastSelectedIndex.value, index)
        
        const subset = scraper.chapters.slice(start, end + 1)
        const allSelected = subset.every(ch => scraper.selectedIds.includes(ch.id))
        
        subset.forEach(ch => {
            if (allSelected) {
                 if (scraper.selectedIds.includes(ch.id)) scraper.toggleSelection(ch.id)
            } else {
                if (!scraper.selectedIds.includes(ch.id)) scraper.toggleSelection(ch.id)
            }
        })
    } else {
        scraper.toggleSelection(id)
    }
    lastSelectedIndex.value = index
}

// Virtual Scroll for Chapters
const { list: virtualChapters, containerProps, wrapperProps } = useVirtualList(
  computed(() => scraper.chapters),
  {
    itemHeight: 76,
    overscan: 10
  }
)

onMounted(() => {
  scraper.ensureUserAgent()
  scraper.loadProviders()
})
onUnmounted(() => {
    scraper.stopPolling()
    if (observer.value) observer.value.disconnect()
})
</script>

<template>
  <div class="min-h-screen relative pb-24 xl:pb-10">
    <ComicBackground />
    <GlassNav title="资源爬取">
      <template #actions>
        <button @click="router.push({ name: 'home' })" class="text-text-secondary hover:text-text-main transition flex items-center gap-2">
          <i class="fas fa-arrow-left"></i> 返回
        </button>
      </template>
    </GlassNav>

    <main class="container mx-auto px-4 py-6">
      <!-- Desktop Tabs & Controls -->
      <div class="hidden xl:flex items-center justify-between mb-4">
        <div class="flex flex-wrap gap-2">
            <button v-for="tab in [{k:'search',l:'搜索漫画'}, {k:'catalog',l:'站点目录'}, {k:'auth',l:'认证'}, {k:'parser',l:'URL 解析'}]" :key="tab.k"
            @click="scraper.setView(tab.k)"
            class="px-4 py-1.5 text-xs font-bold rounded-full border transition-all duration-300 backdrop-blur-md"
            :class="scraper.state.view === tab.k
                ? 'bg-accent-1/20 text-accent-1 border-accent-1/50 shadow-lg shadow-accent-1/10 scale-105'
                : 'bg-bg-secondary/40 text-text-secondary border-border-subtle hover:border-accent-1 hover:text-text-main'">
            {{ tab.l }}
            </button>
        </div>
      </div>

      <!-- Mobile Tabs -->
      <div class="flex xl:hidden flex-wrap gap-2 mb-4">
        <button v-for="tab in [{k:'browse',l:'浏览'}, {k:'catalog',l:'站点目录', view: 'catalog'}, {k:'parser',l:'URL解析', view: 'parser'}, {k:'chapters',l:'章节'}, {k:'settings',l:'设置'}]" :key="tab.k"
          @click="tab.view ? (scraper.setView(tab.view), mobileTab = 'browse') : (mobileTab = tab.k)"
          class="px-3 py-1 text-xs font-semibold rounded-full border transition-all duration-300"
          :class="mobileTab === tab.k
            ? 'bg-accent-1/20 text-accent-1 border-accent-1/50 shadow-sm scale-105'
            : 'bg-bg-secondary text-text-secondary border border-border-subtle hover:border-accent-1 hover:text-text-main'">
          {{ tab.l }}
        </button>
      </div>

      <div class="grid gap-6 xl:grid-cols-12 transition-all duration-500 ease-in-out">
        <!-- Config Panel (Left) -->
        <div class="space-y-4 transition-all duration-500 ease-[cubic-bezier(0.25,0.8,0.25,1)] overflow-hidden" 
             :class="mobileTab === 'settings' ? 'block' : 'hidden xl:block xl:col-span-3'">
            <ScraperConfig 
                :mobileConfigOpen="mobileConfigOpen" 
                @toggle-mobile="mobileConfigOpen = !mobileConfigOpen" 
            />
        </div>

        <!-- Main Content (Center) -->
        <div class="space-y-4 transition-all duration-500 ease-[cubic-bezier(0.25,0.8,0.25,1)]" 
             :class="[
                mobileTab === 'browse' ? 'block' : 'hidden xl:block',
                scraper.selectedManga ? 'xl:col-span-5' : 'xl:col-span-9'
             ]">
          
          <!-- View: Search -->
          <div v-if="scraper.state.view === 'search'" class="bg-surface border border-main rounded-xl p-4 min-h-[500px] relative overflow-hidden flex flex-col">
            
            <!-- Hero Search (Empty State) -->
            <div v-if="!scraper.loading && scraper.results.length === 0" class="flex-1 flex flex-col items-center justify-center py-20 animate-fade-in">
                <div class="text-center mb-8">
                    <h2 class="text-2xl font-bold text-text-main mb-2">探索无限漫画</h2>
                    <p class="text-text-secondary opacity-70">输入关键词或粘贴网址开始</p>
                </div>
                
                <div class="w-full max-w-lg relative group">
                    <div class="absolute inset-0 bg-accent-1/20 blur-xl rounded-full transition-all duration-500 group-hover:bg-accent-1/30"></div>
                    <div class="relative flex items-center bg-bg-secondary border border-border-subtle rounded-full overflow-hidden shadow-lg transition-all group-focus-within:border-accent-1 group-focus-within:ring-2 ring-accent-1/20">
                        <i class="fas fa-search px-4 text-text-secondary"></i>
                        <input v-model="scraper.state.keyword" 
                            @keydown.enter="scraper.search()"
                            placeholder="试试 'One Piece' 或 'ToonGod'..."
                            class="flex-1 bg-transparent py-4 text-text-main placeholder:text-text-secondary/50 focus:outline-none" />
                        <button @click="scraper.search()" :disabled="scraper.loading"
                            class="px-6 py-4 bg-accent-1 text-white font-bold hover:bg-accent-1/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
                            <span v-if="scraper.loading" class="inline-flex items-center gap-2">
                              <i class="fas fa-circle-notch fa-spin text-xs"></i>
                              <span>加载中</span>
                            </span>
                            <span v-else>搜索</span>
                        </button>
                    </div>
                </div>

                <!-- Quick Tags -->
                <div class="mt-8 flex gap-2 flex-wrap justify-center opacity-60">
                    <span v-for="tag in ['Solo Leveling', 'Omniscient Reader', 'Magic Emperor']" :key="tag"
                         @click="scraper.state.keyword = tag; scraper.search()"
                         class="px-3 py-1 bg-bg-secondary rounded-full text-xs text-text-secondary cursor-pointer hover:bg-accent-1/10 hover:text-accent-1 transition">
                        {{ tag }}
                    </span>
                </div>
            </div>

            <!-- Sticky Toolbar (Has Results) -->
            <div v-else class="flex flex-col xl:h-full">
                <div class="flex items-center gap-3 mb-4 p-2 bg-bg-secondary/30 rounded-xl border border-white/5 backdrop-blur-sm sticky top-0 z-10">
                   <div class="flex-1 relative">
                        <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary/50 text-xs"></i>
                        <input v-model="scraper.state.keyword" 
                            @keydown.enter="scraper.search()"
                            class="w-full bg-black/20 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-sm text-text-main focus:border-accent-1 focus:outline-none" />
                   </div>
                   <button @click="scraper.search()" :disabled="scraper.loading"
                       class="px-4 py-1.5 bg-accent-1 rounded-lg text-white text-xs font-bold hover:bg-accent-1/90 transition-opacity"
                       :class="scraper.loading ? 'opacity-50' : ''">
                       <span v-if="scraper.loading" class="inline-flex items-center gap-1.5">
                        <i class="fas fa-circle-notch fa-spin text-[10px]"></i>
                        <span>加载中</span>
                       </span>
                       <span v-else>Go</span>
                   </button>
                </div>

                <!-- Grid Layout -->
                <div class="grid gap-3 transition-all duration-500 content-start xl:overflow-y-auto xl:custom-scrollbar xl:flex-1 xl:min-h-0"
                    :class="scraper.selectedManga ? 'grid-cols-2 lg:grid-cols-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'">
                <MangaListItem 
                    v-for="manga in scraper.results" 
                    :key="manga.id"
                    :manga="manga"
                    class="manga-item"
                    variant="grid"
                    :isSelected="manga.id === scraper.selectedManga?.id"
                    :loading="scraper.loading && manga.id === scraper.selectedManga?.id"
                    @select="scraper.selectManga"
                />
                </div>
            </div>
          </div>



          <!-- View: Catalog -->
          <div v-if="scraper.state.view === 'catalog'" class="bg-surface border border-main rounded-xl p-4 min-h-[500px]">
             <!-- ... (header) ... -->
             <div class="flex flex-wrap items-start justify-between gap-3 mb-4">
              <div>
                <h3 class="font-semibold text-text-main">站点目录</h3>
              </div>
              <div class="flex items-center gap-2 text-xs text-text-secondary">
                <select v-model="scraper.catalog.mode" @change="scraper.setCatalogMode(scraper.catalog.mode)"
                  class="bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-2 py-1 text-xs focus:border-accent-1 outline-none cursor-pointer">
                  <option value="all">全部</option>
                  <option value="views">热度</option>
                  <option value="new">最新</option>
                  <option value="genre-manga">Manga</option>
                  <option value="genre-webtoon">Webtoon</option>
                </select>
              </div>
            </div>

            <div v-if="!scraper.catalog.loading && scraper.catalog.items.length === 0" class="flex flex-col items-center justify-center py-20 text-text-secondary opacity-50">
                <i class="fas fa-book-open text-4xl mb-4 opacity-50"></i>
                <p class="text-xs">暂无数据</p>
            </div>

            <div class="grid gap-3 transition-all duration-500"
                 :class="scraper.selectedManga ? 'grid-cols-2 lg:grid-cols-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'">
               <!-- Skeleton Loader -->
               <template v-if="scraper.catalog.loading && scraper.catalog.page === 1">
                  <SkeletonCard v-for="i in (scraper.selectedManga ? 6 : 10)" :key="i" />
               </template>

               <MangaListItem 
                v-for="manga in scraper.catalog.items" 
                :key="manga.id"
                :manga="manga"
                class="manga-item"
                variant="grid"
                :isSelected="manga.id === scraper.selectedManga?.id"
                :loading="scraper.loading && manga.id === scraper.selectedManga?.id"
                @select="scraper.selectManga"
              />
              
              <!-- Review: Skeleton appended for "load more" state -->
               <template v-if="scraper.catalog.loading && scraper.catalog.page > 1">
                  <SkeletonCard v-for="i in (scraper.selectedManga ? 3 : 5)" :key="`more-${i}`" />
               </template>
            </div>

            <!-- Infinite Scroll Sentinel & Status -->
            <div ref="sentinel" class="mt-6 flex items-center justify-center min-h-[50px]">
              <div v-if="scraper.catalog.loading" class="inline-flex items-center gap-2 text-xs text-text-secondary">
                <i class="fas fa-circle-notch fa-spin text-[10px]"></i>
                <span class="loading-line w-16"></span>
                <span>加载中</span>
              </div>
              <span v-else-if="!scraper.catalog.hasMore && scraper.catalog.items.length > 0" class="text-xs text-text-secondary opacity-50">
                - End -
              </span>
              <button v-else-if="!scraper.catalog.loading && scraper.catalog.hasMore" @click="scraper.loadMoreCatalog()" 
                class="text-xs text-accent-1 hover:underline">
                点击加载更多 (若未自动触发)
              </button>
            </div>
          </div>

          <!-- View: Auth -->
          <div v-if="scraper.state.view === 'auth'" class="bg-surface border border-main rounded-xl p-4">
             <div class="flex items-start justify-between gap-3">
              <div><h3 class="font-semibold text-text-main">站点认证</h3></div>
            </div>
            <div class="mt-4 space-y-4 text-sm bg-bg-secondary/20 p-4 rounded-xl">
               <p class="text-sm text-text-main break-all font-mono bg-black/20 p-2 rounded">{{ scraper.authInfo.url || '加载中...' }}</p>
               <a :href="scraper.authInfo.url || '/auth'" target="_blank"
                class="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-accent-1 hover:bg-accent-1/90 text-white transition-colors">
                前往认证 <i class="fas fa-external-link-alt text-xs"></i>
              </a>
            </div>
          </div>

          <!-- View: Parser -->
          <div v-if="scraper.state.view === 'parser'" class="bg-surface border border-main rounded-xl p-6 min-h-[600px] flex flex-col">
             <!-- Header -->
             <div class="text-center mb-8">
                <h3 class="text-2xl font-bold text-text-main mb-2">URL 智能解析</h3>
                <p class="text-xs text-text-secondary opacity-70">提取网页正文、漫画列表及元数据</p>
             </div>

             <!-- Input Area (Hero Style) -->
             <div class="w-full max-w-2xl mx-auto space-y-4 mb-8">
                <div class="relative group">
                    <div class="absolute inset-0 bg-accent-1/20 blur-xl rounded-xl transition-all duration-500 group-hover:bg-accent-1/30"></div>
                    <div class="relative bg-bg-secondary border border-border-subtle rounded-xl shadow-lg transition-all focus-within:border-accent-1 focus-within:ring-2 ring-accent-1/20 flex flex-col sm:flex-row overflow-hidden">
                        <input v-model="scraper.parser.url" placeholder="粘贴网页链接 (例如: https://example.com/chapter-1)"
                            class="flex-1 bg-transparent px-5 py-4 text-text-main placeholder:text-text-secondary/50 focus:outline-none"
                            @keydown.enter="scraper.parseUrl()" />
                        
                        <div class="flex items-center border-t sm:border-t-0 sm:border-l border-border-subtle bg-bg-secondary/50 px-2">
                            <select v-model="scraper.parser.mode" class="bg-transparent text-xs font-bold text-text-secondary focus:outline-none cursor-pointer py-3 px-2 hover:text-text-main transition-colors">
                                <option value="http">Fast (HTTP)</option>
                                <option value="playwright">Full (Browser)</option>
                            </select>
                            <button @click="scraper.parseUrl()" :disabled="scraper.parser.loading"
                                class="ml-2 px-6 py-2 rounded-lg bg-accent-1 text-white font-bold text-sm hover:bg-accent-1/90 transition-all disabled:opacity-50 whitespace-nowrap shadow-lg shadow-accent-1/20">
                                <span v-if="scraper.parser.loading" class="inline-flex items-center gap-2">
                                  <i class="fas fa-circle-notch fa-spin text-xs"></i>
                                  <span>解析中</span>
                                </span>
                                <span v-else>开始解析</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Results Area -->
            <div v-if="scraper.parser.result" class="animate-fade-in-up space-y-6">
                <!-- Meta & Action Cards -->
                <div class="grid gap-4 md:grid-cols-12">
                    <!-- Meta Card -->
                    <div class="md:col-span-4 bg-bg-secondary/30 rounded-xl p-4 border border-border-subtle flex flex-col gap-3">
                        <div class="flex items-center gap-3 pb-3 border-b border-border-subtle/50">
                            <div class="w-10 h-10 rounded-full bg-accent-1/10 flex items-center justify-center text-accent-1">
                                <i class="fas fa-info-circle text-lg"></i>
                            </div>
                            <div>
                                <h4 class="font-bold text-text-main text-sm">元数据</h4>
                                <p class="text-[10px] text-text-secondary opacity-70">网页基本信息</p>
                            </div>
                        </div>
                        <div class="space-y-2 text-sm mt-1">
                            <div v-if="scraper.parser.result.cover || scraper.parser.result.cover_url" class="flex items-center gap-3">
                                <img
                                    :src="scraper.proxyParserImageUrl(scraper.parser.result.cover || scraper.parser.result.cover_url)"
                                    alt="cover"
                                    class="w-16 h-20 object-cover rounded-lg border border-border-subtle bg-bg-secondary/40"
                                />
                                <div class="min-w-0">
                                    <p class="text-[10px] uppercase text-text-secondary opacity-70">解析站点</p>
                                    <p class="text-text-main font-medium truncate">{{ scraper.parser.context.host || '-' }}</p>
                                </div>
                            </div>
                            <div>
                                <p class="text-[10px] uppercase text-text-secondary opacity-70">Title</p>
                                <p class="text-text-main font-medium line-clamp-2 select-text">{{ scraper.parser.result.title || '-' }}</p>
                            </div>
                            <div>
                                <p class="text-[10px] uppercase text-text-secondary opacity-70">Author</p>
                                <p class="text-text-main font-medium select-text">{{ scraper.parser.result.author || '-' }}</p>
                            </div>
                            <div v-if="!(scraper.parser.result.cover || scraper.parser.result.cover_url)">
                                <p class="text-[10px] uppercase text-text-secondary opacity-70">解析站点</p>
                                <p class="text-text-main font-medium">{{ scraper.parser.context.host || '-' }}</p>
                            </div>
                             <div class="pt-2 mt-auto">
                                <button @click="copyParserJson()" class="w-full py-2 rounded-lg bg-bg-secondary hover:bg-bg-secondary/80 text-xs font-semibold text-text-secondary hover:text-text-main transition-colors border border-border-subtle">
                                    <i class="fas fa-code mr-1"></i> Copy JSON
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Text Content Card -->
                    <div class="md:col-span-8 bg-bg-secondary/20 rounded-xl border border-border-subtle overflow-hidden flex flex-col">
                        <div class="flex items-center justify-between px-4 py-3 bg-bg-secondary/40 border-b border-border-subtle/50">
                             <div class="flex items-center gap-2">
                                <i class="fas fa-align-left text-text-secondary text-xs"></i>
                                <span class="text-xs font-bold text-text-main">正文预览</span>
                            </div>
                            <button @click="copyParserText()" class="text-[10px] hover:bg-accent-1/10 hover:text-accent-1 px-2 py-1 rounded transition-colors text-text-secondary">
                                <i class="fas fa-copy mr-1"></i> 复制全文
                            </button>
                        </div>
                        <div class="p-4 overflow-y-auto max-h-[250px] custom-scrollbar bg-slate-50/5 dark:bg-black/20 text-sm leading-relaxed text-text-main/90 font-serif">
                             <template v-if="parserParagraphs.length > 0">
                                <p v-for="(p, i) in parserParagraphs" :key="i" class="mb-3 last:mb-0">{{ p }}</p>
                             </template>
                             <div v-else class="h-full flex flex-col items-center justify-center text-text-secondary opacity-40 min-h-[100px]">
                                 <i class="fas fa-paragraph mb-2"></i>
                                 <span>无正文内容</span>
                             </div>
                        </div>
                         <div v-if="hasMoreParagraphs" class="p-2 bg-bg-secondary/30 border-t border-border-subtle/50 text-center">
                            <button @click="scraper.parser.showAll = !scraper.parser.showAll" class="text-xs text-accent-1 hover:underline font-medium">
                                {{ scraper.parser.showAll ? '收起' : `展开剩余 ${scraper.parser.result.paragraphs.length - 6} 段` }}
                            </button>
                        </div>
                    </div>
                </div>

                 <!-- List Result -->
                 <div v-if="parserListAvailable" class="space-y-4 pt-4 border-t border-border-subtle/30">
                    <div class="flex items-center justify-between">
                         <div class="flex items-center gap-2">
                             <span class="text-sm font-bold text-text-main">
                                <i class="fas fa-list-ul mr-1 text-accent-1"></i> 列表结果
                                <span class="bg-accent-1/10 text-accent-1 text-[10px] px-2 py-0.5 rounded-full ml-2">{{ parserListItems.length }}</span>
                             </span>
                         </div>
                         <div class="flex items-center gap-3">
                            <span class="text-[10px] px-2 py-0.5 rounded border flex items-center gap-1" :class="parserListRecognized ? 'text-green-400 border-green-400/30' : 'text-amber-400 border-amber-400/30'">
                                <i class="fas" :class="parserListRecognized ? 'fa-check-circle' : 'fa-exclamation-circle'"></i>
                                {{ parserListRecognized ? '已识别' : '未识别' }}
                            </span>
                         </div>
                    </div>
                    
                    <!-- Manga Grid for Parser Results -->
                    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                        <MangaListItem 
                            v-for="item in parserListItems" 
                            :key="item.id || item.url"
                            :manga="item"
                            class="manga-item"
                            variant="grid"
                            :actionLabel="'查看'"
                            :disabled="!parserListDownloadable"
                            @select="scraper.selectMangaFromParser"
                        />
                    </div>
                 </div>
            </div>
          </div>
        </div>

        <!-- Chapters Panel (Right) -->
        <div class="space-y-4 transition-all duration-500 ease-[cubic-bezier(0.25,0.8,0.25,1)]" 
             :class="[
                mobileTab === 'chapters' ? 'block' : 'hidden xl:block',
                scraper.selectedManga 
                   ? 'xl:col-span-4 translate-x-0 opacity-100' 
                   : 'xl:col-span-0 w-0 overflow-hidden opacity-0 translate-x-20'
             ]">
          <div class="bg-surface border border-main rounded-xl p-4 min-h-[500px] flex flex-col">
            <div class="flex items-start justify-between gap-4 mb-3">
              <div>
                <h3 class="font-semibold text-text-main">章节列表</h3>
                <div v-if="scraper.selectedManga" class="text-xs text-text-secondary mt-1 flex items-center gap-2">
                   <span class="truncate max-w-[150px]">{{ scraper.selectedManga.title }}</span>
                   <span v-if="scraper.downloadSummary.total > 0" class="px-1.5 py-0.5 rounded bg-bg-secondary">{{ scraper.downloadSummary.done }}/{{ scraper.downloadSummary.total }}</span>
                </div>
              </div>
               <!-- Bulk Actions -->
              <div class="flex gap-1">
                 <button @click="scraper.selectAll()" title="全选" class="w-8 h-8 rounded-full bg-bg-secondary flex items-center justify-center text-text-secondary hover:text-white transition-colors">
                    <i class="fas fa-check-double text-xs"></i>
                 </button>
                 <button @click="scraper.clearSelection()" title="清空选择" class="w-8 h-8 rounded-full bg-bg-secondary flex items-center justify-center text-text-secondary hover:text-white transition-colors">
                    <i class="fas fa-eraser text-xs"></i>
                 </button>
                 <button @click="scraper.downloadSelected()" :disabled="scraper.selectedIds.length === 0" title="下载选中"
                    class="w-8 h-8 rounded-full bg-accent-1/20 flex items-center justify-center text-accent-1 hover:bg-accent-1 hover:text-white transition-colors disabled:opacity-50">
                    <i class="fas fa-download text-xs"></i>
                 </button>
              </div>
            </div>

            <!-- List (Virtual Scroller) -->
            <div v-bind="containerProps" class="flex-1 overflow-y-auto custom-scrollbar min-h-0">
               <div v-bind="wrapperProps" class="space-y-2">
                   <div v-if="scraper.chapters.length === 0" class="flex flex-col items-center justify-center h-40 text-text-secondary opacity-50">
                       <p class="text-xs text-center">请在列表选择漫画<br>查看章节</p>
                   </div>
                   
                   <ChapterListItem 
                     v-for="{ data, index } in virtualChapters" 
                     :key="data.id"
                     :chapter="data"
                     :isSelected="scraper.selectedIds.includes(data.id)"
                     :status="scraper.chapterStatus(data.id)"
                     :isBusy="scraper.isChapterBusy(data.id)"
                     :loading="scraper.loading"
                     @toggle="(id, event) => handleToggle(id, index, event)"
                     @download="scraper.download"
                   />
               </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
