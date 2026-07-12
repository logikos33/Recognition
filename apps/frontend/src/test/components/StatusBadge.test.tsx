import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from '../../components/shared/StatusBadge'

describe('StatusBadge', () => {
  it('renders active status translated to pt-BR', () => {
    render(<StatusBadge status="active" />)
    expect(screen.getByText('Ativo')).toBeDefined()
  })

  it('renders error status translated to pt-BR', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText('Erro')).toBeDefined()
  })

  it('keeps the raw status key in the title attribute for debugging', () => {
    render(<StatusBadge status="active" />)
    expect(screen.getByTitle('active')).toBeDefined()
  })

  it('falls back to humanized label for unknown status', () => {
    render(<StatusBadge status="weird_status" />)
    expect(screen.getByText('Weird status')).toBeDefined()
  })
})
