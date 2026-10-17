import path from 'node:path'
import { loadOrCompileStory } from '@cycle-master/story-schema'
import { GameDatabase } from './database.ts'
import { GameService } from './service.ts'
import { createApp } from './app.ts'

const projectRoot = process.env.PROJECT_ROOT ?? path.resolve()
const sourceRoot = process.env.STORY_SOURCE_ROOT ?? path.join(projectRoot, 'content/story_v3')
const buildRoot = process.env.STORY_BUILD_ROOT ?? path.join(projectRoot, 'content/build')
const databaseFile = process.env.DATABASE_FILE ?? path.join(projectRoot, 'data/cycle-master.db')
const port = Number(process.env.PORT ?? 8000)
const host = process.env.HOST ?? '0.0.0.0'

async function main(): Promise<void> {
  const story = await loadOrCompileStory(sourceRoot, buildRoot, true)
  const database = new GameDatabase(databaseFile)
  const service = new GameService(story, database)
  const app = createApp(service, path.join(projectRoot, 'content/assets'))
  const server = app.listen(port, host, () => {
    console.log(`Cycle Master API listening on http://${host}:${port}`)
  })
  const shutdown = (): void => {
    server.close(() => database.close())
  }
  process.once('SIGINT', shutdown)
  process.once('SIGTERM', shutdown)
}

main().catch(error => {
  console.error(error)
  process.exit(1)
})
