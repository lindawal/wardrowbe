import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import HelpPage from '@/app/dashboard/help/page'

describe('HelpPage', () => {
  it('renders the German help', () => {
    render(<HelpPage />)
    expect(screen.getByRole('heading', { level: 1, name: 'Hilfe' })).toBeTruthy()
  })

  // A renamed or removed section would otherwise leave a table-of-contents link
  // that silently scrolls nowhere.
  it('has a target for every in-page link', () => {
    const { container } = render(<HelpPage />)
    const anchors = Array.from(container.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'))

    expect(anchors.length).toBeGreaterThan(0)
    for (const a of anchors) {
      const id = a.getAttribute('href')!.slice(1)
      expect(container.querySelector(`[id="${id}"]`), `no section for ${a.getAttribute('href')}`).not.toBeNull()
    }
  })
})
