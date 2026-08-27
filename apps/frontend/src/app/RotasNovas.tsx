/**
 * Rotas do front novo — as que montam o `Shell` Logikos Vision.
 *
 * COEXISTÊNCIA (decisão do Vitor, 27/08): estas rotas correm ao lado do front
 * antigo, que segue inteiro e de pé. O App monta assim:
 *
 *     <Routes>
 *       <Route path={PREFIXO_NOVO} element={<Shell />}>{ROTAS_NOVAS}</Route>
 *       <Route path="*" element={<AppLayout><AppRoutes/></AppLayout>} />
 *     </Routes>
 *
 * POR QUE UM PREFIXO, e não os caminhos do desenho direto:
 *
 * Metade das telas novas MUDA de endereço (`/epi/alerts` → `/epi/eventos`) e a
 * outra metade NÃO (`/epi/dashboard` continua `/epi/dashboard`). Sem prefixo, as
 * que não mudam colidiriam de frente com o front antigo, e a mesma URL teria de
 * servir duas telas — o que "coexistir" justamente não é. Com prefixo, cada
 * front tem endereço próprio, o antigo não muda de comportamento em nada, e o
 * tombamento vira uma operação pequena e reversível: tirar o prefixo e trocar
 * as rotas antigas por redirects (de-para em `docs/migration/DELTA-PRE-MIGRACAO.md`).
 *
 * ⛔ Não registre aqui tela que ainda não existe. Rota apontando para
 * placeholder é tela inventada — e tela sem desenho não se inventa.
 */
import { lazy, type ReactElement } from 'react'
import { Navigate, Route } from 'react-router-dom'

/**
 * Cada tela em seu próprio pedaço, como o front antigo já faz. Importadas de
 * forma estática, as 8 telas EPI entram no bundle de entrada e são baixadas por
 * quem só vai abrir uma — numa operação que roda em tablet de chão de fábrica,
 * isso é tempo de carregamento cobrado de todo mundo.
 */
const Acoes = lazy(() => import('./epi/Acoes').then((m) => ({ default: m.Acoes })))
const AoVivo = lazy(() => import('./epi/AoVivo').then((m) => ({ default: m.AoVivo })))
const Cameras = lazy(() => import('./epi/Cameras').then((m) => ({ default: m.Cameras })))
const Dashboard = lazy(() => import('./epi/Dashboard').then((m) => ({ default: m.Dashboard })))
const EventoDetalhe = lazy(() => import('./epi/EventoDetalhe').then((m) => ({ default: m.EventoDetalhe })))
const Eventos = lazy(() => import('./epi/Eventos').then((m) => ({ default: m.Eventos })))
const Relatorios = lazy(() => import('./epi/Relatorios').then((m) => ({ default: m.Relatorios })))
const Verificacao = lazy(() => import('./epi/Verificacao').then((m) => ({ default: m.Verificacao })))

/**
 * Prefixo do front novo enquanto os dois convivem. Sai no tombamento.
 *
 * As rotas abaixo são declaradas RELATIVAS de propósito: caminho relativo só
 * consegue existir DENTRO do prefixo, então nenhuma tela nova tem como cair em
 * cima do front antigo por descuido. Há teste que reprova caminho absoluto.
 */
export const PREFIXO_NOVO = '/novo'

/**
 * As telas entram aqui conforme forem migradas E PROVADAS, uma por uma.
 * Lista vazia = o front novo ainda não serve rota nenhuma, e o antigo atende
 * tudo. É o estado honesto até a primeira tela ficar de pé.
 */
export const ROTAS_NOVAS: ReactElement[] = [
  <Route key="i" index element={<Navigate to="epi/dashboard" replace />} />,

  // EPI, na ordem da jornada mestra: DETECTAR → TRIAR → AGIR → PROVAR.
  <Route key="d" path="epi/dashboard" element={<Dashboard />} />,
  <Route key="v" path="epi/live" element={<AoVivo />} />,
  <Route key="e" path="epi/eventos" element={<Eventos />} />,
  <Route key="ed" path="epi/eventos/:id" element={<EventoDetalhe />} />,
  <Route key="vf" path="epi/verificacao" element={<Verificacao />} />,
  <Route key="a" path="epi/acoes" element={<Acoes />} />,
  <Route key="c" path="epi/cameras" element={<Cameras />} />,
  <Route key="r" path="epi/relatorios" element={<Relatorios />} />,
]
