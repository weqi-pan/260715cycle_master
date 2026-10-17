import { describe, expect, it } from 'vitest'
import path from 'node:path'
import { canonicalJsonBytes, snapshotRevisionWithoutRevision, StoryCompiler } from '../packages/story-schema/src/index'

const sourceRoot = path.resolve('content/story_v3')

describe('StoryCompiler', () => {
  it('compiles the migrated Story v3 source without errors', () => {
    const compilation = new StoryCompiler().compile(sourceRoot)
    expect(compilation.diagnostics.filter(item => item.severity === 'error')).toEqual([])
    expect(compilation.snapshot).toBeTruthy()
    expect(Object.keys(compilation.snapshot!.nodes)).toHaveLength(30)
  })

  it('produces a revision from canonical JSON, independent of key order and whitespace', () => {
    const snapshot = new StoryCompiler().compile(sourceRoot).snapshot!
    const withoutRevision = { ...snapshot }
    delete (withoutRevision as Record<string, unknown>).revision
    const first = snapshotRevisionWithoutRevision(withoutRevision)
    const cloned = JSON.parse(JSON.stringify(withoutRevision)) as typeof withoutRevision
    expect(canonicalJsonBytes(cloned).equals(canonicalJsonBytes(withoutRevision))).toBe(true)
    expect(snapshotRevisionWithoutRevision(cloned)).toBe(first)
  })
})
