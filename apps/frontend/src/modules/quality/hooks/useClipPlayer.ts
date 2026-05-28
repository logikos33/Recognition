/**
 * Hook para gerenciar a URL presigned de vídeo/clip com renovação automática.
 *
 * A URL expira em `expires_in` segundos. O hook agenda uma renovação
 * (expires_in - 120)s antes do vencimento para nunca deixar o player sem URL válida.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { qualityService } from '../services/qualityService'

interface ClipPlayerState {
  url: string | null
  loading: boolean
  error: string | null
}

export function useClipPlayer(inspectionId: string | null) {
  const [state, setState] = useState<ClipPlayerState>({ url: null, loading: false, error: null })
  const renewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const fetchUrl = useCallback(async () => {
    if (!inspectionId) return
    if (!mountedRef.current) return

    setState(s => ({ ...s, loading: true, error: null }))
    try {
      const res = await qualityService.getClipUrl(inspectionId)
      if (!mountedRef.current) return
      const { url, expires_in } = res.data

      setState({ url, loading: false, error: null })

      // Agendar renovação 2 min antes do vencimento
      const renewIn = Math.max(10, expires_in - 120) * 1000
      if (renewTimerRef.current) clearTimeout(renewTimerRef.current)
      renewTimerRef.current = setTimeout(fetchUrl, renewIn)
    } catch (err) {
      if (!mountedRef.current) return
      setState({ url: null, loading: false, error: 'Erro ao gerar URL do clipe' })
    }
  }, [inspectionId])

  useEffect(() => {
    mountedRef.current = true
    fetchUrl()
    return () => {
      mountedRef.current = false
      if (renewTimerRef.current) clearTimeout(renewTimerRef.current)
    }
  }, [fetchUrl])

  return { ...state, refresh: fetchUrl }
}

/**
 * Mesmo padrão, mas para URL de evidência (foto estática) de uma inspeção.
 */
export function useEvidenceUrl(inspectionId: string | null) {
  const [state, setState] = useState<ClipPlayerState>({ url: null, loading: false, error: null })
  const renewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const fetchUrl = useCallback(async () => {
    if (!inspectionId) return
    if (!mountedRef.current) return

    setState(s => ({ ...s, loading: true, error: null }))
    try {
      const res = await qualityService.getEvidenceUrl(inspectionId)
      if (!mountedRef.current) return
      const { url, expires_in } = res.data

      setState({ url, loading: false, error: null })

      const renewIn = Math.max(10, expires_in - 120) * 1000
      if (renewTimerRef.current) clearTimeout(renewTimerRef.current)
      renewTimerRef.current = setTimeout(fetchUrl, renewIn)
    } catch {
      if (!mountedRef.current) return
      setState({ url: null, loading: false, error: 'Erro ao gerar URL da evidência' })
    }
  }, [inspectionId])

  useEffect(() => {
    mountedRef.current = true
    fetchUrl()
    return () => {
      mountedRef.current = false
      if (renewTimerRef.current) clearTimeout(renewTimerRef.current)
    }
  }, [fetchUrl])

  return { ...state, refresh: fetchUrl }
}
