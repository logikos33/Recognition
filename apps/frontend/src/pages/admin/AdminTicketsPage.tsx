/**
 * AdminTicketsPage — Placeholder para sistema de tickets (Fase 2).
 * Tabela vazia com colunas prontas.
 * Tabela admin.support_tickets já existe no banco.
 */
export function AdminTicketsPage() {
  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      <h1 style={{ marginBottom: 8 }}>Suporte — Tickets</h1>
      <p style={{ color: '#888', marginBottom: 32 }}>
        Sistema de tickets será implementado na Fase 2. A estrutura de dados já está pronta no banco.
      </p>

      {/* Aviso de fase 2 */}
      <div style={{
        border: '2px dashed #d1d5db', borderRadius: 12, padding: 32,
        textAlign: 'center', color: '#6b7280', marginBottom: 32,
      }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>🎫</div>
        <h2 style={{ marginBottom: 8, color: '#374151' }}>Em breve — Fase 2</h2>
        <p>Gerenciamento de tickets de suporte, notificações via WebSocket e respostas inline.</p>
      </div>

      {/* Tabela vazia com estrutura pronta */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, opacity: 0.5 }}>
        <thead>
          <tr style={{ background: '#f5f5f5', textAlign: 'left' }}>
            <th style={th}>ID</th>
            <th style={th}>Cliente</th>
            <th style={th}>Assunto</th>
            <th style={th}>Status</th>
            <th style={th}>Prioridade</th>
            <th style={th}>Data</th>
            <th style={th}>Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={7} style={{ padding: 24, textAlign: 'center', color: '#999' }}>
              Nenhum ticket no momento
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

const th: React.CSSProperties = { padding: '8px 12px', fontWeight: 600 }
