<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] }
  // items: [{ label: '', icon: '', action: () => {} }]
})

const visible = ref(false)
const position = ref({ x: 0, y: 0 })
const targetData = ref(null)
const menuRef = ref(null)

function show(event, data = null) {
  event.preventDefault()
  targetData.value = data
  
  // Handle touch or mouse
  const clientX = event.touches ? event.touches[0].clientX : event.clientX
  const clientY = event.touches ? event.touches[0].clientY : event.clientY
  
  // Prevent menu from going off-screen
  const menuWidth = 200
  const menuHeight = props.items.length * 40
  
  position.value = {
    x: Math.min(clientX, window.innerWidth - menuWidth - 20),
    y: Math.min(clientY, window.innerHeight - menuHeight - 20)
  }
  visible.value = true
}

function hide() {
  visible.value = false
  targetData.value = null
}

function handleAction(item) {
  if (item.action) {
    item.action(targetData.value)
  }
  hide()
}

// Close on click outside
function onClickOutside(e) {
  if (!visible.value) return
  const el = menuRef.value
  // On touch devices, `touchstart` can fire before the menu item click.
  // Only close when the user taps/clicks outside of the menu.
  if (el && e?.target && el.contains(e.target)) return
  hide()
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.addEventListener('touchstart', onClickOutside, { passive: true })
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
  document.removeEventListener('touchstart', onClickOutside)
})

defineExpose({ show, hide })
</script>

<template>
  <Teleport to="body">
    <Transition name="menu">
      <div v-if="visible" 
        ref="menuRef"
        class="fixed z-[150] min-w-[180px] bg-surface border border-slate-700 rounded-xl shadow-2xl overflow-hidden py-2"
        :style="{ left: position.x + 'px', top: position.y + 'px' }">
        <button v-for="(item, idx) in items" :key="idx"
          @click.stop="handleAction(item)"
          class="w-full px-4 py-2.5 text-left text-sm hover:bg-white/10 transition flex items-center gap-3"
          :class="item.danger ? 'text-red-400 hover:text-red-300' : 'text-slate-200'">
          <i v-if="item.icon" class="fas w-4" :class="item.icon"></i>
          <span>{{ item.label }}</span>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.menu-enter-active,
.menu-leave-active {
  transition: all 0.15s ease;
}
.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
