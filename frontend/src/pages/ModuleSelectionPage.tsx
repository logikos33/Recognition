/**
 * ModuleSelectionPage — SaaS module picker after login.
 * Two cards: EPI Monitor (active) and Controle de Carregamento (coming soon).
 */
import { useNavigate } from 'react-router-dom'
import { Shield, Truck, Microscope, ArrowRight } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { useAuth } from '../hooks/useAuth'
import {
  page, header, title, subtitle, cardsRow,
  card, cardDisabled, cardIconWrap, cardTitle, cardDesc,
  badgeActive, badgeDot, badgeComingSoon, cardCta,
} from './ModuleSelectionPage.css'

export function ModuleSelectionPage() {
  const navigate = useNavigate()
  const setSelectedModule = useAppStore((s) => s.setSelectedModule)
  const { hasModule } = useAuth()

  const handleSelectEpi = () => {
    setSelectedModule('epi')
    navigate('/epi/dashboard')
  }

  const handleSelectQuality = () => {
    setSelectedModule('quality')
    navigate('/quality/dashboard')
  }

  return (
    <div className={page}>
      <div className={header}>
        <h1 className={title}>Selecione o Módulo</h1>
        <p className={subtitle}>
          Escolha o módulo de monitoramento para acessar o dashboard e as câmeras.
        </p>
      </div>

      <div className={cardsRow}>
        {/* EPI Monitor — Active */}
        <div
          className={card}
          onClick={handleSelectEpi}
          role="button"
          tabIndex={0}
          aria-label="Acessar módulo EPI Monitor"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleSelectEpi() }}
        >
          <div className={cardIconWrap}>
            <Shield size={28} color="#a78bfa" />
          </div>
          <span className={badgeActive}>
            <span className={badgeDot} />
            Ativo
          </span>
          <h2 className={cardTitle}>EPI Monitor</h2>
          <p className={cardDesc}>
            Monitoramento inteligente de Equipamentos de Proteção Individual.
            Detecção em tempo real via câmeras CCTV com visão computacional YOLOv8.
          </p>
          <div className={cardCta}>
            Acessar módulo <ArrowRight size={14} />
          </div>
        </div>

        {/* Qualidade Industrial — Ativo se tenant tiver módulo 'quality' */}
        {hasModule('quality') ? (
          <div
            className={card}
            onClick={handleSelectQuality}
            role="button"
            tabIndex={0}
            aria-label="Acessar módulo Qualidade Industrial"
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleSelectQuality() }}
          >
            <div className={cardIconWrap}>
              <Microscope size={28} color="#34d399" />
            </div>
            <span className={badgeActive}>
              <span className={badgeDot} />
              Ativo
            </span>
            <h2 className={cardTitle}>Qualidade Industrial</h2>
            <p className={cardDesc}>
              Inspeção visual automatizada com YOLO, controle estatístico de processo (CEP)
              e relatórios de turno em tempo real.
            </p>
            <div className={cardCta}>
              Acessar módulo <ArrowRight size={14} />
            </div>
          </div>
        ) : (
          <div
            className={cardDisabled}
            role="button"
            aria-disabled="true"
            aria-label="Módulo Qualidade Industrial em breve"
          >
            <div className={cardIconWrap}>
              <Microscope size={28} color="#64748b" />
            </div>
            <span className={badgeComingSoon}>Em breve</span>
            <h2 className={cardTitle}>Qualidade Industrial</h2>
            <p className={cardDesc}>
              Inspeção visual automatizada com YOLO, controle estatístico de processo (CEP)
              e relatórios de turno em tempo real.
            </p>
          </div>
        )}

        {/* Controle de Carregamento — Coming Soon */}
        <div
          className={cardDisabled}
          role="button"
          aria-disabled="true"
          aria-label="Módulo Controle de Carregamento em breve"
        >
          <div className={cardIconWrap}>
            <Truck size={28} color="#64748b" />
          </div>
          <span className={badgeComingSoon}>
            Em breve
          </span>
          <h2 className={cardTitle}>Controle de Carregamento</h2>
          <p className={cardDesc}>
            Acompanhamento de operações de carga e descarga.
            Contabilização automática de materiais e verificação de qualidade em tempo real.
          </p>
        </div>
      </div>
    </div>
  )
}
