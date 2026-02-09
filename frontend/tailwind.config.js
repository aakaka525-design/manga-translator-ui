/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{vue,js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Use the rgb(var(--token) / <alpha-value>) convention so Tailwind's
                // opacity modifiers (e.g. bg-accent-1/20) work with CSS variables.
                'bg-primary': 'rgb(var(--bg-primary) / <alpha-value>)',
                'bg-secondary': 'rgb(var(--bg-secondary) / <alpha-value>)',
                'surface': 'rgb(var(--bg-surface) / <alpha-value>)',
                'accent-1': 'rgb(var(--accent-1) / <alpha-value>)',
                'accent-2': 'rgb(var(--accent-2) / <alpha-value>)',
                'text-main': 'rgb(var(--text-main) / <alpha-value>)',
                'text-secondary': 'rgb(var(--text-secondary) / <alpha-value>)',
                'border-main': 'var(--border-color)',
                'border-subtle': 'var(--border-subtle)',
                'state-success': 'rgb(var(--state-success) / <alpha-value>)',
                'state-warning': 'rgb(var(--state-warning) / <alpha-value>)',
                'state-error': 'rgb(var(--state-error) / <alpha-value>)',
            },
            fontFamily: {
                'heading': ['Bebas Neue', 'sans-serif'],
                'body': ['Inter', 'sans-serif'],
                'comic': ['Bangers', 'cursive'],
            },
            boxShadow: {
                'comic': '5px 5px 0px 0px var(--card-shadow-color)',
                'comic-hover': '7px 7px 0px 0px var(--card-shadow-hover)',
            },
            borderWidth: {
                'card': 'var(--card-border-width)',
            }
        },
    },
    plugins: [],
}
