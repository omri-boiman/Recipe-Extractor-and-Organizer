import React, { useEffect, useMemo, useState } from 'react'

export type IngredientSection = {
  section: string
  items: string[]
}

export type StepsSection = {
  section: string
  items: string[]
}

export type Recipe = {
  title: string
  author: string
  source_url: string
  prep_time?: number
  cook_time?: number
  total_time?: number
  servings: string
  // Updated: ingredients now come grouped by sections
  ingredients: IngredientSection[]
  // Updated: steps now come grouped by sections
  steps: StepsSection[]
}

function Navbar() {
  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded bg-emerald-500 flex items-center justify-center text-white font-bold">R</div>
        <h1 className="text-xl font-semibold">Recipe Organizer</h1>
      </div>
    </header>
  )
}

function ExtractForm({ onSaved, existingUrls = [] }: { onSaved?: () => void; existingUrls?: string[] }) {
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const normalizeUrl = (input: string) => {
    const trimmed = input.trim()
    try {
      const u = new URL(trimmed)
      u.hash = ''
      return u.href.replace(/\/$/, '')
    } catch {
      return trimmed.replace(/\/$/, '')
    }
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url) return
    setBusy(true)
    setMsg('')
    try {
      const normNew = normalizeUrl(url)
      const isDup = existingUrls.some((u) => normalizeUrl(u) === normNew)
      if (isDup) {
        const proceed = window.confirm('This URL already exists. Do you want to update the saved recipe?')
        if (!proceed) {
          setMsg('Cancelled. URL already exists.')
          return
        }
      }

      const res = await fetch(`/extract-recipe?url=${encodeURIComponent(url)}`, { method: 'POST' })
      if (!res.ok) throw new Error('Extraction failed')
      await res.json()
      setMsg('Recipe saved ✔')
      setUrl('')
      onSaved?.()
    } catch (err) {
      console.error(err)
      setMsg('Could not extract recipe. Try another URL.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="bg-white shadow-sm rounded-lg border border-slate-200 p-5 mb-6">
      <h2 className="text-lg font-semibold mb-3">Add a recipe from URL</h2>
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/your-recipe"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <button
          disabled={busy}
          className="rounded-md bg-emerald-600 text-white px-4 py-2 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >{busy ? 'Extracting…' : 'Extract & Save'}</button>
      </form>
      {msg && <p className="mt-2 text-sm text-slate-600">{msg}</p>}
    </section>
  )
}

function RecipeCard({ recipe, isActive, onSelect, onDelete }: { recipe: Recipe; isActive: boolean; onSelect: () => void; onDelete: () => void }) {
  const time = recipe.total_time || ((recipe.prep_time || 0) + (recipe.cook_time || 0))
  const flatIngredients = useMemo(
    () => (recipe.ingredients || []).flatMap((s: IngredientSection) => s.items || []),
    [recipe.ingredients]
  )
  const flatSteps = useMemo(
    () => (recipe.steps || []).flatMap((s: StepsSection) => s.items || []),
    [recipe.steps]
  )
  return (
    <button onClick={onSelect} className={`text-left bg-white rounded-lg border border-slate-200 shadow-sm hover:shadow-md transition ${isActive ? 'ring-2 ring-emerald-500' : ''}`}>
      <div className="p-4 border-b border-slate-100">
        <h3 className="font-semibold text-slate-900 line-clamp-2">{recipe.title || 'Untitled recipe'}</h3>
        <div className="text-sm text-slate-600 mt-1 flex items-center gap-3">
          <span>{recipe.author || 'Unknown author'}</span>
          <span>•</span>
          <span>{recipe.servings ? `${recipe.servings} servings` : 'Servings N/A'}</span>
          <span>•</span>
          <span>{time ? `${time} min` : 'Time N/A'}</span>
        </div>
      </div>
      <div className="p-4 grid grid-cols-2 gap-4">
        <div>
          <h4 className="text-sm font-medium text-slate-700 mb-1">Ingredients</h4>
          <ul className="text-sm text-slate-700 space-y-1">
            {flatIngredients.slice(0, 6).map((i, idx) => (
              <li key={idx} className="truncate">• {i}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-medium text-slate-700 mb-1">Steps</h4>
          <ul className="text-sm text-slate-700 space-y-1">
            {flatSteps.slice(0, 3).map((s, idx) => (
              <li key={idx} className="truncate"><span className="font-medium">{idx + 1}.</span> {s}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="px-4 pb-4 flex gap-2">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          className="text-sm text-red-700 hover:underline"
        >Delete</button>
      </div>
    </button>
  )
}

function RecipeDetails({ recipe }: { recipe: Recipe | null }) {
  if (!recipe) return <div className="text-slate-500">Select a recipe to view details.</div>
  const time = recipe.total_time || ((recipe.prep_time || 0) + (recipe.cook_time || 0))
  const hasMultipleSections = (recipe.ingredients || []).length > 1
  const hasMultipleStepSections = (recipe.steps || []).length > 1
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
      <h2 className="text-2xl font-semibold text-slate-900">{recipe.title || 'Untitled recipe'}</h2>
      <div className="mt-1 text-sm text-slate-600 flex flex-wrap gap-3">
        <span>{recipe.author || 'Unknown author'}</span>
        <span>•</span>
        <span>{recipe.servings ? `${recipe.servings} servings` : 'Servings N/A'}</span>
        <span>•</span>
        <span>{time ? `${time} min total` : 'Time N/A'}</span>
        {recipe.source_url && (
          <>
            <span>•</span>
            <a className="text-emerald-700 hover:underline" href={recipe.source_url} target="_blank">View source</a>
          </>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-6">
        <div>
          <h3 className="text-lg font-medium mb-2">Ingredients</h3>
          <div className="space-y-4">
            {(recipe.ingredients || []).map((sec, sidx) => (
              <div key={sidx}>
                {hasMultipleSections && (
                  <div className="text-sm font-semibold text-slate-700">{sec.section || 'Ingredients'}</div>
                )}
                <ul className="list-disc list-inside space-y-1">
                  {(sec.items || []).map((i, idx) => (
                    <li key={idx}>{i}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3 className="text-lg font-medium mb-2">Steps</h3>
          <div className="space-y-4">
            {(recipe.steps || []).map((sec, sidx) => (
              <div key={sidx}>
                {hasMultipleStepSections && (
                  <div className="text-sm font-semibold text-slate-700">{sec.section || 'Steps'}</div>
                )}
                <ol className="list-decimal list-inside space-y-2">
                  {(sec.items || []).map((s, idx) => (
                    <li key={idx}>{s}</li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// Removed modal - details open in a new window

export default function App() {
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setError('')
      const res = await fetch('/recipes')
      if (!res.ok) throw new Error('Failed to load recipes')
      const data = await res.json()
      setRecipes(data)
  if (data.length === 0) setSelectedIdx(null)
  else if (selectedIdx != null && selectedIdx >= data.length) setSelectedIdx(0)
    } catch (e) {
      console.error(e)
      setError('Could not load recipes.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* Section 1: Only URL input */}
        <ExtractForm onSaved={load} existingUrls={recipes.map((r) => r.source_url)} />

        {/* Section 2: Only existing recipes */}
        <section className="mt-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Saved recipes</h2>
            <div className="text-sm text-slate-600">{loading ? 'Loading…' : `${recipes.length} saved`}</div>
          </div>

          {error && <div className="mb-4 text-sm text-red-600">{error}</div>}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recipes.map((r, i) => (
              <RecipeCard
                key={`${r.source_url || r.title || 'idx'}-${i}`}
                recipe={r}
                isActive={selectedIdx === i}
                onSelect={() => {
                  // open in a new window with basic details view using a data URL
                  const win = window.open('', '_blank')
                  if (win) {
                    const time = r.total_time || ((r.prep_time || 0) + (r.cook_time || 0))
                    const multi = (r.ingredients || []).length > 1
                    const ingHtml = (r.ingredients || [])
                      .map(sec => `
                        ${multi ? `<div style='font-weight:600; color:#334155; font-size:14px; margin-top:10px;'>${sec.section || 'Ingredients'}</div>` : ''}
                        <ul>${(sec.items || []).map(i => `<li>${i}</li>`).join('')}</ul>
                      `)
                      .join('')
                    const stepsMulti = (r.steps || []).length > 1
                    const stepsHtml = (r.steps || [])
                      .map(sec => `
                        ${stepsMulti ? `<div style='font-weight:600; color:#334155; font-size:14px; margin-top:10px;'>${sec.section || 'Steps'}</div>` : ''}
                        <ol>${(sec.items || []).map(s => `<li>${s}</li>`).join('')}</ol>
                      `)
                      .join('')
                    win.document.write(`<!doctype html><html><head><title>${r.title || 'Recipe'}</title><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
                    <style>body{font-family:system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial; padding:24px; max-width:900px; margin:0 auto; background:#f8fafc; color:#0f172a} .card{background:#fff; border:1px solid #e2e8f0; border-radius:12px; box-shadow:0 1px 2px rgba(0,0,0,0.04); overflow:hidden} .card h1{font-size:28px; margin:0 0 8px} .muted{color:#475569; font-size:14px} h2{font-size:18px; margin-top:20px}</style></head><body>
                    <div class='card' style='padding:20px;'>
                      <h1>${r.title || 'Untitled recipe'}</h1>
                      <div class='muted'>${r.author || 'Unknown author'} • ${r.servings || 'Servings N/A'} • ${time ? time + ' min' : 'Time N/A'}</div>
                      ${r.source_url ? `<div style='margin-top:6px'><a href='${r.source_url}' target='_blank'>View source</a></div>` : ''}
                      <h2>Ingredients</h2>
                      ${ingHtml}
                      <h2>Steps</h2>
                      ${stepsHtml}
                    </div>
                    
                    </body></html>`)
                    win.document.close()
                  }
                }}
                onDelete={async () => {
                  if (!confirm('Delete this recipe?')) return
                  try {
                    const res = await fetch(`/recipes?source_url=${encodeURIComponent(r.source_url)}`, { method: 'DELETE' })
                    if (!res.ok) throw new Error('Delete failed')
                    await load()
                  } catch (err) {
                    console.error(err)
                    alert('Failed to delete recipe')
                  }
                }}
              />
            ))}
          </div>

          {!loading && !recipes.length && (
            <div className="text-slate-600 mt-2">No recipes saved yet. Paste a URL above to get started.</div>
          )}
        </section>
      </main>
      <footer className="text-center text-slate-500 text-sm py-8">Made with ❤️ for good food</footer>

  {/* Modal removed: details open in new window */}
    </div>
  )
}
