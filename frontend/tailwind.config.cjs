/** @type {import('tailwindcss').Config} */

// Every neutral and every accent text shade below resolves to a CSS variable
// rather than to a fixed hex. globals.css declares those variables twice, once
// per theme, so switching themes is a single attribute change on <html> and no
// component re-renders and no class name changes.
//
// The shades are remapped rather than added alongside Tailwind's defaults on
// purpose. `text-slate-400` appears 62 times in this app and means "secondary
// text"; leaving it pointing at Tailwind's #94a3b8 would make it unreadable on a
// light panel, and rewriting 62 call sites to a new name is the same work with
// a worse diff.
//
// RGB triplets, not hex, because the call sites use alpha modifiers
// (`border-slate-800/60`) and Tailwind can only apply those to a
// `rgb(var(--x) / <alpha-value>)` form.
const v = (name) => `rgb(var(${name}) / <alpha-value>)`;

module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Neutrals, one role per step so the nine-step scale keeps its
        // ordering when the theme flips.
        slate: {
          100: v("--ink-1"), // primary text
          200: v("--ink-1b"), // primary text, one step down
          300: v("--ink-2"), // emphasised body
          400: v("--ink-3"), // secondary text
          500: v("--ink-4"), // muted, meta
          600: v("--ink-5"), // faint, placeholder
          700: v("--line-2"), // border, emphasised
          800: v("--line"), // border, default
          900: v("--deep"), // recessed fill
        },

        // Surfaces, for the places that were written as `bg-[#0d1117]` and
        // friends. Same values as the slate steps they replace.
        surface: v("--surface"),
        panel: v("--panel"),
        "panel-2": v("--panel-2"),
        inset: v("--inset"),
        "surface-hover": v("--surface-hover"),

        // Primary text as its own name. `text-white` cannot stand in for it:
        // this app uses text-white both for body copy on a panel, which has to
        // invert in light mode, and for the four labels sitting on bg-blue-600,
        // which must stay white in both. Those four keep `text-white`.
        ink: v("--ink-1"),

        // Accent text shades. Only 100-400 are remapped: those are the shades
        // used for text and for small status dots. 500 and up stay Tailwind's
        // defaults, so solid buttons and tinted fills (bg-blue-500/10,
        // bg-green-500/20) are identical in both themes and the four white
        // labels sitting on bg-blue-600 keep their contrast.
        blue: { 200: v("--accent-blue-softest"), 300: v("--accent-blue-soft"), 400: v("--accent-blue") },
        green: { 300: v("--accent-green-soft"), 400: v("--accent-green") },
        red: { 300: v("--accent-red-soft"), 400: v("--accent-red") },
        amber: { 200: v("--accent-amber-softest"), 300: v("--accent-amber-soft"), 400: v("--accent-amber") },
        yellow: { 400: v("--accent-amber") },
      },
    },
  },
  plugins: [],
};