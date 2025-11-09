import React from 'react'
import DarkModeToggle from './DarkModeToggle'
import { Utensils } from 'lucide-react'

export default function Header() {
  return (
    <header className="gradient-header glass sticky top-0 z-20">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-500 text-white flex items-center justify-center shadow-soft">
            <Utensils size={20} />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Recipe Organizer</h1>
        </div>
        <div className="flex items-center gap-3">
          <DarkModeToggle />
        </div>
      </div>
    </header>
  )
}
