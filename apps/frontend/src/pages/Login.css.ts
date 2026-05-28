/**
 * Login page styles — light blue theme (standalone, no vars tokens).
 */
import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({
  minHeight: '100vh',
  background: 'linear-gradient(160deg, #eff6ff, #dbeafe, #bfdbfe)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontFamily: "'Inter', 'Segoe UI', sans-serif",
  padding: '20px',
})

export const container = style({
  width: '100%',
  maxWidth: '400px',
})

export const logoWrap = style({
  textAlign: 'center',
  marginBottom: '28px',
})

export const logoIcon = style({
  width: '72px',
  height: '72px',
  borderRadius: '20px',
  margin: '0 auto 14px',
  background: 'linear-gradient(135deg, #2563eb, #1e40af)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '36px',
  boxShadow: '0 8px 24px rgba(37, 99, 235, 0.4)',
})

export const logoTitle = style({
  fontSize: '28px',
  fontWeight: 800,
  color: '#1e3a5f',
  margin: 0,
})

export const logoSub = style({
  color: '#64748b',
  margin: '6px 0 0',
  fontSize: '14px',
})

export const card = style({
  background: '#fff',
  borderRadius: '20px',
  padding: '28px 24px',
  boxShadow: '0 8px 40px rgba(37, 99, 235, 0.12)',
  border: '1px solid #e0eaff',
})

export const tabs = style({
  display: 'flex',
  background: '#f0f7ff',
  borderRadius: '10px',
  padding: '4px',
  marginBottom: '24px',
  gap: '4px',
})

export const tabBtn = style({
  flex: 1,
  padding: '9px 0',
  border: 'none',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 600,
  cursor: 'pointer',
  background: 'transparent',
  color: '#94a3b8',
  boxShadow: 'none',
  transition: `background ${vars.animation.duration}, color ${vars.animation.duration}, box-shadow ${vars.animation.duration}`,
})

export const tabBtnActive = style({
  background: '#fff',
  color: '#2563eb',
  boxShadow: '0 2px 8px rgba(37, 99, 235, 0.15)',
})

export const formStack = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
})

export const input = style({
  width: '100%',
  padding: '12px 14px',
  borderRadius: '10px',
  border: '1.5px solid #dbeafe',
  background: '#f0f7ff',
  fontSize: '15px',
  color: '#1e3a5f',
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
})

export const errorBox = style({
  padding: '10px 14px',
  borderRadius: '8px',
  background: '#fef2f2',
  border: '1px solid #fecaca',
  color: '#dc2626',
  fontSize: '13px',
})

export const submitBtn = style({
  padding: '13px',
  borderRadius: '10px',
  border: 'none',
  background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
  color: '#fff',
  fontSize: '15px',
  fontWeight: 700,
  cursor: 'pointer',
  boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)',
})

export const submitBtnLoading = style({
  background: '#93c5fd',
  cursor: 'not-allowed',
})

export const credHint = style({
  marginTop: '16px',
  padding: '10px 12px',
  borderRadius: '8px',
  background: '#f0f7ff',
  border: '1px dashed #93c5fd',
})

export const credHintLabel = style({
  margin: 0,
  fontSize: '12px',
  color: '#475569',
  fontWeight: 600,
})

export const credHintValue = style({
  margin: '2px 0 0',
  fontSize: '12px',
  color: '#64748b',
  fontFamily: 'monospace',
})

export const footer = style({
  textAlign: 'center',
  color: '#94a3b8',
  fontSize: '12px',
  marginTop: '20px',
})

export const footerBrand = style({
  color: '#2563eb',
  fontWeight: 600,
})
