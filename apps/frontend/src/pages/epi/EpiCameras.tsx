/**
 * ⚠️ SUPERADA — esta tela tem substituta no front novo.
 *
 * @migrado-para src/app/epi/Cameras.tsx
 * rota nova: /novo/epi/cameras
 *
 * Paridade fechada em 30/08/2026: FPS/qualidade/coleta de treino/telemetria →
 * PR #576 (5ª aba "Desempenho"); fabricante no detalhe → #581. §7 (modelo por
 * câmera: reverter ao padrão + precisão no seletor) ADIADO por decisão de
 * 30/08 — repor na semana de 07/09 (a atribuição em si já existe na aba
 * Escopo). Ver "Atualização 30/08" em
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
 * EpiCameras — wrapper de CamerasPage para o módulo EPI.
 */
import { CamerasPage } from '../CamerasPage'

export function EpiCameras() {
  return <CamerasPage />
}

export default EpiCameras
