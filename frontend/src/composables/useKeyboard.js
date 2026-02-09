import { onMounted, onUnmounted } from 'vue'

/**
 * useKeyboard - Reader keyboard navigation
 * @param {Object} options - { onPrev, onNext, onEscape, onSpace }
 */
export function useKeyboard(options = {}) {
    const { onPrev, onNext, onEscape, onSpace } = options

    function handleKeydown(e) {
        // Ignore if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

        switch (e.key) {
            case 'ArrowLeft':
            case 'ArrowUp':
                e.preventDefault()
                if (onPrev) onPrev()
                break
            case 'ArrowRight':
            case 'ArrowDown':
                e.preventDefault()
                if (onNext) onNext()
                break
            case ' ':
                e.preventDefault()
                if (onSpace) onSpace()
                else window.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' })
                break
            case 'Escape':
                e.preventDefault()
                if (onEscape) onEscape()
                break
        }
    }

    onMounted(() => {
        window.addEventListener('keydown', handleKeydown)
    })

    onUnmounted(() => {
        window.removeEventListener('keydown', handleKeydown)
    })
}
