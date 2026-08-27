/**
 * PaletaComandos — o ⌘K da Logikos Vision.
 *
 * Handoff (LOTE 1, "Command palette ⌘K", NOVO): "Busca global: câmeras,
 * eventos, telas, ações — com atalhos exibidos. Abre por clique ou ⌘K/Ctrl+K;
 * fecha com ESC."
 *
 * ELA NÃO BUSCA NADA. Recebe `grupos` prontos de quem a monta. O motivo é o
 * de sempre neste produto: cada tenant tem câmeras, eventos e telas próprios,
 * e uma paleta que soubesse de API viraria mais um lugar por onde vazar
 * contexto de outro tenant. Aqui só entra o que o chamador já autorizou.
 *
 * O teclado inteiro mora num único listener no `document`, e não espalhado em
 * `onKeyDown`: enquanto aberta ela é modal, então ↑ ↓ ↵ ESC são dela mesmo que
 * o foco escorregue do campo.
 */
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'

import * as s from './PaletaComandos.css'

export interface ItemPaleta {
  id: string
  rotulo: string
  /** Atalho exibido em mono — 'G V', '⌘⇧A'. Ausente = item sem atalho. */
  atalho?: string
  /** Acessório à direita: 'HOJE 14:32', '● online'. */
  detalhe?: string
  icone?: ReactNode
  aoEscolher: () => void
}

export interface GrupoPaleta {
  id: string
  /** 'Câmeras' · 'Eventos' · 'Telas' · 'Ações' — os quatro do handoff. */
  titulo: string
  itens: ItemPaleta[]
}

export interface PaletaComandosProps {
  grupos: GrupoPaleta[]
  /**
   * Só para quem precisa abrir de fora (o botão "Buscar…" da topbar). Sem
   * esta prop a paleta se governa sozinha pelo ⌘K.
   */
  aberta?: boolean
  onAbertaChange?: (aberta: boolean) => void
}

/**
 * Chave de comparação da busca: sem acento e em minúscula. Quem digita
 * "acoes" com pressa tem de achar "Ações" — no chão de fábrica ninguém para
 * para acertar o til.
 */
const chave = (texto: string) =>
  texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()

export function PaletaComandos({ grupos, aberta: abertaExterna, onAbertaChange }: PaletaComandosProps) {
  const [abertaInterna, setAbertaInterna] = useState(false)
  const aberta = abertaExterna ?? abertaInterna
  const [busca, setBusca] = useState('')
  const [destaque, setDestaque] = useState(0)

  const campoRef = useRef<HTMLInputElement>(null)
  /** De onde o foco veio. Fechar sem devolver o foco deixa quem usa teclado
   *  perdido no começo da página. */
  const focoAnteriorRef = useRef<HTMLElement | null>(null)
  const idBase = useId()

  const definirAberta = (valor: boolean) => {
    setAbertaInterna(valor)
    onAbertaChange?.(valor)
  }

  /** Filtra DENTRO dos grupos e descarta os que ficaram vazios — grupo com
   *  título e nenhum item é ruído. */
  const visiveis = useMemo(() => {
    const alvo = chave(busca.trim())
    return grupos
      .map((g) => (alvo ? { ...g, itens: g.itens.filter((i) => chave(i.rotulo).includes(alvo)) } : g))
      .filter((g) => g.itens.length > 0)
  }, [grupos, busca])

  /** A navegação ignora as fronteiras de grupo: ↓ no último item de Câmeras
   *  cai no primeiro de Eventos, como em qualquer paleta. */
  const planos = useMemo(() => visiveis.flatMap((g) => g.itens), [visiveis])
  const indice = planos.length > 0 ? Math.min(destaque, planos.length - 1) : -1

  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      // ⌘K no Mac, Ctrl+K no resto. Alterna, para o mesmo atalho fechar.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        definirAberta(!aberta)
        return
      }
      if (!aberta) return

      if (e.key === 'Escape') {
        e.preventDefault()
        definirAberta(false)
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        const alvo = planos[indice]
        if (alvo) {
          alvo.aoEscolher()
          definirAberta(false)
        }
        return
      }
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
      e.preventDefault()
      if (planos.length === 0) return
      const passo = e.key === 'ArrowDown' ? 1 : -1
      // (i + passo + n) % n dá a volta nas duas pontas sem ramificar.
      setDestaque((i) => (Math.min(i, planos.length - 1) + passo + planos.length) % planos.length)
    }

    // Sem lista de dependências de propósito: o handler lê `aberta`, `indice`
    // e `planos` do render corrente. Um array aqui é convite a closure velha,
    // e o custo de reassinar um listener por render é zero perto disso.
    document.addEventListener('keydown', aoTeclar)
    return () => document.removeEventListener('keydown', aoTeclar)
  })

  useEffect(() => {
    if (aberta) {
      focoAnteriorRef.current = document.activeElement as HTMLElement | null
      // Abrir com a busca anterior ainda no campo mostraria um resultado que
      // ninguém pediu desta vez.
      setBusca('')
      setDestaque(0)
      campoRef.current?.focus()
    } else {
      focoAnteriorRef.current?.focus()
      focoAnteriorRef.current = null
    }
  }, [aberta])

  if (!aberta) return null

  const idLista = `${idBase}-lista`
  const idItem = (i: number) => `${idBase}-op-${i}`
  // Contador corrido: o índice do item na lista plana, atravessando grupos.
  let n = -1

  return (
    <div className={s.veu} onMouseDown={() => definirAberta(false)}>
      <div
        className={s.painel}
        role="dialog"
        aria-modal="true"
        aria-label="Paleta de comandos"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className={s.cabecalho}>
          <svg className={s.lupa} viewBox="0 0 24 24" aria-hidden="true">
            <path d="M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12zM14.5 14.5L20 20" />
          </svg>
          <input
            ref={campoRef}
            className={s.campo}
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value)
              // Filtrou, o destaque volta ao topo: manter o índice apontaria
              // para um item que a busca acabou de tirar da tela.
              setDestaque(0)
            }}
            placeholder="Buscar câmeras, eventos, telas, ações…"
            aria-label="Buscar câmeras, eventos, telas, ações"
            role="combobox"
            aria-expanded
            aria-autocomplete="list"
            aria-controls={idLista}
            aria-activedescendant={indice >= 0 ? idItem(indice) : undefined}
          />
          <span className={s.tecla}>ESC</span>
        </div>

        <div className={s.lista} id={idLista} role="listbox" aria-label="Resultados">
          {planos.length === 0 ? (
            <div className={s.vazio} role="presentation">
              Nada encontrado.
            </div>
          ) : (
            visiveis.map((grupo) => (
              <div key={grupo.id} role="group" aria-labelledby={`${idBase}-g-${grupo.id}`}>
                <span className={s.titulo} id={`${idBase}-g-${grupo.id}`}>
                  {grupo.titulo}
                </span>
                {grupo.itens.map((item) => {
                  const i = (n += 1)
                  return (
                    <div
                      key={item.id}
                      id={idItem(i)}
                      role="option"
                      aria-selected={i === indice}
                      className={i === indice ? `${s.item} ${s.destacado}` : s.item}
                      onMouseMove={() => setDestaque(i)}
                      onClick={() => {
                        item.aoEscolher()
                        definirAberta(false)
                      }}
                    >
                      {item.icone && (
                        <span className={s.icone} aria-hidden="true">
                          {item.icone}
                        </span>
                      )}
                      <span className={s.rotulo}>{item.rotulo}</span>
                      {item.detalhe && <span className={s.detalhe}>{item.detalhe}</span>}
                      {item.atalho && <span className={s.tecla}>{item.atalho}</span>}
                    </div>
                  )
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
