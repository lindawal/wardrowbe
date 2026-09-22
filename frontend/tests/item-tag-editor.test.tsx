import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ItemTagEditor } from '@/components/item-tag-editor'
import type { EditableTags } from '@/lib/item-tags'
import type { TagOptions } from '@/lib/types'

const options: TagOptions = {
  colors: ['navy', 'white'],
  patterns: ['solid', 'striped'],
  materials: ['cotton', 'wool'],
  formality: ['casual', 'formal'],
  styles: ['classic', 'modern'],
  seasons: ['summer', 'winter'],
  fits: ['regular', 'slim'],
}

const value: EditableTags = {
  formality: 'casual',
  pattern: 'solid',
  material: null,
  fit: null,
  colors: ['navy'],
  style: [],
  // Set before the editor offered only tagger values; must still show.
  season: ['monsoon'],
}

function setup() {
  const onChange = vi.fn()
  render(
    <ItemTagEditor
      value={value}
      onChange={onChange}
      options={options}
      describeColor={(c) => ({ name: `color:${c}` })}
    />
  )
  // next-intl is mocked to echo the key, so group labels are key names.
  const group = (label: string) => screen.getByRole('group', { name: label })
  return { onChange, group }
}

describe('ItemTagEditor', () => {
  it('offers every tagger value as a toggle, marking the selected ones', () => {
    const { group } = setup()

    const styles = within(group('style')).getAllByRole('button')
    expect(styles.map((b) => b.textContent)).toEqual(['classic', 'modern'])
    expect(styles.every((b) => b.getAttribute('aria-pressed') === 'false')).toBe(true)

    const navy = within(group('colors')).getByRole('button', { name: 'color:navy' })
    expect(navy.getAttribute('aria-pressed')).toBe('true')
  })

  it('adds a value on click', () => {
    const { onChange, group } = setup()

    fireEvent.click(within(group('style')).getByRole('button', { name: 'modern' }))

    expect(onChange).toHaveBeenCalledWith({ ...value, style: ['modern'] })
  })

  it('removes a selected value on click', () => {
    const { onChange, group } = setup()

    fireEvent.click(within(group('colors')).getByRole('button', { name: 'color:navy' }))

    expect(onChange).toHaveBeenCalledWith({ ...value, colors: [] })
  })

  it('keeps a current value that is outside the offered ones', () => {
    const { group } = setup()

    const monsoon = within(group('season')).getByRole('button', { name: 'monsoon' })
    expect(monsoon.getAttribute('aria-pressed')).toBe('true')
  })
})
