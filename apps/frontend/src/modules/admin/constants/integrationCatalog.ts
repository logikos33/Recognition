/**
 * integrationCatalog — catálogo único de integrações (WS5).
 *
 * Fonte única de título/descrição/helpText por integration_type, consumida
 * pela AdminIntegrationsPage (cards editáveis) e pela seção read-only de
 * integrações do Console de Teste (AdminTestConsolePage).
 *
 * Cobre os 5 tipos da migration 082:
 *   r2 | vast_ai | generic_gpu | notification | byo_db
 *
 * Metadado estático por tipo — NÃO é dado por tenant (por isso vive no
 * frontend e não em coluna no banco).
 */

export interface IntegrationCardSpec {
  type: string
  title: string
  description: string
  /** Onde obter a chave + escopo de uso (exibido como ajuda ao operador). */
  helpText: string
  configFields: { key: string; label: string; placeholder: string }[]
  secretLabel: string
  secretPlaceholder: string
}

export const INTEGRATION_CATALOG: IntegrationCardSpec[] = [
  {
    type: 'r2',
    title: 'Storage — Cloudflare R2',
    description: 'Armazenamento de frames, modelos e datasets.',
    helpText:
      'Crie as credenciais em dash.cloudflare.com → R2 → Manage R2 API Tokens. '
      + 'Usadas para gravar e ler frames, datasets e modelos treinados.',
    configFields: [
      { key: 'endpoint', label: 'Endpoint', placeholder: 'https://ACCOUNT.r2.cloudflarestorage.com' },
      { key: 'bucket', label: 'Bucket', placeholder: 'recognition-prod' },
    ],
    secretLabel: 'Secret Access Key',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'vast_ai',
    title: 'Provedor GPU — Vast.ai',
    description: 'Treinamento de modelos YOLO em GPUs sob demanda.',
    helpText:
      'Crie a API Key em cloud.vast.ai → Account → API Keys. '
      + 'Usada apenas para alugar GPUs de treinamento — nunca para inferência.',
    configFields: [
      { key: 'gpu_type', label: 'GPU preferida', placeholder: 'RTX_3090' },
    ],
    secretLabel: 'API Key',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'generic_gpu',
    title: 'GPU Genérico',
    description: 'Provedor GPU alternativo (SSH/API personalizado).',
    helpText:
      'Informe o endpoint SSH/API do seu provedor de GPU e o token de acesso. '
      + 'Usado como alternativa ao Vast.ai para treinos em infra própria.',
    configFields: [
      { key: 'endpoint', label: 'Endpoint SSH/API', placeholder: 'https://meu-gpu.exemplo.com' },
    ],
    secretLabel: 'Token / Senha',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'notification',
    title: 'Notificações',
    description: 'Webhook ou chave para envio de alertas externos.',
    helpText:
      'Cole a URL do webhook do seu canal (Slack, Teams, Discord ou endpoint próprio). '
      + 'Usada para enviar alertas de violação em tempo real.',
    configFields: [
      { key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://hooks.exemplo.com/...' },
    ],
    secretLabel: 'Secret do Webhook',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
  {
    type: 'byo_db',
    title: 'Banco de Dados Próprio',
    description: 'Conexão PostgreSQL dedicada do tenant (BYO database).',
    helpText:
      'Informe a connection string PostgreSQL fornecida pelo seu DBA ou provedor '
      + '(ex.: Railway, RDS, Neon). Usada para isolar os dados do tenant em banco próprio.',
    configFields: [
      { key: 'host', label: 'Host', placeholder: 'db.exemplo.com' },
      { key: 'database', label: 'Database', placeholder: 'recognition' },
    ],
    secretLabel: 'Senha / Connection String',
    secretPlaceholder: 'Deixe vazio para manter atual',
  },
]

/** Spec do catálogo por integration_type (fallback: título = próprio tipo). */
export function integrationSpec(type: string): IntegrationCardSpec | undefined {
  return INTEGRATION_CATALOG.find(spec => spec.type === type)
}
