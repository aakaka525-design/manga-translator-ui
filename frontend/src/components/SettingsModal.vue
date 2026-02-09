<script setup>
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const onUpscaleModelChange = (event) => {
  const value = event?.target?.value
  const model = settingsStore.availableUpscaleModels.find((item) => item.id === value)
  if (model) {
    settingsStore.selectUpscaleModel(model)
  }
}

const onUpscaleScaleChange = (event) => {
  const value = Number(event?.target?.value)
  if (!Number.isNaN(value)) {
    settingsStore.selectUpscaleScale(value)
  }
}

const onUpscaleEnableToggle = async () => {
  await settingsStore.setUpscaleEnabled(!settingsStore.settings.upscaleEnabled)
}
</script>

<template>
  <!-- Settings Modal -->
  <Teleport to="body" :disabled="!settingsStore.showModal">
    <div v-show="settingsStore.showModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="settingsStore.showModal = false"></div>
      <div class="bg-surface border border-border-main w-full max-w-lg rounded-2xl p-6 relative z-10 shadow-2xl">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-xl font-bold flex items-center gap-2">
            <i class="fas fa-sliders-h text-accent-1"></i> 设置
          </h3>
          <button @click="settingsStore.showModal = false" class="p-2 hover:bg-white/10 rounded-full transition">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="space-y-6 max-h-[70vh] overflow-y-auto pr-2">
          <!-- Appearance -->
          <div>
            <h4 class="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wider">外观</h4>
            <button @click="settingsStore.toggleTheme()"
              class="w-full px-4 py-3 rounded-xl text-left transition flex items-center justify-between group border border-transparent bg-bg-secondary/50 hover:bg-bg-secondary">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
                  :class="settingsStore.settings.theme === 'pop' ? 'bg-accent-1 text-white' : 'bg-bg-primary text-text-secondary'">
                  <i class="fas" :class="settingsStore.settings.theme === 'pop' ? 'fa-bolt' : 'fa-moon'"></i>
                </div>
                <div>
                  <span class="font-medium block text-text-main">
                    {{ settingsStore.settings.theme === 'pop' ? 'High-Voltage Pop' : 'Dark Glass' }}
                  </span>
                  <span class="text-xs text-text-secondary opacity-70">
                    {{ settingsStore.settings.theme === 'pop' ? '高亮波普风格' : '沉浸式暗黑风格' }}
                  </span>
                </div>
              </div>
              <div class="relative w-11 h-6 bg-bg-primary rounded-full transition-colors duration-200"
                :class="settingsStore.settings.theme === 'pop' ? 'bg-accent-1' : 'bg-bg-primary'">
                <div class="absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform duration-200"
                  :class="settingsStore.settings.theme === 'pop' ? 'translate-x-5' : ''"></div>
              </div>
            </button>
          </div>

          <!-- AI Model -->
          <div>
            <h4 class="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wider">AI 模型</h4>
            <div class="space-y-2">
              <button v-for="model in settingsStore.availableModels" :key="model.id"
                @click="settingsStore.selectModel(model)"
                class="w-full px-4 py-3 rounded-xl text-left transition flex items-center justify-between group border"
                :class="settingsStore.settings.aiModel === model.id ? 'bg-accent-1/20 border-accent-1/30' : 'bg-bg-secondary/50 border-transparent hover:bg-bg-secondary'">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg flex items-center justify-center"
                    :class="settingsStore.settings.aiModel === model.id ? 'bg-accent-1 text-white' : 'bg-bg-primary text-text-secondary'">
                    <i class="fas fa-robot"></i>
                  </div>
                  <div>
                    <span class="font-medium block"
                      :class="settingsStore.settings.aiModel === model.id ? 'text-accent-1' : 'text-text-main'">
                      {{ model.name }}
                    </span>
                    <span class="text-xs text-text-secondary opacity-70">{{ model.desc }}</span>
                  </div>
                </div>
                <div class="w-5 h-5 rounded-full border border-border-subtle flex items-center justify-center">
                  <div class="w-2.5 h-2.5 rounded-full bg-accent-1 transition-transform"
                    :class="settingsStore.settings.aiModel === model.id ? 'scale-100' : 'scale-0'"></div>
                </div>
              </button>
            </div>
          </div>

          <!-- Upscale -->
          <div>
            <h4 class="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wider">高清放大</h4>
            <button
              data-test="upscale-enable-toggle"
              @click="onUpscaleEnableToggle"
              class="w-full px-4 py-3 rounded-xl text-left transition flex items-center justify-between group border border-transparent bg-bg-secondary/50 hover:bg-bg-secondary mb-3"
            >
              <div class="flex items-center gap-3">
                <div
                  class="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
                  :class="settingsStore.settings.upscaleEnabled ? 'bg-accent-1 text-white' : 'bg-bg-primary text-text-secondary'"
                >
                  <i class="fas fa-expand"></i>
                </div>
                <div>
                  <span class="font-medium block text-text-main">超分增强</span>
                  <span class="text-xs text-text-secondary opacity-70">
                    {{ settingsStore.settings.upscaleEnabled ? '已开启，输出更清晰' : '已关闭，保留原始渲染速度' }}
                  </span>
                </div>
              </div>
              <div
                class="relative w-11 h-6 rounded-full transition-colors duration-200"
                :class="settingsStore.settings.upscaleEnabled ? 'bg-accent-1' : 'bg-bg-primary'"
              >
                <div
                  class="absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform duration-200"
                  :class="settingsStore.settings.upscaleEnabled ? 'translate-x-5' : ''"
                ></div>
              </div>
            </button>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-xs text-text-secondary opacity-70 mb-1 block">放大模型</label>
                <select
                  v-model="settingsStore.settings.upscaleModel"
                  data-test="upscale-model-select"
                  @change="onUpscaleModelChange"
                  :disabled="!settingsStore.settings.upscaleEnabled"
                  class="w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none"
                  :class="!settingsStore.settings.upscaleEnabled ? 'opacity-60 cursor-not-allowed' : ''"
                >
                  <option v-for="model in settingsStore.availableUpscaleModels" :key="model.id" :value="model.id">
                    {{ model.name }}
                  </option>
                </select>
              </div>
              <div>
                <label class="text-xs text-text-secondary opacity-70 mb-1 block">放大倍率</label>
                <select
                  v-model.number="settingsStore.settings.upscaleScale"
                  data-test="upscale-scale-select"
                  @change="onUpscaleScaleChange"
                  :disabled="!settingsStore.settings.upscaleEnabled"
                  class="w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none"
                  :class="!settingsStore.settings.upscaleEnabled ? 'opacity-60 cursor-not-allowed' : ''"
                >
                  <option
                    v-for="scale in settingsStore.getUpscaleScalesForModel(settingsStore.settings.upscaleModel)"
                    :key="scale"
                    :value="scale"
                  >
                    x{{ scale }}
                  </option>
                </select>
              </div>
            </div>
          </div>

          <!-- Language -->
          <div>
            <h4 class="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wider">翻译偏好</h4>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-xs text-text-secondary opacity-70 mb-1 block">源语言</label>
                <select v-model="settingsStore.settings.sourceLang" @change="settingsStore.saveSettings()"
                  class="w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none">
                  <option value="en">English (英语)</option>
                  <option value="ja">Japanese (日语)</option>
                  <option value="ko">Korean (韩语)</option>
                  <option value="zh">Chinese (中文)</option>
                </select>
              </div>
              <div>
                <label class="text-xs text-text-secondary opacity-70 mb-1 block">目标语言</label>
                <select v-model="settingsStore.settings.targetLang" @change="settingsStore.saveSettings()"
                  class="w-full bg-bg-secondary border border-border-subtle text-text-main rounded-lg px-3 py-2 text-sm focus:border-accent-1 focus:outline-none">
                  <option value="zh">Chinese (中文)</option>
                  <option value="en">English (英语)</option>
                  <option value="ja">Japanese (日语)</option>
                </select>
              </div>
            </div>
          </div>

          <!-- System -->
          <div>
            <h4 class="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wider">系统</h4>
            <button @click="settingsStore.openLogs()"
              class="w-full px-4 py-3 rounded-xl bg-bg-secondary/50 hover:bg-bg-secondary border border-transparent hover:border-border-subtle text-left transition flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-bg-primary text-text-secondary flex items-center justify-center">
                  <i class="fas fa-terminal"></i>
                </div>
                <div>
                  <span class="font-medium block text-text-main">系统日志</span>
                  <span class="text-xs text-text-secondary opacity-70">查看最近的运行日志</span>
                </div>
              </div>
              <i class="fas fa-chevron-right text-text-secondary"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Logs Modal -->
  <Teleport to="body">
    <div v-if="settingsStore.showLogsModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="settingsStore.showLogsModal = false"></div>
      <div class="bg-surface border border-border-main w-full max-w-4xl rounded-2xl p-6 relative z-10 shadow-2xl">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-xl font-bold flex items-center gap-2">
            <i class="fas fa-terminal text-accent-2"></i> 系统日志
          </h3>
          <button @click="settingsStore.showLogsModal = false" class="p-2 hover:bg-white/10 rounded-full transition">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <pre class="bg-black/50 rounded-xl p-4 text-xs text-green-400 font-mono overflow-auto h-[60vh] whitespace-pre-wrap">{{ settingsStore.logsContent || 'Loading...' }}</pre>
        <div class="mt-4 flex justify-end">
          <button @click="settingsStore.fetchLogs()" :disabled="settingsStore.loading"
            class="px-4 py-2 rounded-lg bg-bg-secondary text-sm hover:bg-bg-primary transition shadow-md">
            <i class="fas fa-sync-alt mr-2" :class="{ 'animate-spin': settingsStore.loading }"></i> 刷新
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
