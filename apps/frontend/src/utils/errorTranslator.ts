/**
 * Translates HTTP errors into user-friendly Portuguese messages.
 * Deduplicates identical toasts within a time window.
 */
import { useToastStore } from '../components/ui/Toast/useToast'

// ── Nada de tripa na tela (issues #799/#800) ────────────────────────────────
// MEDIDO no DEV: numa janela de deploy, qualquer uma das 8 telas do EPI
// imprimia o SELECT que falhou e o nome interno do schema do tenant
// (`rvb_isolantes`). O conserto de raiz é no backend — a resposta não sai mais
// com isso. Esta é a segunda tranca: o `api.ts` monta `ApiError.message` a
// partir do corpo do servidor, e dezenas de telas jogam esse texto na tela.
// Se algum dia voltar tripa de uma resposta que não é da nossa API (proxy,
// gateway, worker antigo), ela para aqui.
const TRIPA = new RegExp(
  [
    '\\b(select|insert|update|delete|drop|truncate|alter|create)\\b[\\s\\S]{0,120}?' +
      '\\b(from|into|table|set|where|values|join|returning)\\b',
    'search_path',
    '\\bschemas?\\b',
    'psycopg',
    'sqlalchemy',
    '\\btraceback\\b',
    '\\.py["\']?[,:]?\\s*line\\s+\\d+',
    '\\b[a-z][a-z0-9+.-]*://[^\\s/@]*:[^\\s/@]*@',
    '\\b(postgres|postgresql|mysql|mongodb|redis|amqp)://',
    '\\bconnection\\s+pool\\b',
    '\\bpool\\s+(exhausted|timeout)',
    '\\brelation\\s+"',
    '\\bcolumn\\s+"',
    '\\bduplicate\\s+key\\s+value\\b',
    'violates\\s+\\w+\\s+constraint',
    '\\b(DETAIL|HINT|CONTEXT):',
    '\\bcould\\s+not\\s+connect\\s+to\\s+server\\b',
    '\\bserver\\s+closed\\s+the\\s+connection\\b',
    // Estouro de render (o que o ErrorBoundary pega): a mensagem do runtime do
    // JS é tão jargão quanto um SELECT para quem opera a fábrica.
    '\\b(type|reference|syntax|range)error\\b',
    'cannot\\s+read\\s+propert',
    'is\\s+not\\s+a\\s+function',
    '(undefined|null)\\s+is\\s+not\\s+an?\\s+',
    'unexpected\\s+token',
    'failed\\s+to\\s+fetch',
    'dynamically\\s+imported\\s+module',
    '\\bchunk\\b.{0,20}\\bload',
  ].join('|'),
  'i',
)

// Sem número de HTTP: "503" não diz nada para quem opera a fábrica.
const GENERICA_CLIENTE = 'Não foi possível concluir esta ação. Confira os dados e tente de novo.'
const GENERICA_SERVIDOR = 'O sistema não conseguiu responder agora. Tente de novo em instantes.'

/** True quando o texto carrega tripa técnica que não pode ir para a tela. */
export function pareceTripa(texto: string): boolean {
  return !!texto && TRIPA.test(texto)
}

/**
 * Texto que pode ir para a tela. No-op quando a mensagem já é de gente — só
 * troca quando detecta tripa (ou quando não veio mensagem nenhuma).
 * Nunca engole o erro: quem chama continua mostrando QUE falhou.
 */
export function mensagemHumana(rawMessage: string, status = 0): string {
  if (rawMessage && !pareceTripa(rawMessage)) return rawMessage
  return status >= 400 && status < 500 ? GENERICA_CLIENTE : GENERICA_SERVIDOR
}

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
  return mensagemHumana(rawMessage, status)
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
  // 410 da fila de anotação = cursor cujo frame sumiu (vídeo pai apagado).
  // CropClassifier recarrega a fila sozinho — avisar de erro seria mentira.
  { statuses: [410], pathContains: '/training/images' },
  // stream/info 404 é sempre "câmera fora do tenant do token" (C-01) — pode ser
  // cross-tenant legítimo (superadmin navegando outro tenant) ou câmera
  // removida. CameraCell decide o aviso caso a caso (banner "assumir
  // contexto" vs. este mesmo toast) para não duplicar — ver
  // services/crossTenantCameras.ts.
  { statuses: [404], pathContains: '/stream/info' },
  // 409 em /verification = OUTRA PESSOA julgou o alerta primeiro (guarda do
  // UPDATE em verification_service.py). NÃO é falha do operador, e as cinco
  // telas que chamam `POST /verification/<id>/review` já mostram a frase do
  // servidor ("Fulana já avaliou este alerta há 2 minutos") no seu próprio
  // aviso. Sem esta regra saíam DOIS toasts para o mesmo fato — e o genérico
  // saía VERMELHO, dizendo que deu erro o que na verdade é informação.
  { statuses: [409], pathContains: '/verification' },
  // 403 em /auth/login é SEMPRE `password_change_required` (é o único 403 que
  // a rota emite — auth/routes.py). Não é "sem permissão": é a senha
  // temporária cobrada, e a própria tela de login abre o formulário de troca
  // logo abaixo. O toast genérico saía VERMELHO dizendo a coisa errada em
  // cima da instrução certa.
  { statuses: [403], pathContains: '/auth/login' },
  // Mesma tela, mesmo motivo (#819). `/auth/change-password` tem um chamador
  // só — o formulário de troca em `app/acesso/Entrar.tsx` — e ele SEMPRE põe a
  // frase do servidor na sua caixa de erro. Sem esta regra saíam DOIS
  // vermelhos para o mesmo fato na PRIMEIRA tela do produto (o ToastProvider
  // mora na raiz, main.tsx:17 — aparece deslogado também). 500 continua
  // gritando: aí não é dado ruim, é o sistema caído.
  { statuses: [400, 429], pathContains: '/auth/change-password' },
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
