/**
 * CamerasPorModulo — "Para que serve cada câmera". A tela em que o dono separa
 * o que é EPI do que é estacionamento.
 *
 * ─── O PROBLEMA QUE ELA RESOLVE ────────────────────────────────────────────
 * Não existia vínculo câmera↔módulo. `public.cameras` tem `module_code` e
 * `active_module`, as duas VARCHAR única e as duas com DEFAULT 'epi' — e as 29
 * câmeras da RVB estão em 'epi' porque esse é o default da coluna, não porque
 * alguém decidiu. Resultado medido: o pool de anotação do EPI carrega 1.035
 * quadros da "Qualidade 06" e 300 das câmeras de estacionamento e guarita.
 * Esta tela é onde a decisão passa a existir (migration 134,
 * `public.camera_modules`, N:N).
 *
 * ⚠️ ELA NÃO ACUSA NINGUÉM. Câmera de Qualidade no pool de EPI PODE ser
 * legítima — uma das câmeras da RVB se chama "Qualidade 01 EPI", que é o caso
 * de uso escrito no nome, e é por isso que o vínculo é N:N. A tela não marca
 * nada como errado e não sugere nada: quem declara é o dono.
 *
 * ─── O QUE ELA COPIA DE "MODELOS POR CÂMERA" ───────────────────────────────
 * A grade `CameraModelScope` (aba vizinha do Estúdio) é o molde: tabela por
 * câmera, chips que ligam/desligam, salvar por linha, e o mesmo motivo
 * arquitetural do endpoint em LOTE — lá a versão "um GET por câmera" estourou
 * o pool de conexões da API justamente nas 28 câmeras do RVB. Por isso aqui
 * também: UMA rota (`GET/PUT /api/cameras/modules`) que carrega e grava o
 * tenant inteiro, e a ação em massa é um único PUT, não N.
 *
 * ─── LINGUAGEM ─────────────────────────────────────────────────────────────
 * Quem usa é o dono da fábrica. Nenhum `module_code` aparece na tela; os nomes
 * saem de `app/modulos/rotulos.ts`, os mesmos do cartão de `/novo/modules`.
 *
 * ─── HONESTIDADE SOBRE O EFEITO ────────────────────────────────────────────
 * Marcar aqui GRAVA a decisão. A coleta de quadros e o painel ainda não leem
 * `camera_modules` (essa ponta é outra frente). A tela diz isso com todas as
 * letras — prometer um efeito que ainda não existe é a mentira mais cara que
 * uma tela de configuração pode contar.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Cctv, HelpCircle } from 'lucide-react'

import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { useToast } from '../../components/ui/Toast/useToast'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types'
import { DESCRICAO_MODULO, rotuloModulo } from '../modulos/rotulos'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './CamerasPorModulo.css'

const ROTA = '/cameras/modules'

export interface CameraComModulos {
  id: string
  name: string
  location?: string | null
  is_active: boolean
  /** Códigos declarados pelo dono. Vazio = SEM MÓDULO (ninguém declarou). */
  modules: string[]
}

interface Payload {
  cameras: CameraComModulos[]
  modules_enabled: string[]
}

/** Câmeras que ainda ninguém declarou. É a pergunta aberta da tela — nunca
 * fica escondida, e é a única lista que ganha um atalho de seleção próprio. */
export function semModulo(cameras: CameraComModulos[]): CameraComModulos[] {
  return cameras.filter((c) => c.modules.length === 0)
}

/** Conjunto que o PUT deve gravar ao (des)marcar UM módulo de UMA câmera.
 * Extraído porque é a única conta desta tela — e porque um teste que só clica
 * no chip não distingue "mandou o conjunto novo" de "mandou o antigo". */
export function alternar(atuais: string[], codigo: string): string[] {
  return atuais.includes(codigo) ? atuais.filter((m) => m !== codigo) : [...atuais, codigo]
}

interface ChipProps {
  rotulo: string
  titulo?: string
  marcado: boolean
  desabilitado: boolean
  ariaLabel: string
  onAlternar: () => void
}

/** Mesmo idioma visual do chip de classe de `CameraModelScope` — botão com
 * `aria-pressed`, não `<input type=checkbox>` (o quadradinho do navegador não
 * segue tema nenhum, achado B2 da rodada de UX). */
function Chip({ rotulo, titulo, marcado, desabilitado, ariaLabel, onAlternar }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={marcado}
      aria-label={ariaLabel}
      title={titulo}
      disabled={desabilitado}
      className={marcado ? `${s.chip} ${s.chipMarcado}` : s.chip}
      onClick={onAlternar}
    >
      {rotulo}
    </button>
  )
}

export function CamerasPorModulo() {
  const toast = useToast()
  // Mesma permissão de "Modelos por câmera": isto é configuração de câmera,
  // e ela inclui o admin do tenant — que é quem conhece a fábrica.
  const { can } = useAuth()
  const podeEditar = can('cameras:configure')

  const [dados, setDados] = useState<Payload | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [selecao, setSelecao] = useState<string[]>([])
  const [emMassa, setEmMassa] = useState<string[]>([])
  const [soSemModulo, setSoSemModulo] = useState(false)
  const [salvando, setSalvando] = useState(false)

  const carregar = useCallback(() => {
    setErro(null)
    api
      .get<ApiResponse<Payload>>(ROTA)
      .then((r) =>
        setDados({
          cameras: r?.data?.cameras ?? [],
          modules_enabled: r?.data?.modules_enabled ?? [],
        }),
      )
      .catch((e) => setErro(e instanceof Error ? e.message : 'Erro ao carregar as câmeras'))
  }, [])

  useEffect(carregar, [carregar])

  const cameras = dados?.cameras ?? []
  const modulos = dados?.modules_enabled ?? []
  const pendentes = useMemo(() => semModulo(cameras), [cameras])
  const visiveis = useMemo(
    () => (soSemModulo ? pendentes : cameras),
    [soSemModulo, pendentes, cameras],
  )

  /**
   * O único caminho de escrita — uma câmera ou várias, sempre o mesmo PUT.
   *
   * Otimista com desfazer: a lista muda na hora e VOLTA ao estado anterior se
   * a gravação falhar. Sem o rollback a tela ficaria afirmando uma decisão que
   * o banco não tem — que é exatamente o defeito que esta tela veio consertar.
   */
  const gravar = useCallback(
    (cameraIds: string[], modulosNovos: string[], mensagem: string) => {
      if (!podeEditar || cameraIds.length === 0 || !dados) return
      const anterior = dados
      const alvo = new Set(cameraIds)
      setDados({
        ...dados,
        cameras: dados.cameras.map((c) =>
          alvo.has(c.id) ? { ...c, modules: modulosNovos } : c,
        ),
      })
      setSalvando(true)
      api
        .put<ApiResponse<{ assignments: Record<string, string[]> }>>(ROTA, {
          camera_ids: cameraIds,
          modules: modulosNovos,
        })
        .then(() => toast.success(mensagem))
        .catch((e: unknown) => {
          setDados(anterior)
          toast.error(
            e instanceof Error ? e.message : 'Não deu para salvar',
            'Nada foi alterado — a lista voltou como estava. Tente de novo.',
          )
        })
        .finally(() => setSalvando(false))
    },
    [podeEditar, dados, toast],
  )

  const alternarCamera = useCallback(
    (cam: CameraComModulos, codigo: string) => {
      const novos = alternar(cam.modules, codigo)
      gravar(
        [cam.id],
        novos,
        novos.length === 0
          ? `${cam.name} ficou sem uso definido`
          : `${cam.name}: ${novos.map(rotuloModulo).join(', ')}`,
      )
    },
    [gravar],
  )

  const aplicarEmMassa = useCallback(() => {
    gravar(
      selecao,
      emMassa,
      emMassa.length === 0
        ? `${selecao.length} câmera(s) ficaram sem uso definido`
        : `${selecao.length} câmera(s) agora em ${emMassa.map(rotuloModulo).join(', ')}`,
    )
    setSelecao([])
    setEmMassa([])
  }, [gravar, selecao, emMassa])

  const alternarSelecao = (id: string) =>
    setSelecao((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const todasVisiveisSelecionadas =
    visiveis.length > 0 && visiveis.every((c) => selecao.includes(c.id))

  // ── estados de carga ─────────────────────────────────────────────────────
  if (erro) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={32} strokeWidth={1.5} aria-hidden="true" />
        <p className={s.centroTitulo}>Não deu para carregar as câmeras</p>
        {/* A lista NÃO foi carregada — isto não quer dizer "nenhuma câmera". */}
        <p className={s.centroTecnico}>GET /api{ROTA} · {erro}</p>
        <button className={s.botaoSecundario} onClick={carregar}>
          Tentar novamente
        </button>
      </div>
    )
  }

  if (dados === null) {
    return <LogikosLoader estado="waiting" variante="tile" rotulo="CARREGANDO CÂMERAS" />
  }

  if (cameras.length === 0) {
    return (
      <EmptyState
        icon={<Cctv size={26} strokeWidth={1.6} aria-hidden="true" />}
        title="Nenhuma câmera cadastrada"
        description="Cadastre as câmeras da fábrica primeiro. Depois volte aqui para dizer para que serve cada uma."
      />
    )
  }

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h2 className={s.titulo}>Para que serve cada câmera</h2>
        <p className={s.subtitulo}>
          Uma câmera pode servir para mais de uma coisa — marque todas que valerem.
        </p>
      </div>

      <p className={s.avisoEfeito} role="note">
        O que você marcar aqui fica gravado. A separação ainda <strong>não</strong> chegou à
        coleta de imagens nem ao painel — enquanto isso não acontece, esta tela registra a
        decisão, não muda o que já foi coletado.
      </p>

      {modulos.length === 0 && (
        <p className={s.avisoBloqueio} role="alert">
          Este cliente não tem nenhuma área liberada, então não há o que marcar. Quem
          administra a plataforma precisa liberar as áreas contratadas.
        </p>
      )}

      {!podeEditar && (
        <p className={s.avisoBloqueio} role="alert">
          Você só pode ver esta tela. Para mudar o uso das câmeras, peça a quem administra a
          sua conta.
        </p>
      )}

      {/* SEM BECO SEM SAÍDA: a câmera não declarada aparece, é contada, e tem
          um botão que a coloca direto na seleção da ação em massa. */}
      {pendentes.length > 0 && (
        <div className={s.pendencia} role="status">
          <HelpCircle size={18} strokeWidth={1.7} aria-hidden="true" />
          <span className={s.pendenciaTexto}>
            <strong>{pendentes.length}</strong>{' '}
            {pendentes.length === 1 ? 'câmera ainda não tem' : 'câmeras ainda não têm'} uso
            definido.
          </span>
          <button
            className={s.botaoSecundario}
            onClick={() => {
              setSoSemModulo(true)
              setSelecao(pendentes.map((c) => c.id))
            }}
          >
            Resolver essas agora
          </button>
        </div>
      )}

      <div className={s.filtros}>
        <Chip
          rotulo={soSemModulo ? `Mostrando só as sem uso (${pendentes.length})` : `Ver todas (${cameras.length})`}
          marcado={soSemModulo}
          desabilitado={false}
          ariaLabel="Mostrar só as câmeras sem uso definido"
          onAlternar={() => setSoSemModulo((v) => !v)}
        />
      </div>

      {/* Ação em massa. SUBSTITUI o conjunto das câmeras marcadas — está
          escrito na frase do botão, porque "aplicar" pode ser lido como
          "somar" e a diferença muda o resultado de 29 câmeras de uma vez. */}
      {selecao.length > 0 && podeEditar && (
        <div className={s.massa} role="group" aria-label="Ação em massa">
          <span className={s.massaTitulo}>
            {selecao.length} {selecao.length === 1 ? 'câmera marcada' : 'câmeras marcadas'} —
            elas passarão a servir <strong>exatamente</strong>:
          </span>
          <div className={s.massaChips}>
            {modulos.map((codigo) => (
              <Chip
                key={codigo}
                rotulo={rotuloModulo(codigo)}
                titulo={DESCRICAO_MODULO[codigo]}
                marcado={emMassa.includes(codigo)}
                desabilitado={salvando}
                ariaLabel={`${rotuloModulo(codigo)} para as câmeras marcadas`}
                onAlternar={() => setEmMassa((prev) => alternar(prev, codigo))}
              />
            ))}
          </div>
          <div className={s.massaAcoes}>
            <button className={s.botaoPrimario} disabled={salvando} onClick={aplicarEmMassa}>
              {emMassa.length === 0
                ? `Deixar ${selecao.length} sem uso definido`
                : `Aplicar a ${selecao.length}`}
            </button>
            <button
              className={s.botaoSecundario}
              onClick={() => {
                setSelecao([])
                setEmMassa([])
              }}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div className={s.tabelaWrap}>
        <table className={s.tabela}>
          <thead>
            <tr>
              <th className={s.th}>
                <input
                  type="checkbox"
                  aria-label="Marcar todas as câmeras da lista"
                  disabled={!podeEditar}
                  checked={todasVisiveisSelecionadas}
                  onChange={() =>
                    setSelecao(todasVisiveisSelecionadas ? [] : visiveis.map((c) => c.id))
                  }
                />
              </th>
              <th className={s.th}>Câmera</th>
              <th className={s.th}>Serve para</th>
            </tr>
          </thead>
          <tbody>
            {visiveis.map((cam) => (
              <tr key={cam.id} className={cam.modules.length === 0 ? s.linhaPendente : undefined}>
                <td className={s.td}>
                  <input
                    type="checkbox"
                    aria-label={`Marcar ${cam.name}`}
                    disabled={!podeEditar}
                    checked={selecao.includes(cam.id)}
                    onChange={() => alternarSelecao(cam.id)}
                  />
                </td>
                <td className={s.td}>
                  <span className={s.nome}>{cam.name}</span>
                  {cam.location && <span className={s.local}>{cam.location}</span>}
                  {!cam.is_active && <span className={s.arquivada}>desligada</span>}
                </td>
                <td className={s.td}>
                  <div className={s.chips}>
                    {modulos.map((codigo) => (
                      <Chip
                        key={codigo}
                        rotulo={rotuloModulo(codigo)}
                        titulo={DESCRICAO_MODULO[codigo]}
                        marcado={cam.modules.includes(codigo)}
                        desabilitado={!podeEditar || salvando}
                        ariaLabel={`${rotuloModulo(codigo)} em ${cam.name}`}
                        onAlternar={() => alternarCamera(cam, codigo)}
                      />
                    ))}
                    {/* Câmera atribuída a uma área que este cliente não tem mais
                        liberada: sem isto o vínculo existiria no banco e seria
                        invisível — e não teria como ser desfeito. */}
                    {cam.modules
                      .filter((codigo) => !modulos.includes(codigo))
                      .map((codigo) => (
                        <Chip
                          key={codigo}
                          rotulo={`${rotuloModulo(codigo)} (não contratada)`}
                          marcado
                          desabilitado={!podeEditar || salvando}
                          ariaLabel={`${rotuloModulo(codigo)} em ${cam.name} — área não contratada`}
                          onAlternar={() => alternarCamera(cam, codigo)}
                        />
                      ))}
                    {cam.modules.length === 0 && (
                      <span className={s.semUso}>ainda sem uso definido</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {visiveis.length === 0 && (
              <tr>
                <td className={s.td} colSpan={3}>
                  Todas as câmeras já têm uso definido.{' '}
                  <button className={s.linkInline} onClick={() => setSoSemModulo(false)}>
                    Ver todas
                  </button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
