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
