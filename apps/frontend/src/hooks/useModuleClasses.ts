import { useEffect, useMemo, useState } from 'react'
import { moduleService, type ModuleClass } from '../services/moduleService'
import { labelForClass } from '../utils/labels'

/**
 * Cache em memória por module_code — evita refetch entre montagens.
 * A UI nunca espera o fetch: renderiza com o fallback estático e refina
 * quando o display_name canônico do backend chega.
 */
const cache = new Map<string, ModuleClass[]>()

interface UseModuleClassesResult {
  classes: ModuleClass[]
  loading: boolean
  /** Rótulo humano: display_name da API > mapa estático > humanize. */
  classLabel: (code: string) => string
}

/**
 * useModuleClasses — fonte canônica de nomes humanos de classes YOLO.
 *
 * Envolve GET /api/modules/{code}/classes (editável em ModuleClassesPage).
 * Em erro/403 degrada silenciosamente para o mapa estático de utils/labels
 * (é enriquecimento, não bloqueio — sem toast).
 */
export function useModuleClasses(moduleCode?: string): UseModuleClassesResult {
  const [classes, setClasses] = useState<ModuleClass[]>(
    () => (moduleCode && cache.get(moduleCode)) || []
  )
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!moduleCode) {
      setClasses([])
      return
    }
    const cached = cache.get(moduleCode)
    if (cached) {
      setClasses(cached)
      return
    }
    let cancelled = false
    setLoading(true)
    moduleService
      .getClasses(moduleCode)
      .then((cls) => {
        cache.set(moduleCode, cls)
        if (!cancelled) setClasses(cls)
      })
      .catch(() => {
        // degradação silenciosa: fallback ao mapa estático
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [moduleCode])

  const byName = useMemo(() => {
    const m = new Map<string, ModuleClass>()
    for (const c of classes) m.set(c.class_name, c)
    return m
  }, [classes])

  const classLabel = (code: string): string =>
    labelForClass(code, byName.get(code)?.display_name || undefined)

  return { classes, loading, classLabel }
}
