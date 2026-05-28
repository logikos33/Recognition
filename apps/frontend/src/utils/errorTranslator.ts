/**
 * Translates HTTP errors into user-friendly Portuguese messages.
 * Deduplicates identical toasts within a time window.
 */
import { useToastStore } from '../components/ui/Toast/useToast'

const TRANSLATIONS: Array<{ match: (status: number, url: string, msg: string) => boolean; text: string }> = [
  { match: (s, u) => s === 404 && u.includes('stream'), text: 'Camera nao esta transmitindo' },
  { match: (s) => s === 503, text: 'Servico temporariamente indisponivel, tentando reconectar...' },
  { match: (s, u) => s === 500 && u.includes('stats'), text: 'Erro ao carregar estatisticas' },
  { match: (_, __, m) => /refused|connect/i.test(m), text: 'Falha na conexao. Verifique a rede.' },
  { match: (_, __, m) => /timeout|timed.out|aborted/i.test(m), text: 'Servidor nao respondeu a tempo.' },
{ match: (s) => s === 403, text: 'Sem permissao para esta acao.' },
]

export function translateError(status: number, url: string, rawMessage: string): string {
  for (const t of TRANSLATIONS) {
    if (t.match(status, url, rawMessage)) return t.text
  }
  if (status >= 500) return 'Erro interno do servidor'
  return rawMessage || `Erro ${status}`
}

// Deduplication: track recent messages to group identical errors
const _recent = new Map<string, { count: number; timer: ReturnType<typeof setTimeout> }>()
const DEDUP_WINDOW_MS = 3000

// Endpoints de polling em background — falhas 503/500 não devem gerar toast intrusivo.
// O componente usa Promise.allSettled e lida com o estado vazio silenciosamente.
const SILENT_RULES: Array<{ statuses: number[]; pathContains: string }> = [
  { statuses: [503, 500], pathContains: '/cameras' },
  { statuses: [503, 500], pathContains: '/modules/' },
  { statuses: [503, 500], pathContains: '/training' },
]

export function showErrorToast(status: number, url: string, rawMessage: string) {
  const isSilent = SILENT_RULES.some(
    r => r.statuses.includes(status) && url.includes(r.pathContains)
  )
  if (isSilent) return

  const friendly = translateError(status, url, rawMessage)
  const key = friendly

  const existing = _recent.get(key)
  if (existing) {
    existing.count += 1
    clearTimeout(existing.timer)
    existing.timer = setTimeout(() => _recent.delete(key), DEDUP_WINDOW_MS)
    // Don't show duplicate within window
    return
  }

  _recent.set(key, {
    count: 1,
    timer: setTimeout(() => {
      const entry = _recent.get(key)
      if (entry && entry.count > 1) {
        useToastStore.getState().push({ variant: 'error', title: `${friendly} (x${entry.count})` })
      }
      _recent.delete(key)
    }, DEDUP_WINDOW_MS),
  })

  useToastStore.getState().push({ variant: 'error', title: friendly })
}
