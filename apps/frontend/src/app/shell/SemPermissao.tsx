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

export function SemPermissao({ permissao }: { permissao: string }) {
  return (
    <div className={s.centro} role="status">
      <Lock size={36} strokeWidth={1.7} color={lk.cor.cinzaNevoa} aria-hidden="true" />
      <span className={s.titulo}>Sem permissão</span>
      <span className={s.texto}>
        Esta área exige a permissão <code className={s.chave}>{permissao}</code>. Peça ao
        administrador do seu tenant.
      </span>
      <Link className={s.voltar} to={rotaNova('/')}>
        Voltar ao início
      </Link>
    </div>
  )
}
