import React, { useState } from 'react'
import TypingDots from './TypingDots'

type Msg = { role: 'user' | 'assistant'; content: string }

export default function ChatPanel({ sourceUrl, className = '' }: { sourceUrl: string; className?: string }) {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: 'assistant',
      content:
        "Hi! I can answer questions only about this recipe's ingredients, steps, times, and substitutions. What would you like to know?",
    },
  ])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)

  const ask = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = q.trim()
    if (!text || busy) return
    setQ('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setBusy(true)
    try {
      const res = await fetch('/recipes/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: sourceUrl, question: text }),
      })
      if (!res.ok) throw new Error('Request failed')
      const data = await res.json()
      const ans = (data && (data.answer || data.result || '')) || 'Sorry, I could not answer.'
      setMessages((m) => [...m, { role: 'assistant', content: ans }])
    } catch {
      setMessages((m) => [...m, { role: 'assistant', content: 'There was an error answering. Please try again.' }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`glass rounded-xl overflow-hidden ${className}`}>
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 font-semibold">Ask about this recipe</div>
      <div className="p-4 flex flex-col gap-3 max-h-[340px] overflow-auto">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`chat-bubble ${m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}>{m.content}</div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="chat-bubble chat-bubble-assistant">
              <TypingDots />
            </div>
          </div>
        )}
      </div>
      <form onSubmit={ask} className="p-4 border-t border-slate-200 dark:border-slate-700 flex gap-2">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask a question about this recipe..."
          className="flex-1 rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:focus:ring-brand-400"
        />
        <button
          disabled={busy}
          className="rounded-md bg-brand-600 dark:bg-brand-500 text-white px-4 py-2 font-medium shadow hover:bg-brand-700 dark:hover:bg-brand-600 disabled:opacity-50"
        >Send</button>
      </form>
    </div>
  )
}
