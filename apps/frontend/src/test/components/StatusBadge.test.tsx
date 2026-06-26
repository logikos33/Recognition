import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from '../../components/shared/StatusBadge'

describe('StatusBadge', () => {
  it('renders active status text', () => {
    render(<StatusBadge status="active" />)
    expect(screen.getByText('active')).toBeDefined()
  })

  it('renders error status text', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText('error')).toBeDefined()
  })
})
