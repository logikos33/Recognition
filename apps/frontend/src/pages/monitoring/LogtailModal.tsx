/**
 * LogtailModal — últimas linhas de log de uma unit do box (lines=200).
 * Logtail é um COMANDO: pode voltar pending (box dormindo) — acompanha via
 * GET /monitoring/commands/<id> a cada 2,5 s até done/failed.
 * Os logs são redigidos no box ANTES de sair (aviso no rodapé).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Modal } from '../../components/ui/Modal/Modal'
import { Banner } from '../../components/ui/Banner/Banner'
import { Skeleton } from '../../components/ui/Skeleton/Skeleton'
import { usePolling } from '../../hooks/usePolling'
import { monitoringService } from '../../services/monitoringService'
import type { LogtailResult } from '../../types/monitoring'
import * as s from './monitoring.css'

interface LogtailModalProps {
  open: boolean
  siteId: string
  unit: string | null
  onClose: () => void
}

export function LogtailModal({ open, siteId, unit, onClose }: LogtailModalProps) {
  const [result, setResult] = useState<LogtailResult | null>(null)
  const [waking, setWaking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const commandIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!open || !unit) return
    let cancelled = false
    setResult(null)
    setError(null)
    setWaking(false)
    setPolling(false)
    commandIdRef.current = null

    monitoringService
      .logtail(siteId, unit, 200)
      .then((res) => {
        if (cancelled) return
        if (res.state === 'done' && res.result) {
          setResult(res.result)
        } else if (res.state === 'failed') {
          setError('O box respondeu com falha ao ler o log.')
        } else if (res.command_id) {
          commandIdRef.current = res.command_id
          setWaking(true)
          setPolling(true)
        } else {
          setError('Resposta sem comando para acompanhar.')
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Falha ao pedir o log.')
      })

    return () => {
      cancelled = true
    }
  }, [open, unit, siteId])

  const pollCommand = useCallback(async () => {
    const id = commandIdRef.current
    if (!id) return
    const res = await monitoringService.getLogtailCommand(id)
    if (res.state === 'done') {
      setResult(res.result ?? { lines: [] })
      setWaking(false)
      setPolling(false)
    } else if (res.state === 'failed') {
      setError('O box respondeu com falha ao ler o log.')
      setWaking(false)
      setPolling(false)
    }
  }, [])

  usePolling(pollCommand, 2500, { enabled: open && polling })

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={unit ? `Log — ${unit}` : 'Log'}
      maxWidth="760px"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {error && <Banner variant="danger">{error}</Banner>}
        {waking && !error && (
          <Banner variant="info">
            Acordando o box — o agente faz poll de comandos a cada 60 s.
            Aguardando o log...
          </Banner>
        )}
        {!result && !error && (
          <div>
            <Skeleton variant="text" height={16} style={{ marginBottom: 6 }} />
            <Skeleton variant="text" height={16} style={{ marginBottom: 6 }} />
            <Skeleton variant="text" height={16} width="70%" />
          </div>
        )}
        {result && (
          <>
            {result.path && (
              <span className={`${s.muted} ${s.mono}`}>{result.path}</span>
            )}
            <pre className={s.logPre}>
              {result.lines?.length ? result.lines.join('\n') : '(log vazio)'}
            </pre>
            {result.truncated && (
              <span className={s.muted}>Saída truncada — mostrando as últimas linhas.</span>
            )}
          </>
        )}
        <span className={s.muted}>
          Logs são redigidos no box antes de sair — segredos e tokens já vêm mascarados.
        </span>
      </div>
    </Modal>
  )
}
