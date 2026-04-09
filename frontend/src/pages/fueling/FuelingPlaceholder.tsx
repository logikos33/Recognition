/**
 * FuelingPlaceholder — Tela "em breve" para o módulo Fueling Control.
 */
export function FuelingPlaceholder() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '60vh', textAlign: 'center', padding: 32,
    }}>
      <div style={{
        fontSize: 64, width: 120, height: 120, borderRadius: '50%',
        background: '#1e293b', display: 'flex', alignItems: 'center',
        justifyContent: 'center', marginBottom: 24,
      }}>⛽</div>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: '#e2e8f0', margin: '0 0 8px' }}>
        Fueling Control
      </h1>
      <p style={{ fontSize: 14, color: '#64748b', maxWidth: 420, lineHeight: 1.6, margin: '0 0 24px' }}>
        Módulo de acompanhamento de abastecimento com OCR de placas e contagem automática de produtos carregados.
      </p>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        fontSize: 13, color: '#475569',
        background: '#1e293b', padding: '8px 16px', borderRadius: 20,
      }}>
        <span>⏳</span>
        <span>Em breve</span>
      </div>
    </div>
  )
}

export default FuelingPlaceholder
