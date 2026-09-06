/**
 * Estado "Sem permissão" — contrato de rota do front novo (o Estúdio soma este
 * quinto estado aos quatro de sempre; `Estúdio.dc.html` / Handoff LOTE 3).
 *
 * O desenho traz um CTA "Solicitar acesso". Não existe rota no backend que
 * registre esse pedido — o botão prometeria o que ninguém honra. Fica a
 * orientação e o caminho de volta; o CTA está registrado como pedido-ao-backend.
 */
import { Lock } from 'lucide-react'
import { Link } from 'react-router-dom'

import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import * as s from './SemPermissao.css'

/**
 * Chave de permissão → o PODER em português (issue #810).
 *
 * A chave CRUA era servida por este componente compartilhado a 5 chamadores —
 * um deles, `epi/Cenario.tsx`, no caminho dos usuários da RVB. A régua
 * `semJargao` não acusa: `{permissao}` é EXPRESSÃO, não literal em JSX, e a
 * varredura só lê literal. Por isso a tradução mora aqui, no componente: um
 * guard, não cinco cópias no chamador.
 *
 * Chave desconhecida cai no texto genérico — nunca vaza a chave.
 */
const PODER: Record<string, string> = {
  'admin:panel': 'de abrir o painel de administração',
  'cameras:configure': 'de configurar as câmeras',
  'frames:annotate': 'de anotar imagens',
  'training:read': 'de ver os treinos e os modelos',
  'training:write': 'de preparar treinos',
}

export function SemPermissao({ permissao }: { permissao: string }) {
  const poder = PODER[permissao]
  return (
    <div className={s.centro} role="status">
      <Lock size={36} strokeWidth={1.7} color={lk.cor.cinzaNevoa} aria-hidden="true" />
      <span className={s.titulo}>Sem permissão</span>
      <span className={s.texto}>
        {poder
          ? `Esta área exige a permissão ${poder}.`
          : 'Você não tem permissão para abrir esta área.'}{' '}
        Peça a quem administra o seu acesso.
      </span>
      <Link className={s.voltar} to={rotaNova('/')}>
        Voltar ao início
      </Link>
    </div>
  )
}
