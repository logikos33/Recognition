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
const Admin = lazy(() => import('./admin/Admin').then((m) => ({ default: m.Admin })))
const VisaoGeralAdmin = lazy(() => import('./admin/VisaoGeral').then((m) => ({ default: m.VisaoGeral })))
const DispositivosAdmin = lazy(() => import('./admin/Dispositivos').then((m) => ({ default: m.Dispositivos })))
const AuditoriaAdmin = lazy(() => import('./admin/Auditoria').then((m) => ({ default: m.Auditoria })))
const TenantsAdmin = lazy(() => import('./admin/Tenants').then((m) => ({ default: m.Tenants })))
const TenantDetalheAdmin = lazy(() => import('./admin/TenantDetalhe').then((m) => ({ default: m.TenantDetalhe })))
const UsuariosAdmin = lazy(() => import('./admin/Usuarios').then((m) => ({ default: m.Usuarios })))

/**
 * Prefixo do front novo enquanto os dois convivem. Sai no tombamento.
 *
 * As rotas abaixo são declaradas RELATIVAS de propósito: caminho relativo só
 * consegue existir DENTRO do prefixo, então nenhuma tela nova tem como cair em
 * cima do front antigo por descuido. Há teste que reprova caminho absoluto.
 */
export const PREFIXO_NOVO = '/novo'

/**
 * Endereço de uma tela do front novo. **Todo `<Link>`/`navigate` interno passa
 * por aqui.**
 *
 * Escrever `to="/epi/cameras"` direto não dá erro nenhum: leva o usuário para a
 * tela ANTIGA de mesmo endereço, calada, com a cara do produto velho. Foi o que
 * aconteceu em 10 lugares na primeira leva — e nenhum teste pegou, porque do
 * ponto de vista do React Router estava tudo certo. Há teste agora.
 */
export const rotaNova = (caminho: string) => PREFIXO_NOVO + caminho

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

  // F5 SR2 — Admin (`Admin Plataforma.dc.html`): layout com gate
  // `admin:panel` (superadmin-only) e lateral própria. Visão geral (PR-1),
  // Tenants/Detalhe com white-label e Usuários (PR-2), Dispositivos e
  // Auditoria (PR-3). Resta Links compartilhados (aguarda backend).
  <Route key="ad" path="admin" element={<Admin />}>
    <Route key="adi" index element={<VisaoGeralAdmin />} />
    <Route key="adt" path="tenants" element={<TenantsAdmin />} />
    <Route key="adtd" path="tenants/:tenantId" element={<TenantDetalheAdmin />} />
    <Route key="adu" path="usuarios" element={<UsuariosAdmin />} />
    <Route key="add" path="dispositivos" element={<DispositivosAdmin />} />
    <Route key="ada" path="auditoria" element={<AuditoriaAdmin />} />
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
