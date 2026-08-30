/**
 * ⚠️ SUPERADA — esta tela tem substituta no front novo.
 *
 * @migrado-para src/app/epi/Eventos.tsx
 * rota nova: /novo/epi/eventos
 *
 * Paridade fechada em 30/08/2026: coluna de confiança → PR #581; janela de
 * datas livre → refutada na lista final do PARIDADE doc (período + deep-link
 * cobrem). §6 (taxa de uso por área) ADIADO por decisão de 30/08 — repor na
 * semana de 07/09; ver "Atualização 30/08" em
 * docs/migration/PARIDADE-ANTIGO-VS-NOVO.md.
 *
 * Continua VIVA e servindo a rota antiga: os dois fronts convivem até a
 * migração terminar (decisão do Vitor, 27/08). Não apague nesta rodada.
 *
 * Na rodada de remoção, ANTES de apagar: a substituta foi provada renderizando
 * com dado real no DEV, mas paridade de FUNCIONALIDADE não foi conferida item a
 * item. Compare as duas telas primeiro — e confira quem mais importa deste
 * arquivo (componentes e estilos só dele saem junto; os compartilhados, não).
 * A lista está em docs/migration/MANIFESTO-FRONT-ANTIGO.md.
 */
/**
 * EpiAlerts — wrapper de AlertsHistoryPage para o módulo EPI.
 */
import { AlertsHistoryPage } from '../AlertsHistoryPage'

export function EpiAlerts() {
  return <AlertsHistoryPage />
}

export default EpiAlerts
