import React, { useEffect, useMemo, useState } from 'react'
import Header from './components/Header'
import Footer from './components/Footer'
import Card from './components/Card'
import ChatPanel from './components/ChatPanel'
import EditRecipeForm from './components/EditRecipeForm'
import { ArrowLeft } from 'lucide-react'

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

// Legacy Navbar replaced by Header component

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
    <section className="relative mb-6">
      {/* Gradient ring wrapper */}
      <div className="absolute -inset-[2px] rounded-xl bg-gradient-to-r from-brand-500/50 via-indigo-500/40 to-sky-500/50 opacity-80 blur-sm dark:opacity-60 pointer-events-none"></div>
      <div className="relative bg-white/90 dark:bg-slate-800/80 backdrop-blur-sm shadow-soft rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><span className="bg-brand-500/10 dark:bg-brand-500/20 text-brand-600 dark:text-brand-300 px-2 py-1 rounded-md text-xs font-medium">URL</span> Add a recipe from URL</h2>
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/your-recipe"
            className="flex-1 rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:focus:ring-brand-400 placeholder:text-slate-400 dark:placeholder:text-slate-500"
          />
          <button
            disabled={busy}
            className="rounded-md bg-brand-600 dark:bg-brand-500 text-white px-5 py-2 font-medium shadow hover:bg-brand-700 dark:hover:bg-brand-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >{busy ? 'Extracting…' : 'Extract & Save'}</button>
        </form>
        {msg && <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">{msg}</p>}
      </div>
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
    <Card onClick={onSelect} active={isActive} className="group h-full">
      {/* Upper content */}
      <div className="p-4 border-b border-slate-100 dark:border-slate-700">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100 line-clamp-2 group-hover:translate-x-px transition-transform min-h-[2.5rem]">{recipe.title || 'Untitled recipe'}</h3>
        <div className="text-sm text-slate-600 dark:text-slate-400 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 leading-relaxed">
          <span>{recipe.author || 'Unknown author'}</span>
          <span>•</span>
          <span>{recipe.servings ? `${recipe.servings} servings` : 'Servings N/A'}</span>
          <span>•</span>
          <span>{time ? `${time} min` : 'Time N/A'}</span>
        </div>
      </div>
      {/* Middle content grows */}
      <div className="p-4 grid grid-cols-2 gap-4 flex-1">
        <div className="flex flex-col min-h-0">
          <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Ingredients</h4>
          <ul className="text-sm text-slate-700 dark:text-slate-300 space-y-1 flex-1">
            {flatIngredients.slice(0, 6).map((i, idx) => (
              <li key={idx} className="truncate">• {i}</li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col min-h-0">
          <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Steps</h4>
          <ul className="text-sm text-slate-700 dark:text-slate-300 space-y-1 flex-1">
            {flatSteps.slice(0, 3).map((s, idx) => (
              <li key={idx} className="truncate"><span className="font-medium">{idx + 1}.</span> {s}</li>
            ))}
          </ul>
        </div>
      </div>
      {/* Footer pinned to bottom */}
      <div className="mt-auto px-4 pb-4 pt-0 flex justify-end">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          className="text-xs font-medium text-red-600 dark:text-red-400 hover:underline tracking-wide"
        >Delete</button>
      </div>
    </Card>
  )
}

function RecipeDetails({ recipe }: { recipe: Recipe | null }) {
  if (!recipe) return <div className="text-slate-500">Select a recipe to view details.</div>
  const time = recipe.total_time || ((recipe.prep_time || 0) + (recipe.cook_time || 0))
  const hasMultipleSections = (recipe.ingredients || []).length > 1
  const hasMultipleStepSections = (recipe.steps || []).length > 1
  return (
    <div className="glass rounded-xl border border-slate-200 dark:border-slate-700 shadow-soft p-5">
      <h2 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{recipe.title || 'Untitled recipe'}</h2>
      <div className="mt-1 text-sm text-slate-600 dark:text-slate-400 flex flex-wrap gap-3">
        <span>{recipe.author || 'Unknown author'}</span>
        <span>•</span>
        <span>{recipe.servings ? `${recipe.servings} servings` : 'Servings N/A'}</span>
        <span>•</span>
        <span>{time ? `${time} min total` : 'Time N/A'}</span>
        {recipe.source_url && (
          <>
            <span>•</span>
            <a className="text-emerald-700 dark:text-emerald-300 hover:underline" href={recipe.source_url} target="_blank">View source</a>
          </>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-6">
        <div>
          <h3 className="text-lg font-medium mb-2 text-slate-900 dark:text-slate-100">Ingredients</h3>
          <div className="space-y-4">
            {(recipe.ingredients || []).map((sec, sidx) => (
              <div key={sidx}>
                {hasMultipleSections && (
                  <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">{sec.section || 'Ingredients'}</div>
                )}
                <ul className="list-disc list-inside space-y-1 text-slate-700 dark:text-slate-300">
                  {(sec.items || []).map((i, idx) => (
                    <li key={idx}>{i}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3 className="text-lg font-medium mb-2 text-slate-900 dark:text-slate-100">Steps</h3>
          <div className="space-y-4">
            {(recipe.steps || []).map((sec, sidx) => (
              <div key={sidx}>
                {hasMultipleStepSections && (
                  <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">{sec.section || 'Steps'}</div>
                )}
                <ol className="list-decimal list-inside space-y-2 text-slate-700 dark:text-slate-300">
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


export default function App() {
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [editing, setEditing] = useState(false)

  const ordered = useMemo(() => recipes, [recipes])
  const current = selectedIdx != null ? ordered[selectedIdx] ?? null : null

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
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-100">
      <Header />
      <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {current ? (
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setSelectedIdx(null)}
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                <ArrowLeft size={16} /> Back
              </button>
              {!editing && (
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="ml-auto inline-flex items-center gap-2 rounded-md bg-brand-600 dark:bg-brand-500 text-white px-5 py-2 text-sm font-medium shadow hover:bg-brand-700 dark:hover:bg-brand-600 transition"
                >
                  Edit
                </button>
              )}
            </div>

            {editing ? (
              <EditRecipeForm
                recipe={current}
                onCancel={() => setEditing(false)}
                onSaved={async () => {
                  await load()
                  setEditing(false)
                }}
              />
            ) : (
              <>
                <RecipeDetails recipe={current} />
                <ChatPanel sourceUrl={current.source_url} />
              </>
            )}
          </section>
        ) : (
          <>
            {/* Section 1: Only URL input */}
            <ExtractForm onSaved={load} existingUrls={recipes.map((r) => r.source_url)} />

            {/* Section 2: Only existing recipes */}
            <section className="mt-2">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Saved recipes</h2>
                <div className="text-sm text-slate-600 dark:text-slate-400">
                  {loading ? 'Loading…' : `${recipes.length} saved`}
                </div>
              </div>

              {error && <div className="mb-4 text-sm text-red-600">{error}</div>}

              {(() => {
                const visible = showAll ? ordered : ordered.slice(0, 6)
                return (
                  <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 items-stretch">
                    {visible.map((r, i) => (
                      <RecipeCard
                        key={`${r.source_url || r.title || 'idx'}-${i}`}
                        recipe={r}
                        isActive={false}
                        onSelect={() => setSelectedIdx(i)}
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
                )
              })()}

              {!loading && recipes.length > 6 && (
                <div className="mt-4 flex justify-center">
                  <button
                    type="button"
                    onClick={() => setShowAll((v) => !v)}
                    className="px-4 py-2 text-sm rounded-md border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800"
                  >{showAll ? 'Show less' : 'Show more'}</button>
                </div>
              )}

              {!loading && !recipes.length && (
                <div className="text-slate-600 mt-2">No recipes saved yet. Paste a URL above to get started.</div>
              )}
            </section>
          </>
        )}
      </main>
      <Footer />

  {/* Modal removed: details open in new window */}
    </div>
  )
}
