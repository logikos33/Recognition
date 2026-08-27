/**
 * EPI Câmeras & Sites — `/epi/cameras` (F3 da migração).
 *
 * Desenho: `EPI Câmeras.dc.html`. Ele manda: título "Câmeras & Sites", barra de
 * abas, CTA "Adicionar câmera", split lista(330)+detalhe, prévia 16:9, cinco
 * campos, painel "TESTE DE CONEXÃO · PASSO A PASSO", aba Sites (modo do site +
 * saúde do Jetson + sincronização) e aba Saúde (tabela por câmera).
 *
 * ── ABA "ESCOPO" (delta §2 item 8) ──────────────────────────────────────────
 * O handoff NÃO desenhou esta aba — ela é o `CameraModelScope` que a develop
 * ganhou depois do snapshot do design, e o `DELTA-PRE-MIGRACAO.md` a endereça
 * explicitamente a esta tela ("implementar-na-migração (F3 Câmeras)"). Ela
 * entra como QUARTA aba da barra que o desenho já prevê — a barra é uma lista
 * (`{{ abas }}`), não três botões fixos; então isto estende o desenho, não
 * inventa uma seção nova. O contrato duramente conquistado NÃO foi copiado:
 * `classesDoModelo`, `moduloDaCamera` e `montarConfig` são importados do
 * componente original, inclusive a rota EM LOTE (`GET
 * /cameras/model-config?module=<m>`, uma chamada por MÓDULO e não por câmera —
 * a versão por câmera estourava o pool da API nas 28 câmeras da RVB).
 *
 * ── MULTI-TENANCY ───────────────────────────────────────────────────────────
 * Nada aqui escolhe schema. `cameraService`/`edgeService` chamam as MESMAS
 * rotas que o front atual chama, e é o backend que decide `public.cameras`
 * (com `tenant_id`) ou `{tenant_schema}.cameras` (sem) por rota. Cross-tenant
 * volta 404 (C-01) e cai no estado de erro com "tentar de novo".
 *
 * ── PERMISSÕES (as reais de `core/permissions.py`) ──────────────────────────
 *   cameras:read       ler a tela (já é o gate da rota na nav)
 *   cameras:write      Adicionar câmera · Editar · Arquivar/Desarquivar
 *   cameras:test       Testar conexão
 *   cameras:control    Iniciar/Parar monitoramento
 *   cameras:configure  modo de processamento do site · salvar escopo
 * `cameras:delete` não é usado de propósito: `DELETE /cameras/<id>` apaga em
 * cascata frames e anotações — a UI arquiva (reversível), nunca apaga.
 *
 * ── PARA O DESIGN (o que o desenho não cobre e ficou no mínimo da identidade)
 *  1. Ações do detalhe (Editar · Iniciar/Parar · Operações · Cenário ·
 *     Arquivar): o desenho só desenhou "Testar conexão", mas isto é CRUD real
 *     do front atual e a rota `/epi/cameras` é a MESMA nos dois fronts — sem
 *     estas ações elas somem do produto. Linha única de botões secundários.
 *  2. Cadastro/edição de câmera: sem tela no handoff. Reusa os wizards atuais
 *     (`CameraOnboardingWizard`/`CameraWizard`) — inventar um fluxo de cadastro
 *     sem desenho seria pior que reusar o que já funciona.
 *  3. "UPTIME 7D" (aba Saúde): NÃO existe endpoint de uptime por câmera. Fica
 *     "—". Uptime existe por SITE (`heartbeat-summary`), não por câmera.
 *  4. "FPS" (aba Saúde) virou "FPS ALVO": o que a API dá por câmera é
 *     `fps_target` (configurado), não FPS medido. Chamar de "FPS" mentiria.
 *  5. "FILA 0" e "Reiniciar agente" (aba Sites): sem fonte. `queue_depth` vem
 *     do backend mas o adaptador do `edgeService` não o expõe, e não há rota de
 *     reinício do agente. Botão morto é pior que botão ausente.
 *  6. "ms" por passo do teste de conexão: `TestResult.checks` não traz tempo.
 *  7. Prévia: usa o snapshot de triagem (`/cameras/<id>/snapshot`), que não
 *     acende a câmera. Vídeo ao vivo é a tela Ao Vivo.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CircleAlert,
  CircleCheck,
  CircleSlash,
  Frame,
  Pencil,
  Play,
  Plug,
  Plus,
  RefreshCw,
  Settings2,
  Square,
  TriangleAlert,
  Video,
  type LucideIcon,
} from 'lucide-react'

import { ConfirmDialog } from '../../components/ui/ConfirmDialog/ConfirmDialog'
import { CameraOnboardingWizard } from '../../components/cameras/CameraOnboardingWizard'
import { CameraWizard } from '../../components/cameras/CameraWizard'
import {
  classesDoModelo,
  moduloDaCamera,
  montarConfig,
  type ModelDeployment,
  type RegistryModel,
} from '../../components/training/CameraModelScope'
import { useAuth } from '../../hooks/useAuth'
import { useCameraSnapshot } from '../../hooks/useCameraSnapshot'
import { api } from '../../services/api'
import { cameraService, type TestResult } from '../../services/cameraService'
import { edgeService } from '../../services/edgeService'
import type { Camera } from '../../types'
import {
  DEPLOYMENT_MODE_LABELS,
  type DeploymentMode,
  type EdgeSite,
  type SiteHealth,
  type SiteStatus,
} from '../../types/edge'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './Cameras.css'

type Aba = 'cameras' | 'sites' | 'saude' | 'escopo'

const ABAS: Array<{ id: Aba; rotulo: string }> = [
  { id: 'cameras', rotulo: 'Câmeras' },
  { id: 'sites', rotulo: 'Sites' },
  { id: 'saude', rotulo: 'Saúde' },
  { id: 'escopo', rotulo: 'Escopo' },
]

/** Estado = cor + ícone + palavra. Nunca só a cor: quem não distingue verde de
 * vermelho tem de conseguir operar a tela. */
interface Estado {
  tom: 'ok' | 'atencao' | 'nc' | 'neutro'
  palavra: string
  Icone: LucideIcon
}

export function estadoDaCamera(cam: Pick<Camera, 'is_active' | 'stream_status'>): Estado {
  if (cam.is_active === false) return { tom: 'neutro', palavra: 'ARQUIVADA', Icone: CircleSlash }
  const st = (cam.stream_status ?? '').toLowerCase()
  if (st === 'active' || st === 'online') return { tom: 'ok', palavra: 'ONLINE', Icone: CircleCheck }
  if (st === 'error') return { tom: 'nc', palavra: 'FALHA', Icone: CircleAlert }
  return { tom: 'atencao', palavra: 'PARADA', Icone: TriangleAlert }
}

const ESTADO_SITE: Record<SiteStatus, Estado> = {
  healthy: { tom: 'ok', palavra: 'EDGE SAUDÁVEL', Icone: CircleCheck },
  degraded: { tom: 'atencao', palavra: 'EDGE DEGRADADO', Icone: TriangleAlert },
  critical: { tom: 'nc', palavra: 'EDGE CRÍTICO', Icone: CircleAlert },
  offline: { tom: 'nc', palavra: 'EDGE OFFLINE', Icone: CircleSlash },
}

const MODO_DESCRICAO: Record<DeploymentMode, string> = {
  edge: 'A detecção roda no equipamento do site. A nuvem recebe evento e evidência.',
  hybrid: 'O site detecta e a nuvem também processa — modo de transição.',
  cloud: 'O vídeo sobe para a nuvem, que detecta. Sem equipamento no site.',
}

/** Passos do teste, na ordem em que o backend os executa (`TestResult.checks`). */
const PASSOS: Array<[keyof TestResult['checks'], string]> = [
  ['url_format', 'Formato do endereço'],
  ['host_reachable', 'Equipamento respondeu'],
  ['port_open', 'Porta aberta'],
  ['rtsp_response', 'Handshake RTSP'],
  ['stream_available', 'Vídeo disponível'],
]

const MARCA_PASSO: Record<string, string> = { ok: '✓', error: '✗', warning: '!', pending: '·' }
const TOM_PASSO: Record<string, Estado['tom']> = {
  ok: 'ok',
  error: 'nc',
  warning: 'atencao',
  pending: 'neutro',
}

function haQuanto(iso: string | null | undefined): string {
  if (!iso) return '—'
  const ms = Date.now() - new Date(iso).getTime()
  if (!Number.isFinite(ms) || ms < 0) return '—'
  const seg = Math.floor(ms / 1000)
  if (seg < 60) return `HÁ ${seg} S`
  const min = Math.floor(seg / 60)
  if (min < 60) return `HÁ ${min} MIN`
  const hor = Math.floor(min / 60)
  if (hor < 24) return `HÁ ${hor} H`
  return `HÁ ${Math.floor(hor / 24)} D`
}

/** Endereço sempre com a senha oculta — a API nunca devolve a senha, e a tela
 * não pode dar a impressão de que devolveria. */
function enderecoMascarado(cam: Camera): string {
  const base = `${cam.host || '...'}:${cam.port || 554}`
  return cam.username ? `rtsp://${cam.username}:****@${base}/…` : `rtsp://${base}/…`
}

function numero(v: number | null | undefined, sufixo = ''): string {
  return v === null || v === undefined ? '—' : `${v}${sufixo}`
}

// ── prévia ───────────────────────────────────────────────────────────────────

/** Prévia 16:9. Usa o snapshot de triagem — NÃO acende a câmera nem abre HLS.
 * `key={cameraId}` no chamador: o hook dispara uma vez por ativação. */
function Previa({ cameraId }: { cameraId: string }) {
  const { url, loading } = useCameraSnapshot(cameraId, true)
  if (url) return <img className={s.previaImagem} src={url} alt="Última imagem capturada da câmera" />
  return (
    <LogikosLoader
      variante="tile"
      estado={loading ? 'waiting' : 'idle'}
      rotulo={loading ? 'BUSCANDO IMAGEM' : 'SEM SINAL'}
      tamanho={36}
    />
  )
}

// ── escopo por câmera (delta §2 item 8) ──────────────────────────────────────

interface Envelope<T> { success: boolean; message?: string; data?: T }
interface ModelDetail {
  model: RegistryModel
  lineage: { dataset_version: { class_distribution?: Record<string, unknown> } | null }
}
interface Rascunho { modelId: string; classes: string[] }

function rascunhoDo(dep: ModelDeployment | undefined): Rascunho {
  if (!dep) return { modelId: '', classes: [] }
  const classes = dep.config?.classes
  return { modelId: dep.model_id, classes: Array.isArray(classes) ? classes : [] }
}

function mesmoConjunto(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((x) => b.includes(x))
}

interface EscopoProps {
  cameras: Camera[]
  podeEditar: boolean
}

function AbaEscopo({ cameras, podeEditar }: EscopoProps) {
  const ativas = useMemo(() => cameras.filter((c) => c.is_active !== false), [cameras])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [modelos, setModelos] = useState<RegistryModel[]>([])
  const [classesPorModelo, setClassesPorModelo] = useState<Record<string, string[]>>({})
  const [deployPorCamera, setDeployPorCamera] = useState<Record<string, ModelDeployment>>({})
  const [rascunhos, setRascunhos] = useState<Record<string, Rascunho>>({})
  const [salvando, setSalvando] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const listagem = await api.get<Envelope<{ models: RegistryModel[] }>>('/v1/models')
      const comArtefato = (listagem.data?.models ?? []).filter((m) => !!m.r2_onnx_key)
      // Uma chamada por MÓDULO distinto (hoje 1), NUNCA uma por câmera: a
      // versão por câmera estourava o pool de conexões da API nas 28 da RVB.
      const modulos = [...new Set(ativas.map(moduloDaCamera))]
      const [detalhes, porModulo] = await Promise.all([
        Promise.allSettled(comArtefato.map((m) => api.get<Envelope<ModelDetail>>(`/v1/models/${m.id}`))),
        Promise.all(
          modulos.map((m) =>
            api.get<Envelope<{ deployments: Record<string, ModelDeployment> }>>(
              `/cameras/model-config?module=${encodeURIComponent(m)}`,
            ),
          ),
        ),
      ])
      const porModelo: Record<string, string[]> = {}
      detalhes.forEach((r, i) => {
        const d = r.status === 'fulfilled' ? r.value.data : undefined
        // Sem catálogo de fallback: classe que o modelo não declara não é
        // inventada aqui — a tela diz que o modelo não declarou classes.
        porModelo[comArtefato[i].id] = classesDoModelo(d?.lineage?.dataset_version?.class_distribution, [])
      })
      const porCamera: Record<string, ModelDeployment> = {}
      porModulo.forEach((r, i) => {
        // Só a câmera CUJO módulo é este: uma câmera de 'quality' não herda o
        // deployment 'epi' de outra só porque veio no mesmo lote.
        const doModulo = new Set(ativas.filter((c) => moduloDaCamera(c) === modulos[i]).map((c) => c.id))
        for (const [cameraId, dep] of Object.entries(r.data?.deployments ?? {})) {
          if (dep && doModulo.has(cameraId)) porCamera[cameraId] = dep
        }
      })
      setModelos(comArtefato)
      setClassesPorModelo(porModelo)
      setDeployPorCamera(porCamera)
      setRascunhos(Object.fromEntries(ativas.map((c) => [c.id, rascunhoDo(porCamera[c.id])])))
    } catch (err) {
      // Sem isto a tabela caía no vazio e afirmava "nenhuma câmera" — falso
      // num tenant de 28 câmeras, e sem como tentar de novo.
      setErro(err instanceof Error ? err.message : 'Erro ao carregar o escopo por câmera')
    } finally {
      setCarregando(false)
    }
  }, [ativas])

  useEffect(() => { void carregar() }, [carregar])

  const mudar = (camId: string, patch: Partial<Rascunho>) =>
    setRascunhos((prev) => ({ ...prev, [camId]: { ...prev[camId], ...patch } }))

  async function salvar(cam: Camera) {
    const rascunho = rascunhos[cam.id]
    if (!podeEditar || !rascunho?.modelId || rascunho.classes.length === 0) return
    setSalvando(cam.id)
    try {
      const res = await api.post<Envelope<{ deployment: ModelDeployment }>>(
        `/cameras/${cam.id}/model-config`,
        {
          model_id: rascunho.modelId,
          module_code: moduloDaCamera(cam),
          config: montarConfig(deployPorCamera[cam.id]?.config, rascunho.classes),
        },
      )
      const novo = res.data?.deployment
      if (novo) {
        setDeployPorCamera((prev) => ({ ...prev, [cam.id]: novo }))
        mudar(cam.id, rascunhoDo(novo))
      }
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao salvar o escopo')
    } finally {
      setSalvando(null)
    }
  }

  if (carregando) return <LogikosLoader variante="tile" estado="waiting" rotulo="CARREGANDO ESCOPO" tamanho={48} />

  if (erro) {
    return (
      <div className={s.centro}>
        <CircleAlert size={36} strokeWidth={1.7} className={s.tom.nc} />
        <span className={s.centroTitulo}>Não foi possível carregar o escopo</span>
        <span className={s.centroMono}>{erro}</span>
        <span className={s.centroTexto}>Isto NÃO quer dizer &quot;nenhuma câmera&quot;.</span>
        <button className={s.botaoPrimario} onClick={() => { void carregar() }}>Tentar novamente</button>
      </div>
    )
  }

  return (
    <div className={s.pagina}>
      <p className={s.nota}>
        Modelo e classes que valem em cada câmera. Câmera sem modelo cai no detector padrão do
        ambiente — não há como desativar por aqui, só trocar. O escopo vale hoje no shadow e no
        worker da nuvem; o box edge ainda não recebe classe por câmera (issue 519).
        {!podeEditar && ' Você tem acesso somente de leitura (requer cameras:configure).'}
      </p>
      <table className={s.tabela}>
        <thead>
          <tr>
            <th className={s.th}>Câmera</th>
            <th className={s.th}>Modelo</th>
            <th className={s.th}>Classes no escopo</th>
            <th className={s.th}>Último deploy</th>
            <th className={s.th} />
          </tr>
        </thead>
        <tbody>
          {ativas.map((cam) => {
            const rascunho = rascunhos[cam.id] ?? { modelId: '', classes: [] }
            const dep = deployPorCamera[cam.id]
            const modulo = moduloDaCamera(cam)
            const doModulo = modelos.filter((m) => (m.module_code || 'epi') === modulo)
            const todas = rascunho.modelId ? classesPorModelo[rascunho.modelId] ?? [] : []
            const base = rascunhoDo(dep)
            const mudou =
              rascunho.modelId !== base.modelId || !mesmoConjunto(rascunho.classes, base.classes)
            const podeSalvar =
              podeEditar && salvando !== cam.id && mudou && !!rascunho.modelId && rascunho.classes.length > 0
            return (
              <tr key={cam.id}>
                <td className={s.tdNome}>{cam.name}</td>
                <td className={s.td}>
                  <select
                    className={s.seletor}
                    aria-label={`Modelo da câmera ${cam.name}`}
                    value={rascunho.modelId}
                    disabled={!podeEditar || salvando === cam.id}
                    onChange={(e) => {
                      const id = e.target.value
                      mudar(cam.id, { modelId: id, classes: id ? [...(classesPorModelo[id] ?? [])] : [] })
                    }}
                  >
                    <option value="" disabled={!!dep}>— sem modelo (detector padrão)</option>
                    {doModulo.map((m) => (
                      <option key={m.id} value={m.id}>{m.name || `Modelo ${m.id.slice(0, 8)}`}</option>
                    ))}
                  </select>
                </td>
                <td className={s.td}>
                  {rascunho.modelId ? (
                    <div className={s.classes}>
                      {todas.map((cls) => {
                        const marcada = rascunho.classes.includes(cls)
                        return (
                          <label key={cls} className={s.classe}>
                            <input
                              type="checkbox"
                              aria-label={`Classe ${cls} em ${cam.name}`}
                              checked={marcada}
                              disabled={!podeEditar || salvando === cam.id}
                              onChange={() =>
                                mudar(cam.id, {
                                  classes: marcada
                                    ? rascunho.classes.filter((c) => c !== cls)
                                    : [...rascunho.classes, cls],
                                })
                              }
                            />
                            {cls}
                          </label>
                        )
                      })}
                      {todas.length === 0 && (
                        <span className={s.tom.atencao}>Este modelo não declara classes.</span>
                      )}
                      {todas.length > 0 && rascunho.classes.length === 0 && (
                        <span className={s.tom.atencao}>marque ≥1 classe</span>
                      )}
                    </div>
                  ) : (
                    <span className={s.rotulo}>—</span>
                  )}
                </td>
                <td className={s.td}>
                  {dep ? new Date(dep.created_at).toLocaleString('pt-BR') : '—'}
                </td>
                <td className={s.td}>
                  <button
                    className={s.botaoSecundario}
                    aria-label={`Salvar escopo de ${cam.name}`}
                    disabled={!podeSalvar}
                    onClick={() => { void salvar(cam) }}
                  >
                    {salvando === cam.id ? 'Salvando…' : 'Salvar'}
                  </button>
                </td>
              </tr>
            )
          })}
          {ativas.length === 0 && (
            <tr><td className={s.td} colSpan={5}>Nenhuma câmera ativa no tenant.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── tela ─────────────────────────────────────────────────────────────────────

export function Cameras() {
  const { can } = useAuth()
  const navegar = useNavigate()

  const podeCadastrar = can('cameras:write')
  const podeTestar = can('cameras:test')
  const podeControlar = can('cameras:control')
  const podeConfigurar = can('cameras:configure')

  const [aba, setAba] = useState<Aba>('cameras')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [sites, setSites] = useState<EdgeSite[]>([])
  const [saudeSites, setSaudeSites] = useState<SiteHealth[]>([])
  const [erroSites, setErroSites] = useState<string | null>(null)
  const [selecionadaId, setSelecionadaId] = useState<string | null>(null)

  const [testando, setTestando] = useState(false)
  const [teste, setTeste] = useState<TestResult | null>(null)
  const [erroTeste, setErroTeste] = useState<string | null>(null)

  const [cadastroAberto, setCadastroAberto] = useState(false)
  const [editando, setEditando] = useState<Camera | undefined>()
  const [confirmarArquivo, setConfirmarArquivo] = useState(false)
  const [arquivando, setArquivando] = useState(false)
  const [salvandoModo, setSalvandoModo] = useState(false)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const lista = await cameraService.list()
      setCameras(lista)
      setSelecionadaId((atual) =>
        atual && lista.some((c) => c.id === atual) ? atual : lista[0]?.id ?? null,
      )
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao carregar câmeras')
    } finally {
      setCarregando(false)
    }
    // Sites são de outro domínio e o backend só os libera a admin/superadmin:
    // um 403 aqui NÃO pode derrubar a lista de câmeras.
    const [lista, saude] = await Promise.allSettled([
      edgeService.listSites(),
      edgeService.getSitesHealth(),
    ])
    if (lista.status === 'fulfilled') setSites(lista.value)
    if (saude.status === 'fulfilled') setSaudeSites(saude.value)
    setErroSites(
      lista.status === 'rejected'
        ? lista.reason instanceof Error
          ? lista.reason.message
          : 'Não foi possível carregar os sites'
        : null,
    )
  }, [])

  useEffect(() => { void carregar() }, [carregar])

  const selecionada = useMemo(
    () => cameras.find((c) => c.id === selecionadaId) ?? null,
    [cameras, selecionadaId],
  )

  const nomeDoSite = useCallback(
    (siteId: string | null | undefined) => sites.find((st) => st.id === siteId)?.name ?? null,
    [sites],
  )

  function selecionar(id: string) {
    setSelecionadaId(id)
    setTeste(null)
    setErroTeste(null)
  }

  async function testarConexao() {
    if (!selecionada || !podeTestar) return
    setTestando(true)
    setTeste(null)
    setErroTeste(null)
    try {
      setTeste(await cameraService.test(selecionada.id))
    } catch (err) {
      setErroTeste(err instanceof Error ? err.message : 'Erro ao testar a conexão')
    } finally {
      setTestando(false)
    }
  }

  async function alternarMonitoramento() {
    if (!selecionada || !podeControlar) return
    const ligada = estadoDaCamera(selecionada).palavra === 'ONLINE'
    try {
      if (ligada) await cameraService.stop(selecionada.id)
      else await cameraService.start(selecionada.id)
      await carregar()
    } catch (err) {
      setErroTeste(err instanceof Error ? err.message : 'Erro ao alternar o monitoramento')
    }
  }

  async function arquivarOuRestaurar() {
    if (!selecionada || !podeCadastrar) return
    setArquivando(true)
    try {
      if (selecionada.is_active === false) await cameraService.restore(selecionada.id)
      else await cameraService.archive(selecionada.id)
      await carregar()
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao arquivar a câmera')
    } finally {
      setArquivando(false)
      setConfirmarArquivo(false)
    }
  }

  async function trocarModo(site: EdgeSite, modo: DeploymentMode) {
    if (!podeConfigurar || site.deployment_mode === modo) return
    setSalvandoModo(true)
    try {
      const atualizado = await edgeService.updateSite(site.id, { deployment_mode: modo })
      setSites((prev) => prev.map((st) => (st.id === atualizado.id ? atualizado : st)))
    } catch (err) {
      setErroSites(err instanceof Error ? err.message : 'Erro ao trocar o modo do site')
    } finally {
      setSalvandoModo(false)
    }
  }

  if (carregando) {
    return <LogikosLoader variante="fullscreen" estado="waiting" rotulo="CARREGANDO CÂMERAS" />
  }

  if (erro) {
    return (
      <div className={s.centro}>
        <CircleAlert size={36} strokeWidth={1.7} className={s.tom.nc} />
        <span className={s.centroTitulo}>Não foi possível carregar</span>
        <span className={s.centroMono}>GET /api/cameras · {erro}</span>
        <button className={s.botaoPrimario} onClick={() => { void carregar() }}>Tentar novamente</button>
      </div>
    )
  }

  const cabecalho = (
    <div className={s.cabecalho}>
      <h1 className={s.titulo}>Câmeras &amp; Sites</h1>
      <div className={s.abas} role="tablist" aria-label="Seções de câmeras e sites">
        {ABAS.map((a) => (
          <button
            key={a.id}
            role="tab"
            aria-selected={aba === a.id}
            className={aba === a.id ? s.aba.ativa : s.aba.inativa}
            onClick={() => setAba(a.id)}
          >
            {a.rotulo}
          </button>
        ))}
      </div>
      <span className={s.espacador} />
      <button className={s.botaoSecundario} onClick={() => { void carregar() }}>
        <RefreshCw size={14} strokeWidth={1.7} /> Atualizar
      </button>
      {podeCadastrar && (
        <button className={s.botaoPrimario} onClick={() => setCadastroAberto(true)}>
          <Plus size={15} strokeWidth={1.7} /> Adicionar câmera
        </button>
      )}
    </div>
  )

  const modais = (
    <>
      {cadastroAberto && (
        <CameraOnboardingWizard
          onComplete={() => { setCadastroAberto(false); void carregar() }}
          onCancel={() => setCadastroAberto(false)}
        />
      )}
      <CameraWizard
        isOpen={!!editando}
        onClose={() => setEditando(undefined)}
        onSuccess={() => { void carregar() }}
        camera={editando}
      />
      <ConfirmDialog
        open={confirmarArquivo}
        onClose={() => setConfirmarArquivo(false)}
        onConfirm={() => { void arquivarOuRestaurar() }}
        title="Arquivar câmera"
        description={`A câmera "${selecionada?.name}" sai do reconhecimento e do export de dataset. Os frames, anotações e detecções dela continuam no banco — nada é apagado, e dá para desarquivar depois.`}
        confirmLabel="Arquivar"
        variant="primary"
        loading={arquivando}
      />
    </>
  )

  if (cameras.length === 0) {
    return (
      <div className={s.pagina}>
        {cabecalho}
        <div className={s.centro}>
          <Video size={36} strokeWidth={1.7} className={s.rotulo} />
          <span className={s.centroTitulo}>Nenhuma câmera cadastrada</span>
          <span className={s.centroTexto}>
            Cadastre a primeira câmera do site para começar a detectar.
          </span>
          {podeCadastrar && (
            <button className={s.botaoPrimario} onClick={() => setCadastroAberto(true)}>
              <Plus size={15} strokeWidth={1.7} /> Adicionar câmera
            </button>
          )}
        </div>
        {modais}
      </div>
    )
  }

  return (
    <div className={s.pagina}>
      {cabecalho}

      {aba === 'cameras' && (
        <div className={s.split}>
          <div className={s.lista} role="list">
            {cameras.map((cam) => {
              const est = estadoDaCamera(cam)
              const ativa = cam.id === selecionadaId
              return (
                <button
                  key={cam.id}
                  role="listitem"
                  aria-current={ativa}
                  className={ativa ? s.item.ativo : s.item.inativo}
                  onClick={() => selecionar(cam.id)}
                >
                  <span className={s.itemTextos}>
                    <span className={s.itemNome}>{cam.name}</span>
                    <span className={s.itemArea}>{cam.location || 'Sem área definida'}</span>
                  </span>
                  <span className={`${s.itemEstado} ${s.tom[est.tom]}`}>
                    <est.Icone size={12} strokeWidth={1.7} aria-hidden="true" />
                    {est.palavra}
                  </span>
                </button>
              )
            })}
          </div>

          {selecionada && (
            <div className={s.cartao}>
              <div className={s.cartaoTopo}>
                <span className={s.cartaoNome}>{selecionada.name}</span>
                {(() => {
                  const est = estadoDaCamera(selecionada)
                  return (
                    <span className={`${s.estadoLinha} ${s.tom[est.tom]}`}>
                      <est.Icone size={13} strokeWidth={1.7} aria-hidden="true" />
                      {est.palavra}
                    </span>
                  )
                })()}
                <span className={s.espacador} />
                {podeTestar && (
                  <button className={s.botaoPrimario} disabled={testando} onClick={() => { void testarConexao() }}>
                    {testando
                      ? <LogikosLoader variante="spinner" estado="waiting" tamanho={16} />
                      : <Plug size={14} strokeWidth={1.7} />}
                    Testar conexão
                  </button>
                )}
              </div>

              <div className={s.corpoDetalhe}>
                <div className={s.previa}>
                  <Previa key={selecionada.id} cameraId={selecionada.id} />
                </div>
                <dl className={s.campos}>
                  <dt className={s.rotulo}>Site</dt>
                  <dd>{nomeDoSite(selecionada.site_id) ?? 'Sem site vinculado'}</dd>
                  <dt className={s.rotulo}>Área</dt>
                  <dd>{selecionada.location || '—'}</dd>
                  <dt className={s.rotulo}>Endereço</dt>
                  <dd className={s.valorMono}>
                    {enderecoMascarado(selecionada)} <span className={s.rotulo}>· senha oculta</span>
                  </dd>
                  <dt className={s.rotulo}>Processa em</dt>
                  <dd>
                    {(() => {
                      const site = sites.find((st) => st.id === selecionada.site_id)
                      if (!site) return '—'
                      return `${DEPLOYMENT_MODE_LABELS[site.deployment_mode]} · ${site.name}`
                    })()}
                  </dd>
                  <dt className={s.rotulo}>Cenário</dt>
                  <dd>{moduloDaCamera(selecionada).toUpperCase()}</dd>
                </dl>
              </div>

              {/* PARA O DESIGN (1): sem estas ações, o CRUD do front atual some
                  do produto — a rota `/epi/cameras` é a mesma nos dois fronts. */}
              <div className={s.acoes}>
                {podeCadastrar && (
                  <button className={s.botaoSecundario} onClick={() => setEditando(selecionada)}>
                    <Pencil size={13} strokeWidth={1.7} /> Editar
                  </button>
                )}
                {podeControlar && (
                  <button className={s.botaoSecundario} onClick={() => { void alternarMonitoramento() }}>
                    {estadoDaCamera(selecionada).palavra === 'ONLINE'
                      ? <><Square size={13} strokeWidth={1.7} /> Parar monitoramento</>
                      : <><Play size={13} strokeWidth={1.7} /> Iniciar monitoramento</>}
                  </button>
                )}
                <button
                  className={s.botaoSecundario}
                  onClick={() => navegar(`/epi/cameras/${selecionada.id}/operations`)}
                >
                  <Settings2 size={13} strokeWidth={1.7} /> Operações
                </button>
                <button
                  className={s.botaoSecundario}
                  onClick={() => navegar(`/epi/cameras/${selecionada.id}/scenario`)}
                >
                  <Frame size={13} strokeWidth={1.7} /> Cenário
                </button>
                {podeCadastrar && (
                  <button
                    className={s.botaoSecundario}
                    disabled={arquivando}
                    onClick={() =>
                      selecionada.is_active === false
                        ? void arquivarOuRestaurar()
                        : setConfirmarArquivo(true)
                    }
                  >
                    {selecionada.is_active === false ? 'Desarquivar' : 'Arquivar'}
                  </button>
                )}
              </div>

              {(teste || erroTeste) && (
                <div className={s.painelTeste}>
                  <span className={s.overline}>Teste de conexão · passo a passo</span>
                  {teste &&
                    PASSOS.map(([chave, texto]) => {
                      const check = teste.checks?.[chave]
                      const tom = TOM_PASSO[check?.status ?? 'pending'] ?? 'neutro'
                      return (
                        <div key={chave} className={s.passo}>
                          <span className={`${s.passoMarca} ${s.tom[tom]}`} aria-hidden="true">
                            {MARCA_PASSO[check?.status ?? 'pending'] ?? '·'}
                          </span>
                          <span className={s.passoTexto}>{texto}</span>
                          <span className={`${s.resultadoDica} ${s.tom[tom]}`}>
                            {check?.message ?? 'não executado'}
                          </span>
                        </div>
                      )
                    })}
                  {teste && (
                    <div className={`${s.resultado} ${teste.success ? s.tom.ok : s.tom.nc}`} role="status">
                      {teste.success ? 'Conexão estabelecida' : teste.error || 'Falha na conexão'}
                      {teste.suggestion && <span className={s.resultadoDica}>{teste.suggestion}</span>}
                    </div>
                  )}
                  {erroTeste && (
                    <div className={`${s.resultado} ${s.tom.nc}`} role="status">{erroTeste}</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {aba === 'sites' && (
        <div className={s.pagina}>
          {erroSites && (
            <p className={s.nota}>
              Não foi possível carregar os sites: {erroSites}. Isto não quer dizer que não há sites —
              a listagem é restrita a administradores.
            </p>
          )}
          {sites.length === 0 && !erroSites && (
            <p className={s.nota}>Nenhum site edge cadastrado para este tenant.</p>
          )}
          {sites.map((site) => {
            const saude = saudeSites.find((h) => h.site_id === site.id)
            const est = saude ? ESTADO_SITE[saude.status] : null
            return (
              <div key={site.id} className={s.cartaoSite}>
                <div className={s.cartaoTopo}>
                  <span className={s.cartaoNome}>{site.name}</span>
                  {est ? (
                    <span className={`${s.estadoLinha} ${s.tom[est.tom]}`}>
                      <est.Icone size={13} strokeWidth={1.7} aria-hidden="true" />
                      {est.palavra}
                    </span>
                  ) : (
                    <span className={`${s.estadoLinha} ${s.tom.neutro}`}>
                      <CircleSlash size={13} strokeWidth={1.7} aria-hidden="true" /> SEM TELEMETRIA
                    </span>
                  )}
                </div>

                <div className={s.bloco}>
                  <span className={s.textoAuxiliar}>Modo de processamento do site</span>
                  <div className={s.seletorModo}>
                    {(Object.keys(DEPLOYMENT_MODE_LABELS) as DeploymentMode[]).map((m) => (
                      <button
                        key={m}
                        className={site.deployment_mode === m ? s.modo.ativo : s.modo.inativo}
                        aria-pressed={site.deployment_mode === m}
                        disabled={!podeConfigurar || salvandoModo}
                        onClick={() => { void trocarModo(site, m) }}
                      >
                        {DEPLOYMENT_MODE_LABELS[m]}
                      </button>
                    ))}
                  </div>
                  <span className={s.textoAuxiliar}>{MODO_DESCRICAO[site.deployment_mode]}</span>
                  {!podeConfigurar && (
                    <span className={s.textoAuxiliar}>
                      Somente leitura — trocar o modo exige a permissão de configurar câmeras.
                    </span>
                  )}
                </div>

                <div className={s.bloco}>
                  <span className={s.overline}>Saúde do equipamento · {site.name}</span>
                  <div className={s.metricas}>
                    <div className={s.metrica}>
                      <span className={s.metricaChave}>Câmeras</span>
                      <span className={s.metricaValor}>
                        {saude ? `${saude.cameras_online}/${saude.cameras_total}` : '—'}
                      </span>
                    </div>
                    <div className={s.metrica}>
                      <span className={s.metricaChave}>FPS inferência</span>
                      <span className={s.metricaValor}>{numero(saude?.fps)}</span>
                    </div>
                    <div className={s.metrica}>
                      <span className={s.metricaChave}>GPU °C</span>
                      <span className={s.metricaValor}>{numero(saude?.gpu_temp_c)}</span>
                    </div>
                    <div className={s.metrica}>
                      <span className={s.metricaChave}>FPS decode</span>
                      <span className={s.metricaValor}>{numero(saude?.decode_fps)}</span>
                    </div>
                  </div>
                </div>

                <div className={s.linhaSync}>
                  <span>Sincronização edge → cloud</span>
                  <span className={`${s.estadoLinha} ${s.tom[est?.tom ?? 'neutro']}`}>
                    {haQuanto(saude?.last_heartbeat)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {aba === 'saude' && (
        <div className={s.pagina}>
          <table className={s.tabela}>
            <thead>
              <tr>
                <th className={s.th}>Câmera</th>
                <th className={s.th}>Status</th>
                <th className={s.thNum}>Uptime 7d</th>
                <th className={s.thNum}>FPS alvo</th>
                <th className={s.thNum}>Último frame</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => {
                const est = estadoDaCamera(cam)
                return (
                  <tr key={cam.id}>
                    <td className={s.tdNome}>{cam.name}</td>
                    <td className={s.td}>
                      <span className={`${s.celulaEstado} ${s.tom[est.tom]}`}>
                        <est.Icone size={13} strokeWidth={1.7} aria-hidden="true" />
                        {est.palavra}
                      </span>
                    </td>
                    <td className={s.tdNum}>—</td>
                    <td className={s.tdNum}>{numero(cam.fps_target)}</td>
                    <td className={s.tdNum}>{haQuanto(cam.last_seen)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className={s.nota}>
            &quot;Uptime 7d&quot; fica vazio de propósito: não existe endpoint de uptime por câmera —
            só por site (heartbeat do edge). &quot;FPS alvo&quot; é o configurado na câmera, não o
            medido.
          </p>
        </div>
      )}

      {aba === 'escopo' && <AbaEscopo cameras={cameras} podeEditar={podeConfigurar} />}

      {modais}
    </div>
  )
}

export default Cameras
