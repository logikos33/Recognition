/**
 * Rotas do front novo — as que montam o `Shell` Logikos Vision.
 *
 * FLIP (decisão do Vitor, 29/08): o front novo é agora o padrão. A
 * coexistência por prefixo (27/08→29/08) acabou — `PREFIXO_NOVO` virou
 * identidade e estas rotas respondem nos próprios endereços finais. O App
 * monta assim:
 *
 *     <Routes>
 *       {ROTAS_NOVAS_SEM_SHELL}
 *       <Route element={<Shell />}>{ROTAS_NOVAS}</Route>
 *       <Route path="/novo/*" element={<RedirecionaLegado />} />
 *       <Route path="*" element={<AppLayout><AppRoutes/></AppLayout>} />
 *     </Routes>
 *
 * A metade das telas que MUDOU de endereço (`/epi/alerts` → `/epi/eventos`)
 * ganhou redirect no bloco legado de `AppRoutes.tsx`. A metade que NÃO mudou
 * (`/epi/dashboard` continua `/epi/dashboard`) sombreia a entrada antiga — a
 * rota nova, por ser estática e vir antes do catch-all `*`, sempre vence. As
 * entradas antigas de mesmo endereço ficam mortas até a demolição do front
 * antigo (`docs/migration/MANIFESTO-FRONT-ANTIGO.md`).
 *
 * ⛔ Não registre aqui tela que ainda não existe. Rota apontando para
 * placeholder é tela inventada — e tela sem desenho não se inventa.
 */
import { lazy, type ReactElement } from 'react'
import { Navigate, Route } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

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
const Operacoes = lazy(() => import('./epi/Operacoes').then((m) => ({ default: m.Operacoes })))
const Qualidade = lazy(() => import('./qualidade/Qualidade').then((m) => ({ default: m.Qualidade })))
const GestaoQualidade = lazy(() => import('./qualidade/GestaoQualidade').then((m) => ({ default: m.GestaoQualidade })))
const RevisaoQualidade = lazy(() => import('./qualidade/RevisaoQualidade').then((m) => ({ default: m.RevisaoQualidade })))
const ConfigQualidade = lazy(() => import('./qualidade/ConfigQualidade').then((m) => ({ default: m.ConfigQualidade })))
const Carga = lazy(() => import('./carga/Carga').then((m) => ({ default: m.Carga })))
const Modulos = lazy(() => import('./modulos/Modulos').then((m) => ({ default: m.Modulos })))
const Estudio = lazy(() => import('./estudio/Estudio').then((m) => ({ default: m.Estudio })))
const DadosEstudio = lazy(() => import('./estudio/Dados').then((m) => ({ default: m.Dados })))
const CoberturaEstudio = lazy(() => import('./estudio/Cobertura').then((m) => ({ default: m.Cobertura })))
const ClassificarEstudio = lazy(() => import('./estudio/Classificar').then((m) => ({ default: m.Classificar })))
const ClassesEstudio = lazy(() => import('./estudio/Classes').then((m) => ({ default: m.Classes })))
const ModeloEstudio = lazy(() => import('./estudio/Modelo').then((m) => ({ default: m.Modelo })))
const ModelosPorCameraEstudio = lazy(() =>
  import('./estudio/ModelosPorCamera').then((m) => ({ default: m.ModelosPorCamera })),
)
const TreinoEstudio = lazy(() => import('./estudio/Treino').then((m) => ({ default: m.Treino })))

/**
 * Prefixo do front novo. Era `/novo` durante a coexistência; no flip (29/08)
 * virou identidade — as rotas abaixo, declaradas relativas, resolvem direto
 * para o endereço final (`epi/dashboard` → `/epi/dashboard`).
 *
 * `PREFIXO_LEGADO` guarda o valor antigo só para redirecionar quem tinha
 * `/novo/...` salvo (favorito, link enviado) — ver `RedirecionaLegado` em
 * `App.tsx`.
 */
export const PREFIXO_NOVO = ''

/** Prefixo do front novo ANTES do flip. Só usado para o redirect de `/novo/*`. */
export const PREFIXO_LEGADO = '/novo'

/**
 * Endereço de uma tela do front novo. **Todo `<Link>`/`navigate` interno passa
 * por aqui.**
 *
 * Hoje `rotaNova()` é identidade (`PREFIXO_NOVO === ''`), mas continua
 * obrigatória: é o único ponto que muda se um prefixo voltar a existir, e o
 * teste de coexistência reprova `to="/..."` literal em `app/` — só passa por
 * `rotaNova()`.
 */
export const rotaNova = (caminho: string) => PREFIXO_NOVO + caminho

/**
 * Índice de `ROTAS_NOVAS` (`/`) — mesma lógica de `RootRedirect` em
 * `AppRoutes.tsx`: superadmin cai no admin (front antigo, não migrado),
 * os demais perfis caem no dashboard do EPI.
 */
function RaizRotasNovas() {
  const { isSuperAdmin } = useAuth()
  return <Navigate to={isSuperAdmin ? '/admin' : 'epi/dashboard'} replace />
}

/**
 * As telas entram aqui conforme forem migradas E PROVADAS, uma por uma.
 * Lista vazia = o front novo ainda não serve rota nenhuma, e o antigo atende
 * tudo. É o estado honesto até a primeira tela ficar de pé.
 */
export const ROTAS_NOVAS: ReactElement[] = [
  <Route key="i" index element={<RaizRotasNovas />} />,

  // EPI, na ordem da jornada mestra: DETECTAR → TRIAR → AGIR → PROVAR.
  <Route key="d" path="epi/dashboard" element={<Dashboard />} />,
  <Route key="v" path="epi/live" element={<AoVivo />} />,
  <Route key="e" path="epi/eventos" element={<Eventos />} />,
  <Route key="ed" path="epi/eventos/:id" element={<EventoDetalhe />} />,
  <Route key="vf" path="epi/verificacao" element={<Verificacao />} />,
  <Route key="a" path="epi/acoes" element={<Acoes />} />,
  <Route key="c" path="epi/cameras" element={<Cameras />} />,
  <Route key="op" path="epi/cameras/:cameraId/operations" element={<Operacoes />} />,
  <Route key="r" path="epi/relatorios" element={<Relatorios />} />,

  // F4 — Qualidade e Carga. O de-para do delta manda `/quality/*` e `/carga/*`.
  <Route key="q" path="quality" element={<Qualidade />} />,
  <Route key="qg" path="quality/gestao" element={<GestaoQualidade />} />,
  <Route key="qr" path="quality/revisao" element={<RevisaoQualidade />} />,
  <Route key="qc" path="quality/configuracao" element={<ConfigQualidade />} />,
  <Route key="ca" path="carga" element={<Carga />} />,

  // F5 — Estúdio (`Estúdio.dc.html`): de-para do delta manda `/estudio/*`.
  // Layout com gate `frames:annotate` e lateral própria; sub-rota só quando a
  // tela EXISTE (IA/Dataset/Treinos/Modelos chegam nas PRs seguintes).
  <Route key="es" path="estudio" element={<Estudio />}>
    <Route key="esi" index element={<Navigate to="dados" replace />} />
    <Route key="esd" path="dados" element={<DadosEstudio />} />
    <Route key="esc" path="cobertura" element={<CoberturaEstudio />} />
    <Route key="escl" path="classificar" element={<ClassificarEstudio />} />
    <Route key="escls" path="classes" element={<ClassesEstudio />} />
    <Route key="esm" path="modelo" element={<ModeloEstudio />} />
    <Route key="esmc" path="modelos-por-camera" element={<ModelosPorCameraEstudio />} />
    <Route key="est" path="treino" element={<TreinoEstudio />} />
  </Route>,
]

/**
 * Rotas do front novo que NÃO usam o Shell.
 *
 * A escolha de módulo tem cabeçalho próprio e nenhuma navegação lateral — ela é
 * anterior a escolher onde navegar. Montá-la dentro do Shell mostraria o menu do
 * EPI para quem ainda não disse que vai trabalhar no EPI.
 */
export const ROTAS_NOVAS_SEM_SHELL: ReactElement[] = [
  <Route key="mod" path={`${PREFIXO_NOVO}/modules`} element={<Modulos />} />,
]
