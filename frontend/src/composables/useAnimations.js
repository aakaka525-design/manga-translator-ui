import { gsap } from 'gsap'

export function useAnimations() {
    // Staggered enter animation for lists
    const animateStagger = (elements, options = {}) => {
        const {
            y = 30,
            delay = 0,
            stagger = 0.05,
            duration = 0.5,
            ease = 'back.out(1.2)'
        } = options

        return gsap.fromTo(elements,
            { opacity: 0, y: y },
            {
                opacity: 1,
                y: 0,
                duration: duration,
                delay: delay,
                stagger: stagger,
                ease: ease,
                clearProps: 'all' // Clean up after animation
            }
        )
    }

    // Single element enter animation
    const animateEnter = (element, options = {}) => {
        const {
            y = 20,
            delay = 0,
            duration = 0.4,
            ease = 'power2.out'
        } = options

        return gsap.fromTo(element,
            { opacity: 0, y: y },
            {
                opacity: 1,
                y: 0,
                duration: duration,
                delay: delay,
                ease: ease,
                clearProps: 'all'
            }
        )
    }

    return {
        animateStagger,
        animateEnter
    }
}
