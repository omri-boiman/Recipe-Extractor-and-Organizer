import React, { useMemo, useState } from 'react'

type IngredientSection = { section: string; items: string[] }
type StepsSection = { section: string; items: string[] }

export type EditableRecipe = {
  title: string
  author: string
  source_url: string
  prep_time?: number
  cook_time?: number
  total_time?: number
  servings: string
  ingredients: IngredientSection[]
  steps: StepsSection[]
}

export default function EditRecipeForm({
  recipe,
  onCancel,
  onSaved,
}: {
  recipe: EditableRecipe
  onCancel: () => void
  onSaved: () => void | Promise<void>
}) {
  const [title, setTitle] = useState<string>(recipe.title || '')
  const [author, setAuthor] = useState<string>(recipe.author || '')
  const [servings, setServings] = useState<string>(recipe.servings || '')
  const [prepTime, setPrepTime] = useState<string>(String(recipe.prep_time || ''))
  const [cookTime, setCookTime] = useState<string>(String(recipe.cook_time || ''))
  const [totalTime, setTotalTime] = useState<string>(String(recipe.total_time || ''))
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string>('')

  const flatIngredients = useMemo(
    () => (recipe.ingredients || []).flatMap((s) => s.items || []),
    [recipe.ingredients]
  )
  const flatSteps = useMemo(
    () => (recipe.steps || []).flatMap((s) => s.items || []),
    [recipe.steps]
  )

  const [ingredientsText, setIngredientsText] = useState<string>(flatIngredients.join('\n'))
  const [stepsText, setStepsText] = useState<string>(flatSteps.join('\n'))

  const toInt = (s: string): number | undefined => {
    const t = (s ?? '').toString().trim()
    if (!t) return undefined
    const n = Number(t)
    return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : undefined
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setMsg('')
    try {
      // Build minimal change set
      const payload: Record<string, unknown> = { source_url: recipe.source_url }

      if (title !== recipe.title) payload.title = title
      if (author !== recipe.author) payload.author = author
      if (servings !== recipe.servings) payload.servings = servings

      const p = toInt(prepTime)
      const c = toInt(cookTime)
      const tt = toInt(totalTime)
      if (p !== (recipe.prep_time || undefined)) payload.prep_time = p
      if (c !== (recipe.cook_time || undefined)) payload.cook_time = c
      if (tt !== (recipe.total_time || undefined)) payload.total_time = tt

      const ingLines = ingredientsText
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0)
      const stepLines = stepsText
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0)

      // Compare flattened originals
      if (ingLines.join('\n') !== flatIngredients.join('\n')) {
        payload.ingredients = ingLines
      }
      if (stepLines.join('\n') !== flatSteps.join('\n')) {
        payload.steps = stepLines
      }

      const res = await fetch('/recipes', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('Failed to update recipe')
      setMsg('Saved ✔')
      await onSaved()
    } catch (err) {
      console.error(err)
      setMsg('Could not save changes')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="relative">
      <div className="absolute -inset-[2px] rounded-xl bg-gradient-to-r from-amber-500/40 via-pink-500/40 to-sky-500/40 opacity-70 blur-sm pointer-events-none" />
      <div className="relative bg-white/90 dark:bg-slate-800/80 backdrop-blur-sm shadow-soft rounded-xl border border-slate-200 dark:border-slate-700 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Edit recipe</h2>
          <div className="flex gap-2">
            <button type="button" onClick={onCancel} className="px-3 py-1.5 text-sm rounded-md border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800">
              Cancel
            </button>
            <button type="submit" form="recipe-edit-form" disabled={busy} className="px-4 py-1.5 text-sm rounded-md bg-brand-600 dark:bg-brand-500 text-white hover:bg-brand-700 dark:hover:bg-brand-600 disabled:opacity-50">
              {busy ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>

        <form id="recipe-edit-form" onSubmit={submit} className="grid gap-4 md:grid-cols-2">
          <label className="block">
            <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Title</div>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2" />
          </label>
          <label className="block">
            <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Author</div>
            <input value={author} onChange={(e) => setAuthor(e.target.value)} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2" />
          </label>
          <label className="block">
            <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Servings</div>
            <input value={servings} onChange={(e) => setServings(e.target.value)} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2" />
          </label>
          <div className="grid grid-cols-3 gap-3">
            <label className="block">
              <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Prep (min)</div>
              <input inputMode="numeric" value={prepTime} onChange={(e) => setPrepTime(e.target.value)} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2" />
            </label>
            <label className="block">
              <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Cook (min)</div>
              <input inputMode="numeric" value={cookTime} onChange={(e) => setCookTime(e.target.value)} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2" />
            </label>
            <label className="block">
              <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Total (min)</div>
              <input inputMode="numeric" value={totalTime} onChange={(e) => setTotalTime(e.target.value)} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2" />
            </label>
          </div>

          <label className="block md:col-span-2">
            <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Ingredients (one per line; use lines ending with ":" for section headers)</div>
            <textarea value={ingredientsText} onChange={(e) => setIngredientsText(e.target.value)} rows={6} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2 font-mono text-sm" />
          </label>

          <label className="block md:col-span-2">
            <div className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Steps (one per line; lines ending with ":" create step sections)</div>
            <textarea value={stepsText} onChange={(e) => setStepsText(e.target.value)} rows={6} className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white/80 dark:bg-slate-900/40 px-3 py-2 font-mono text-sm" />
          </label>

          {msg && (
            <div className="md:col-span-2 text-sm text-slate-600 dark:text-slate-400">{msg}</div>
          )}
        </form>
      </div>
    </section>
  )
}
