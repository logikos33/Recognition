/**
 * ⚠️ SUPERADA — esta tela tem substituta no front novo.
 *
 * @migrado-para src/app/epi/Eventos.tsx
 * rota nova: /novo/epi/eventos
 *
 * @paridade-pendente taxa de uso por área; janela de datas livre; coluna de confiança
 *
 * ⛔ NÃO APAGUE: a substituta existe, mas NÃO faz tudo o que esta faz. A lista
 * completa e verificada está em docs/migration/PARIDADE-ANTIGO-VS-NOVO.md.
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
