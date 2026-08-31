/**
 * labels.ts — dicionário central de rótulos pt-BR (WS2 Onboarding cognitivo).
 *
 * Fonte única do frontend para traduzir chaves técnicas do backend
 * (classes YOLO, módulos, statuses, papéis, direções, períodos, integrações).
 *
 * Regras:
 *  - Values enviados à API permanecem SEMPRE as chaves cruas — aqui só se
 *    traduz a renderização.
 *  - Para classes YOLO, a fonte canônica é o display_name retornado por
 *    GET /api/modules/{code}/classes (ver hooks/useModuleClasses); os mapas
 *    abaixo são o fallback estático.
 *  - Chave desconhecida nunca quebra: humanize() garante fallback legível.
 */

// ── Classes YOLO (fallback estático — canônico é display_name da API) ────────

export const CLASS_LABELS: Record<string, string> = {
  helmet: 'Capacete',
  no_helmet: 'Sem capacete',
  vest: 'Colete',
  no_vest: 'Sem colete',
  gloves: 'Luvas',
  no_gloves: 'Sem luvas',
  glasses: 'Óculos',
  no_glasses: 'Sem óculos',
  no_safety_glasses: 'Sem óculos',
  truck: 'Caminhão',
  plate: 'Placa',
  fuel_nozzle: 'Bico de combustível',
  forklift: 'Empilhadeira',
  product_box: 'Caixa',
  pallet: 'Pallet',
  person: 'Pessoa',
  vehicle: 'Veículo',
}

/** Códigos das 8 classes EPI (ordem canônica de exibição). */
export const EPI_CLASS_CODES = [
  'helmet', 'no_helmet',
  'vest', 'no_vest',
  'gloves', 'no_gloves',
  'glasses', 'no_glasses',
] as const

// ── Módulos ───────────────────────────────────────────────────────────────────

export const MODULE_LABELS: Record<string, string> = {
  epi: 'EPI',
  fueling: 'Abastecimento',
  quality: 'Qualidade',
  parking: 'Estacionamento',
  counting: 'Contagem',
  basic: 'Básico',
  analytics: 'Análises',
}

// ── Statuses (companheiro do statusToBadgeVariant em ui/Badge) ───────────────

export const STATUS_LABELS: Record<string, string> = {
  pending: 'Na fila',
  queued: 'Na fila',
  starting: 'Iniciando',
  running: 'Em execução',
  active: 'Ativo',
  online: 'Online',
  completed: 'Concluído',
  extracted: 'Frames extraídos',
  extracting: 'Extraindo frames',
  uploaded: 'Enviado',
  stopped: 'Parado',
  inactive: 'Inativo',
  offline: 'Offline',
  error: 'Erro',
  failed: 'Falhou',
  healthy: 'Saudável',
  degraded: 'Degradado',
  critical: 'Crítico',
  down: 'Fora do ar',
  idle: 'Ocioso',
  maintenance: 'Manutenção',
  annotated: 'Anotado',
  skipped: 'Pulado',
  ok: 'Saudável',
}

/** Overrides de contexto: jobs de treinamento. */
export const TRAINING_STATUS_OVERRIDES: Record<string, string> = {
  running: 'Treinando',
  pending: 'Na fila',
}

/** Overrides de contexto: sessões de contagem. */
export const COUNTING_SESSION_OVERRIDES: Record<string, string> = {
  active: 'Em andamento',
  completed: 'Finalizada',
}

// ── Papéis ────────────────────────────────────────────────────────────────────

export const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Superadmin',
  admin: 'Admin',
  operator: 'Operador',
  analyst: 'Analista',
  trainer: 'Treinador',
  viewer: 'Viewer',
}

// ── Direções / Períodos / Integrações / Presets ──────────────────────────────

export const DIRECTION_LABELS: Record<string, string> = {
  load: 'Carga',
  unload: 'Descarga',
}

export const PERIOD_LABELS: Record<string, string> = {
  today: 'Hoje',
  week: 'Semana',
  month: 'Mês',
}

/** Types válidos hoje no backend: r2 e vast_ai (integration_routes.py). */
export const INTEGRATION_LABELS: Record<string, string> = {
  r2: 'Cloudflare R2 (armazenamento)',
  vast_ai: 'Vast.ai (GPU em nuvem)',
}

/** Presets válidos no backend: fast | balanced | quality (training_service.py). */
export const PRESET_LABELS: Record<string, string> = {
  fast: 'Rápido',
  balanced: 'Balanceado',
  quality: 'Qualidade',
}

// ── Textos de ajuda contextual (InfoTooltip) ──────────────────────────────────

export const FIELD_HELP: Record<string, string> = {
  module: 'Módulo: qual produto de monitoramento gerou o evento',
  grouping: 'Define o intervalo de agregação do gráfico de volume (hora, dia ou semana)',
  base_model: 'Rede neural de partida. Nano = mais rápido, Medium = mais preciso',
  epochs: 'Quantas vezes o modelo revê o dataset inteiro durante o treino. Mais épocas = mais aprendizado, porém mais tempo',
  batch_size: 'Quantas imagens o modelo processa por vez. Valores maiores exigem mais memória de GPU',
  learning_rate: 'Velocidade com que o modelo ajusta seus pesos. Valores altos aprendem rápido mas podem desestabilizar',
  confidence_threshold: 'Só exibe detecções com confiança igual ou acima deste valor. Ex.: 0,60 = o modelo está 60% seguro da detecção.',
  detections_per_sec: 'Quantas detecções o modelo produz por segundo nesta sessão de teste',
  latency_ms: 'Tempo entre o frame chegar e a detecção sair. Abaixo de ~150 ms é ótimo para tempo real',
  throughput: 'Quantos frames a GPU processa por segundo (throughput)',
  vram: 'Percentual da memória da GPU em uso. Acima de 85% há risco de travamento',
  map50: 'Precisão média das detecções considerando acerto de posição de 50% (métrica padrão YOLO). Quanto maior, melhor',
  map50_95: 'Precisão média das detecções considerando faixas de acerto de posição de 50% a 95% — métrica mais rigorosa',
  precision: 'Das detecções feitas, quantas estavam certas',
  recall: 'Dos objetos reais, quantos o modelo encontrou',
  scenario: 'Conjunto de classes e regras que o modelo deve observar nesta câmera',
  integration_key: 'Identificador técnico da integração. Valores válidos hoje: r2 (armazenamento) e vast_ai (GPU em nuvem)',
  fps: 'Quadros por segundo processados. Valores maiores dão mais fluidez, mas exigem mais processamento',
  dataset: 'Quantidade de imagens usadas para treinar o modelo',
}

// ── Métricas de modelo (mAP50/precisão/cobertura) ─────────────────────────────

/** LEI DA CASA: zero é uma afirmação. Métrica ausente é "—", nunca "0,0%". */
export const METRICA_AUSENTE = '—'
export const METRICA_AUSENTE_ROTULO = 'métrica não registrada'

/**
 * mAP50/precisão/cobertura tratam 0, null e undefined como NÃO REGISTRADA.
 * ponytail: o job de treino grava 0.0 (não NULL) quando a métrica não roda,
 * então 0 é indistinguível de "não medido" hoje — um modelo com 0.0
 * legitimamente medido também cairia aqui e apareceria como "—". Corrigir
 * de verdade exige o backend gravar NULL (pedido registrado, não feito
 * nesta mudança).
 */
export function metricaAusente(v: number | null | undefined): boolean {
  return v == null || v === 0
}

/** Formata métrica de modelo como percentual, ou METRICA_AUSENTE quando ausente. */
export function formatarMetricaModelo(v: number | null | undefined, casas = 1): string {
  return metricaAusente(v) ? METRICA_AUSENTE : `${((v as number) * 100).toFixed(casas)}%`
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Fallback universal: snake_case/kebab-case → 'Frase capitalizada'. */
export function humanize(key: string): string {
  if (!key) return key
  const words = key.replace(/[_-]+/g, ' ').trim()
  if (!words) return key
  return words.charAt(0).toUpperCase() + words.slice(1).toLowerCase()
}

/**
 * Rótulo humano de classe YOLO.
 * Preferência: display_name da API > mapa estático > humanize(code).
 */
export function labelForClass(code: string, apiDisplayName?: string): string {
  return apiDisplayName ?? CLASS_LABELS[code] ?? humanize(code)
}

/** Rótulo humano de módulo (epi → 'EPI', fueling → 'Abastecimento'). */
export function labelForModule(code: string): string {
  return MODULE_LABELS[code] ?? humanize(code)
}

/**
 * Rótulo humano de status técnico, com overrides por contexto
 * (ex.: statusToLabel('active', COUNTING_SESSION_OVERRIDES) → 'Em andamento').
 */
export function statusToLabel(status: string, overrides?: Record<string, string>): string {
  return overrides?.[status] ?? STATUS_LABELS[status] ?? humanize(status)
}

/** Rótulo humano de papel de usuário. */
export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? humanize(role)
}

// ── Motivo do veredito de verificação (contrato B2) ──────────────────────────

/**
 * Motivos ESTRUTURADOS de rejeição/confirmação de alerta na fila de
 * verificação. Chave estável gravada em `alerts.verification_reason` — o
 * texto muda, o dado (chave) fica, mesma regra de `CLASS_LABELS`.
 *
 *  - `epi_presente` é o MAIS IMPORTANTE: falso positivo de AUSÊNCIA (o modelo
 *    disse "sem EPI" e o EPI está lá) — é o sinal que mais alimenta a
 *    recalibração.
 *  - `nao_da_pra_ver` é ABSTENÇÃO (ADR-0067): pessoa de costas ou fora de
 *    quadro NÃO é acerto nem violação — tem nome próprio para não virar
 *    "outro" e se perder.
 */
export const MOTIVOS_VERIFICACAO = [
  { valor: 'epi_presente', rotulo: 'O EPI está presente' },
  { valor: 'nao_da_pra_ver', rotulo: 'Não dá para ver a pessoa (de costas ou fora de quadro)' },
  { valor: 'deteccao_errada', rotulo: 'O sistema confundiu com outra coisa' },
  { valor: 'outro', rotulo: 'Outro motivo' },
] as const

export type MotivoVerificacao = (typeof MOTIVOS_VERIFICACAO)[number]['valor']

const MOTIVO_VERIFICACAO_LABELS: Record<string, string> = Object.fromEntries(
  MOTIVOS_VERIFICACAO.map((m) => [m.valor, m.rotulo]),
)

/** Traduz a chave estável de `verification_reason` para o texto da tela.
 *  Valor que não bate nenhuma chave (motivo livre anterior a este contrato,
 *  ou registro legado) volta como veio — nunca some: é a única testemunha do
 *  porquê daquele veredito. */
export function labelForVerificationReason(motivo: string): string {
  return MOTIVO_VERIFICACAO_LABELS[motivo] ?? motivo
}
