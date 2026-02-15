<script setup>
import { computed } from 'vue'
import { useScraperStore } from '@/stores/scraper'

const scraper = useScraperStore()
const providerOptions = computed(() => scraper.siteOptions())
const providerSchema = computed(() => scraper.providerSchemaFields().filter(field => String(field?.key || '') !== 'base_url'))
const ratePresets = [
  { key: 'conservative', label: '保守', value: 0.5, hint: '更稳，减少风控' },
  { key: 'balanced', label: '平衡', value: 1, hint: '推荐默认' },
  { key: 'fast', label: '快速', value: 1.5, hint: '速度优先（更稳）' }
]

function applyRatePreset(value) {
  scraper.state.rateLimitRps = value
}

function isRatePresetActive(value) {
  return Math.abs(Number(scraper.state.rateLimitRps || 0) - value) < 0.01
}

function schemaFieldValue(field) {
  return scraper.getSchemaFieldValue(field)
}

function schemaFieldInputType(field) {
  const type = String(field?.type || 'string')
  if (type === 'number') return 'number'
  return 'text'
}

function updateSchemaField(field, event) {
  const type = String(field?.type || 'string')
  if (type === 'boolean') {
    scraper.setSchemaFieldValue(field, !!event?.target?.checked)
    return
  }
  const value = event?.target?.value
  scraper.setSchemaFieldValue(field, type === 'number' ? Number(value) : value)
}

defineProps({
  mobileConfigOpen: Boolean
})

const emit = defineEmits(['toggle-mobile'])
</script>

<template>
  <div class="space-y-4">
    <div class="bg-surface border border-main rounded-xl p-4">
      <div class="flex items-center justify-between">
        <h3 class="font-semibold text-text-main">站点设置</h3>
        <button class="text-xs text-text-secondary xl:hidden" @click="emit('toggle-mobile')">
          <span>{{ mobileConfigOpen ? '收起' : '展开' }}</span>
          <i class="fas fa-chevron-down ml-1 transition"
            :class="mobileConfigOpen ? 'rotate-180' : ''"></i>
        </button>
      </div>
      
      <div class="mt-3 space-y-5" :class="mobileConfigOpen ? 'block' : 'hidden xl:block'">
        <p class="text-[10px] uppercase tracking-widest text-text-secondary opacity-70">基础设置</p>
        <div class="space-y-4">
          <div>
            <label class="text-xs text-text-secondary">站点</label>
            <select v-model="scraper.state.site" @change="scraper.setSite(scraper.state.site)"
              class="mt-1 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none transition-colors">
              <option v-for="item in providerOptions" :key="item.key" :value="item.key">
                {{ item.label }}
              </option>
              <option v-if="providerOptions.length === 0" value="toongod">ToonGod</option>
            </select>
            <p v-if="scraper.providerMeta.items.length > 0" class="text-[10px] text-text-secondary mt-1 opacity-70">
              可用 Provider: {{ scraper.providerMeta.items.map(item => item.key).join(', ') }}
            </p>
            <p v-if="scraper.providerMeta.error" class="text-[10px] text-red-300 mt-1">
              {{ scraper.providerMeta.error }}
            </p>
          </div>
          <div>
            <label class="text-xs text-text-secondary">基础地址</label>
            <input v-model="scraper.state.baseUrl" placeholder="https://toongod.org"
              class="mt-1 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none" />
          </div>
          <div v-if="providerSchema.length > 0" class="space-y-3 rounded-xl border border-border-subtle bg-bg-secondary/30 p-3">
            <p class="text-[10px] uppercase tracking-widest text-text-secondary opacity-70">Provider Schema</p>
            <div v-for="field in providerSchema" :key="field.key">
              <label class="text-xs text-text-secondary">{{ field.label || field.key }}</label>
              <template v-if="field.type === 'select'">
                <select
                  class="mt-1 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none"
                  :value="schemaFieldValue(field)"
                  @change="updateSchemaField(field, $event)"
                >
                  <option v-for="option in (field.options || [])" :key="option.value || option" :value="option.value || option">
                    {{ option.label || option.value || option }}
                  </option>
                </select>
              </template>
              <template v-else-if="field.type === 'boolean'">
                <div class="mt-1 flex items-center gap-2">
                  <input
                    type="checkbox"
                    class="accent-accent-1"
                    :checked="!!schemaFieldValue(field)"
                    @change="updateSchemaField(field, $event)"
                  />
                  <span class="text-[10px] text-text-secondary opacity-70">{{ field.help || '' }}</span>
                </div>
              </template>
              <template v-else>
                <input
                  :type="schemaFieldInputType(field)"
                  :placeholder="field.placeholder || ''"
                  :value="schemaFieldValue(field)"
                  @input="updateSchemaField(field, $event)"
                  class="mt-1 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none"
                />
              </template>
              <p v-if="field.help && field.type !== 'boolean'" class="text-[10px] text-text-secondary mt-1 opacity-70">
                {{ field.help }}
              </p>
            </div>
          </div>
          <div>
            <label class="text-xs text-text-secondary">抓取模式</label>
            <select v-model="scraper.state.mode" @change="scraper.setMode(scraper.state.mode)"
              class="mt-1 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none transition-colors">
              <option value="http">HTTP</option>
              <option value="headless">无头浏览器</option>
              <option value="headed">有头浏览器</option>
            </select>
            <p class="text-[10px] text-text-secondary mt-1 opacity-70" v-if="scraper.state.mode === 'headed'">
              有头模式会打开浏览器并需在终端回车继续
            </p>
            <p class="text-[10px] text-text-secondary mt-1 opacity-70" v-else-if="scraper.state.mode === 'headless'">
              无头模式不会弹窗，但需要有效状态文件
            </p>
          </div>
        </div>

        <p class="text-[10px] uppercase tracking-widest text-text-secondary opacity-70">认证与状态</p>
        <div class="space-y-3 rounded-xl border border-border-subtle bg-bg-secondary/40 p-3">
          <div>
            <label class="text-xs text-text-secondary">状态文件（可选）</label>
            <div class="mt-1 flex gap-2">
              <input v-model="scraper.state.storageStatePath" placeholder="data/toongod_state.json"
                class="flex-1 bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none" />
              <button @click="scraper.checkStateInfo()"
                class="px-3 py-2 text-xs font-semibold rounded-lg bg-bg-secondary border border-border-subtle text-text-secondary hover:border-accent-1 hover:text-text-main transition-colors">
                检测
              </button>
            </div>
            <div class="mt-2 flex items-center gap-2">
              <label
                class="px-3 py-2 text-xs font-semibold rounded-lg bg-bg-secondary border border-border-subtle text-text-secondary hover:border-accent-1 hover:text-text-main transition-colors cursor-pointer">
                上传状态文件
                <input type="file" accept=".json" class="hidden"
                  @change="scraper.uploadStateFile($event.target.files[0])" />
              </label>
              <span v-if="scraper.uploadInfo.status !== 'idle'" class="text-[10px]"
                :class="scraper.uploadInfo.status === 'success' ? 'text-green-300' : (scraper.uploadInfo.status === 'error' ? 'text-red-300' : 'text-slate-300')">
                {{ scraper.uploadInfo.message }}
              </span>
            </div>
            <p class="text-[10px] text-text-secondary mt-1 opacity-70">无界面服务器可复用本地 bootstrap 文件</p>
            <p v-if="scraper.stateInfo.status !== 'idle'" class="text-[10px] mt-1"
              :class="scraper.stateInfoClass()">
              {{ scraper.stateInfoLabel() }}
            </p>
            <div class="mt-2 flex items-center gap-2">
              <button @click="scraper.checkAccess()"
                class="px-3 py-2 text-xs font-semibold rounded-lg bg-bg-secondary border border-border-subtle text-text-secondary hover:border-accent-1 hover:text-text-main transition-colors">
                站点检测
              </button>
              <span v-if="scraper.accessInfo.status !== 'idle'" class="text-[10px]"
                :class="scraper.accessInfoClass()">
                {{ scraper.accessInfoLabel() }}
              </span>
            </div>
          </div>
          <div class="grid gap-2 sm:grid-cols-2">
            <button @click="scraper.setView('auth')"
              class="w-full bg-bg-secondary border border-border-subtle text-text-secondary text-sm font-semibold py-2 rounded-lg hover:border-accent-1 hover:text-text-main transition-colors">
              去认证
            </button>
            <a :href="scraper.authInfo.url || '/auth'" target="_blank"
              class="w-full inline-flex items-center justify-center gap-2 bg-accent-1/20 text-accent-1 text-sm font-semibold py-2 rounded-lg hover:bg-accent-1 hover:text-white transition-colors">
              打开认证页
              <i class="fas fa-external-link-alt text-[10px]"></i>
            </a>
          </div>
          <p class="text-[10px] text-text-secondary opacity-70">认证页在新标签打开，完成挑战后回到此处检测</p>
        </div>

        <details class="group rounded-xl border border-border-subtle bg-bg-secondary/40 p-3">
          <summary class="cursor-pointer list-none text-xs font-semibold text-text-main flex items-center justify-between">
            <span>高级设置 <span class="text-[10px] text-text-secondary opacity-70 ml-2">UA / 通道 / 并发</span></span>
            <i class="fas fa-chevron-down text-xs text-text-secondary transition-transform group-open:rotate-180"></i>
          </summary>
          <div class="mt-3 space-y-4">
            <div>
              <label class="text-xs text-text-secondary">持久化配置（推荐）</label>
              <div class="mt-1 flex items-center gap-2">
                <input type="checkbox" v-model="scraper.state.useProfile" class="accent-accent-1" />
                <span class="text-[10px] text-text-secondary opacity-70">开启可减少重复挑战</span>
              </div>
              <input v-if="scraper.state.useProfile" v-model="scraper.state.userDataDir" placeholder="data/toongod_profile"
                class="mt-2 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none" />
            </div>
            <div>
              <label class="text-xs text-text-secondary">固定 UA（推荐）</label>
              <div class="mt-1 flex items-center gap-2">
                <input type="checkbox" v-model="scraper.state.lockUserAgent" class="accent-accent-1"
                  @change="scraper.ensureUserAgent()" />
                <span class="text-[10px] text-text-secondary opacity-70">避免 UA 变化触发挑战</span>
              </div>
              <div v-if="scraper.state.lockUserAgent" class="mt-2 flex gap-2">
                <input v-model="scraper.state.userAgent" placeholder="浏览器 UA"
                  class="flex-1 bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none" />
                <button @click="scraper.syncUserAgent()"
                  class="px-3 py-2 text-xs font-semibold rounded-lg bg-bg-secondary border border-border-subtle text-text-secondary hover:border-accent-1 hover:text-text-main transition-colors">
                  当前 UA
                </button>
              </div>
            </div>
            <div>
              <label class="text-xs text-text-secondary">浏览器通道（推荐）</label>
              <div class="mt-1 flex items-center gap-2">
                <input type="checkbox" v-model="scraper.state.useChromeChannel" class="accent-accent-1"
                  :disabled="scraper.state.httpMode" />
                <span class="text-[10px] text-text-secondary opacity-70">仅有头模式生效，需已安装 Chrome</span>
              </div>
            </div>
            <div>
              <label class="text-xs text-text-secondary">并发</label>
              <input type="number" min="1" max="12" v-model.number="scraper.state.concurrency"
                class="mt-1 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none" />
            </div>
            <div>
              <label class="text-xs text-text-secondary">自定义速率（每秒请求）</label>
              <input
                type="number"
                min="0.2"
                max="20"
                step="0.1"
                v-model.number="scraper.state.rateLimitRps"
                class="mt-1 w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none"
              />
              <p class="mt-1 text-[10px] text-text-secondary opacity-70">建议 0.5~3，站点风控严格时可继续降低</p>
              <div class="mt-2">
                <p class="text-[10px] text-text-secondary opacity-70">速率预设</p>
                <div class="mt-1 grid grid-cols-3 gap-2">
                  <button
                    v-for="preset in ratePresets"
                    :key="preset.key"
                    type="button"
                    @click="applyRatePreset(preset.value)"
                    class="rounded-lg border px-2 py-1.5 text-[11px] font-semibold transition-colors"
                    :class="isRatePresetActive(preset.value)
                      ? 'border-accent-1 bg-accent-1/20 text-accent-1'
                      : 'border-border-subtle bg-bg-secondary text-text-secondary hover:border-accent-1 hover:text-text-main'"
                    :title="preset.hint"
                  >
                    {{ preset.label }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </details>



        <p v-if="scraper.error" class="text-xs text-red-400 p-2 bg-red-400/10 border border-red-400/20 rounded-lg">
            {{ scraper.error }}
        </p>

        <details class="group rounded-xl border border-border-subtle bg-bg-secondary/40 p-3">
          <summary class="cursor-pointer list-none text-xs font-semibold text-text-main flex items-center justify-between">
            <span>Cloudflare 指引</span>
            <span class="text-[10px] text-text-secondary opacity-70 group-open:hidden">点此查看</span>
            <i class="fas fa-chevron-down text-xs text-text-secondary transition-transform group-open:rotate-180"></i>
          </summary>
          <div class="mt-3 text-[10px] text-text-secondary space-y-1">
            <p>1) 有界面电脑运行 bootstrap 生成状态文件</p>
            <p>2) 拷贝到服务器后填写上方路径</p>
            <p>3) 建议开启“持久化配置”减少重复挑战</p>
            <p class="mt-2 font-mono text-[10px] text-text-secondary opacity-70 p-2 bg-black/20 rounded">python scripts/scraper_cli.py bootstrap --base-url https://mangaforfree.com</p>
          </div>
        </details>
      </div>
    </div>

    <!-- Task Status -->
    <div class="bg-surface border border-main rounded-xl p-4">
      <div class="flex items-center justify-between">
        <h3 class="font-semibold text-text-main">下载状态</h3>
        <span v-if="scraper.task.status" class="text-[10px] font-semibold px-2 py-1 rounded-full"
          :class="scraper.statusClass(scraper.task.status)">
          {{ scraper.statusLabel(scraper.task.status) }}
        </span>
      </div>
      <p class="mt-2 text-xs text-text-secondary">{{ scraper.task.message || '暂无任务' }}</p>
      <div class="mt-2 w-full h-1 bg-bg-secondary rounded-full overflow-hidden" v-if="scraper.task.status === 'running'">
        <div class="h-full bg-accent-1 animate-progressBar"></div>
      </div>
      <p class="mt-1 text-[10px] text-text-secondary opacity-70">队列中 {{ scraper.queue.length }} 项</p>
      <div v-if="scraper.task.report" class="mt-2 text-xs text-text-secondary space-y-1 bg-bg-secondary/30 p-2 rounded-lg">
        <p>成功 {{ scraper.task.report.success_count }} / 失败 {{ scraper.task.report.failed_count }}</p>
        <p class="break-all font-mono text-[10px] opacity-70">{{ scraper.task.report.output_dir }}</p>
      </div>
    </div>
  </div>
</template>
