/**
 * Nome de modelo voltado ao cliente (rebranding F5-LEVE, política do dono):
 * cliente NUNCA vê stack interno (nome do motor "YOLO26 ..." / framework
 * YOLOX/RF-DETR). `display_name` (migration 129, `public.trained_models`) é
 * hoje CALCULADO na criação do modelo ("Logikos V<n> · DD/MM" — ver
 * `training.py:_build_display_name`), nunca o `name` interno cru.
 *
 * ADR-0070 corrige a política que este comentário descrevia antes ("nunca
 * inferido... não existe V<n> calculado" — o oposto do código real): o nome
 * calculado é um RÓTULO DE EXIBIÇÃO, não versão semântica ("V3" não afirma
 * que é melhor que "V2"). Nome atribuído por humano, quando essa rota
 * existir, sempre vence o calculado, e os dois precisam ser visualmente
 * distinguíveis — pendente de mecanismo no backend (ver ADR-0070).
 * Vazio = "Logikos" (nenhum modelo calculado ainda, ex.: registros
 * anteriores à migration 129).
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
