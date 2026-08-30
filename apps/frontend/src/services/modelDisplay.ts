/**
 * Nome de modelo voltado ao cliente (rebranding F5-LEVE, política do dono):
 * cliente NUNCA vê stack interno (nome do motor "YOLO26 ..." / framework
 * YOLOX/RF-DETR). `display_name` (migration 129, `public.trained_models`) é
 * atribuído manualmente — nunca inferido do `name` interno nem computado a
 * partir da versão. Vazio = "Logikos" (ninguém rebatizou ainda).
 *
 * Nome interno (`name`) e `framework` seguem existindo no payload — só para
 * superadmin exibir (telas que fazem essa distinção decidem no call site).
 */
export const NOME_PADRAO_CLIENTE = 'Logikos'

export function nomeParaCliente(m: { display_name?: string | null }): string {
  return m.display_name?.trim() || NOME_PADRAO_CLIENTE
}

/**
 * Rótulo de modelo para QUALQUER superfície com dropdown/lista (option, select,
 * card): superadmin vê o nome interno cru (fallback "Modelo <id curto>"),
 * qualquer outro papel vê `nomeParaCliente`. Função única de propósito — achado
 * na prova DEV (2026-08-30): uma tela nova (`app/epi/Cameras.tsx` AbaEscopo)
 * copiou a UI de `CameraModelScope` sem essa regra, e o vazamento voltou por
 * uma superfície não coberta pelos testes. Todo novo dropdown de modelo DEVE
 * chamar esta função, nunca `m.name` cru.
 */
export function nomeInternoOuCliente(
  m: { id: string; name?: string | null; display_name?: string | null },
  isSuperAdmin: boolean,
): string {
  if (isSuperAdmin) return m.name || `Modelo ${m.id.slice(0, 8)}`
  return nomeParaCliente(m)
}
