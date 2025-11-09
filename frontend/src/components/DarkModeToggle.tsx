import React, { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'

// Applies/removes the `dark` class on <html> and persists to localStorage
export default function DarkModeToggle({ className = '' }: { className?: string }) {
  const [dark, setDark] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    const saved = localStorage.getItem('theme')
    if (saved) return saved === 'dark'
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    const root = document.documentElement
    if (dark) {
      root.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [dark])

  return (
    <button
      type="button"
      aria-label="Toggle dark mode"
      onClick={() => setDark((v) => !v)}
      className={`inline-flex items-center gap-2 rounded-md border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 ${className}`}
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
      <span className="hidden sm:inline">{dark ? 'Light' : 'Dark'} mode</span>
    </button>
  )
}
