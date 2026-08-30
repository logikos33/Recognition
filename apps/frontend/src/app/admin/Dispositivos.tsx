/**
 * Dispositivos — `/novo/admin/dispositivos` (F5 SR2 PR-3). Desenho: `Admin
 * Plataforma.dc.html`, seção "Dispositivos".
 *
 * MEDIÇÃO DO BACKEND (`services/api/app/api/v1/devices/routes.py`):
 *
 *  - `POST /api/devices/claim-codes` (linha 47-94) — gera claim code (JWT,
 *    permissão `devices:manage`), plaintext exibido só nesta resposta,
 *    TTL 15 min (`CLAIM_CODE_TTL_MINUTES`). É a ÚNICA ação real desta tela.
 *  - `POST /api/devices/claim` (linha 97) — público, o DISPOSITIVO troca o
 *    código por um token; não é chamado por esta tela.
 *  - Sem `/v1` no prefixo: o blueprint registra `url_prefix="/api/devices"`
 *    direto (`app/__init__.py:395-396`), por isso o path daqui é
 *    `/devices/claim-codes` (API_BASE já inclui `/api`).
 *  - NENHUMA rota de LISTAGEM nem de REVOGAÇÃO — grep por `device_claim` e
 *    `DeviceClaimRepository` (`infrastructure/database/repositories/
 *    device_claim_repository.py`) só encontra `create`, `redeem` e
 *    `get_status` (este último documentado como "debug/auditoria, nunca
 *    expor na API"). A tabela "dispositivo/vínculo/tipo/status + Revogar"
 *    do desenho fica OMITIDA — pedido registrado em
 *    `docs/migration/PEDIDOS-AO-BACKEND-F5.md`.
 *
 * Código exibido UMA VEZ: fica só em estado local do componente — nunca em
 * localStorage/query cache — então sair da tela e voltar (remount) não o
 * traz de volta. Gerar de novo substitui o anterior, nunca acumula.
 */
import { useState } from 'react'
import { Check, Copy, HardDrive } from 'lucide-react'

import { useToast } from '../../components/ui/Toast/useToast'
import type { R } from '../../modules/admin/types/admin'
import { api } from '../../services/api'
import * as s from './Dispositivos.css'

interface ClaimCodeResponse {
  claim_code: string
  claim_id: string
  expires_at: string
  expires_in_minutes: number
}

type Estado = 'idle' | 'gerando' | 'gerado' | 'erro'

export function Dispositivos() {
  const toast = useToast()
  const [estado, setEstado] = useState<Estado>('idle')
  const [codigo, setCodigo] = useState<ClaimCodeResponse | null>(null)
  const [copiado, setCopiado] = useState(false)

  const gerarCodigo = async () => {
    setEstado('gerando')
    setCopiado(false)
    try {
      const res = await api.post<R<ClaimCodeResponse>>('/devices/claim-codes')
      setCodigo(res.data)
      setEstado('gerado')
    } catch (e: unknown) {
      setEstado('erro')
      setCodigo(null)
      toast.error(e instanceof Error ? e.message : 'Erro ao gerar código de reivindicação')
    }
  }

  const copiar = async () => {
    if (!codigo) return
    try {
      await navigator.clipboard.writeText(codigo.claim_code)
      setCopiado(true)
    } catch {
      /* clipboard indisponível — o código já está visível para copiar à mão */
    }
  }

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Dispositivos</h1>
        <span className={s.subtitulo}>kiosks e andons — acesso por código, sem login interativo</span>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          className={s.botaoPrimario}
          onClick={() => void gerarCodigo()}
          disabled={estado === 'gerando'}
        >
          {estado === 'gerando' ? 'Gerando...' : 'Gerar código de reivindicação'}
        </button>
      </div>

      {estado === 'gerado' && codigo && (
        <div className={s.bannerCodigo}>
          <span>Digite este código no dispositivo:</span>
          <span className={s.codigo}>{codigo.claim_code}</span>
          <span className={s.expira}>EXPIRA EM {codigo.expires_in_minutes} MIN</span>
          <button type="button" className={s.botaoCopiar} onClick={() => void copiar()}>
            {copiado ? <Check size={14} strokeWidth={2} aria-hidden="true" /> : <Copy size={14} strokeWidth={1.8} aria-hidden="true" />}
            {copiado ? 'Copiado' : 'Copiar'}
          </button>
        </div>
      )}

      <div className={s.notaOmissao}>
        <HardDrive size={16} strokeWidth={1.6} aria-hidden="true" />
        <span>
          Lista de dispositivos reivindicados e revogação ainda não têm rota no backend — hoje só
          a geração de código de reivindicação existe. Pedido registrado para priorização.
        </span>
      </div>
    </div>
  )
}
