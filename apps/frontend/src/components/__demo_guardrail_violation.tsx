/**
 * DEMO task-065 — NÃO MERGEAR.
 * Arquivo sintético para provar que o guard-rail anti-cores-hardcoded
 * reprova o CI quando há rgba(255,255,255,x) hand-rolled.
 */
export function DemoGuardrailViolation() {
  return <div style={{ color: 'rgba(255,255,255,0.5)' }}>demo violação guard-rail</div>
}
