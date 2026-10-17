import path from 'node:path'
import { loadOrCompileStory } from '../index.ts'

const strict = process.argv.includes('--strict')
const rootIndex = process.argv.indexOf('--source-root')
const buildIndex = process.argv.indexOf('--build-root')
const projectRoot = path.resolve(process.cwd())
const sourceRoot = rootIndex > 0 ? path.resolve(process.argv[rootIndex + 1]!) : path.join(projectRoot, 'content/story_v3')
const buildRoot = buildIndex > 0 ? path.resolve(process.argv[buildIndex + 1]!) : path.join(projectRoot, 'content/build')
loadOrCompileStory(sourceRoot, buildRoot, strict).then(snapshot => {
  console.log(`Story compiled: ${snapshot.revision}`)
}).catch(error => {
  console.error(error)
  process.exit(1)
})
