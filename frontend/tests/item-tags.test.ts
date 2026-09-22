import { describe, it, expect } from 'vitest'
import type { Item } from '@/lib/types'
import {
  applyItemUpdate,
  changedTags,
  editableTagsFromItem,
  withCurrent,
  type EditableTags,
} from '@/lib/item-tags'

function item(overrides: Partial<Item> = {}): Item {
  return {
    id: 'i1',
    type: 'blazer',
    colors: ['navy'],
    pattern: 'solid',
    material: 'wool',
    style: ['classic'],
    season: ['fall'],
    formality: 'casual',
    tags: {
      colors: ['navy'],
      pattern: 'solid',
      material: 'wool',
      style: ['classic'],
      season: ['fall'],
      formality: 'casual',
      fit: 'slim',
    },
    ...overrides,
  } as Item
}

const base: EditableTags = {
  formality: 'casual',
  pattern: 'solid',
  material: 'wool',
  fit: 'slim',
  colors: ['navy'],
  style: ['classic'],
  season: ['fall'],
}

describe('editableTagsFromItem', () => {
  it('reads the columns, because suggestion scoring does', () => {
    // The tags JSON disagrees here, as it can on items re-analysed before the
    // backend kept both in step.
    const stale = item({ tags: { ...item().tags, formality: 'formal', colors: ['black'] } })

    expect(editableTagsFromItem(stale)).toEqual(base)
  })

  it('takes fit from the tags JSON, which is the only place it lives', () => {
    expect(editableTagsFromItem(item()).fit).toBe('slim')
  })

  it('falls back to the JSON when the response has no tag columns', () => {
    const old = item({
      pattern: undefined,
      material: undefined,
      style: undefined,
      season: undefined,
      formality: undefined,
    })

    expect(editableTagsFromItem(old)).toEqual(base)
  })
})

describe('changedTags', () => {
  it('is undefined when nothing changed, so tags are left out of the request', () => {
    expect(changedTags(base, { ...base })).toBeUndefined()
  })

  it('ignores list order', () => {
    const before = { ...base, season: ['fall', 'winter'] }
    expect(changedTags(before, { ...before, season: ['winter', 'fall'] })).toBeUndefined()
  })

  it('returns only the changed tags, with null for a cleared one', () => {
    expect(changedTags(base, { ...base, formality: 'smart-casual', material: null })).toEqual({
      formality: 'smart-casual',
      material: null,
    })
  })
})

describe('applyItemUpdate', () => {
  it('merges tags instead of replacing them, and mirrors them into the columns', () => {
    const next = applyItemUpdate(item(), { tags: { formality: 'formal' } })

    expect(next.tags.formality).toBe('formal')
    expect(next.tags.colors).toEqual(['navy'])
    expect(next.tags.fit).toBe('slim')
    expect(next.formality).toBe('formal')
    expect(next.pattern).toBe('solid')
  })

  it('leaves tags alone for an update without them', () => {
    const before = item()
    const next = applyItemUpdate(before, { name: 'Blazer' })

    expect(next.name).toBe('Blazer')
    expect(next.tags).toBe(before.tags)
  })
})

describe('withCurrent', () => {
  it('keeps a current value that is not among the options', () => {
    expect(withCurrent(['tan', 'navy'], 'khaki')).toEqual(['tan', 'navy', 'khaki'])
    expect(withCurrent(['tan'], ['tan', 'teal'])).toEqual(['tan', 'teal'])
  })

  it('returns the options unchanged otherwise', () => {
    const options = ['tan', 'navy']
    expect(withCurrent(options, 'tan')).toBe(options)
    expect(withCurrent(options, null)).toBe(options)
  })
})
