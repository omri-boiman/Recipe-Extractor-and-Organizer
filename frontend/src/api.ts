export type DbHealth = {
  ok: boolean
  integrity?: string
  recipes_table?: boolean
  recipe_count?: number | null
  db_path?: string
  error?: string
}

export async function fetchRecipes() {
  const res = await fetch('/recipes')
  if (!res.ok) throw new Error('Failed to fetch recipes')
  return res.json()
}

export async function extractRecipe(url: string) {
  const res = await fetch(`/extract-recipe?url=${encodeURIComponent(url)}`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to extract recipe')
  return res.json()
}

export async function dbHealth(): Promise<DbHealth> {
  const res = await fetch('/db-health')
  if (!res.ok) throw new Error('DB health failed')
  return res.json()
}
