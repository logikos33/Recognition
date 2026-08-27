/**
 * ⚠️ SUPERADA — esta tela tem substituta no front novo.
 *
 * @migrado-para src/app/epi/Cameras.tsx
 * rota nova: /novo/epi/cameras
 *
 * @paridade-pendente FPS/qualidade por câmera; qualidade da coleta de treino; modelo por módulo; telemetria
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
 * EpiCameras — wrapper de CamerasPage para o módulo EPI.
 */
import { CamerasPage } from '../CamerasPage'

export function EpiCameras() {
  return <CamerasPage />
}

export default EpiCameras
