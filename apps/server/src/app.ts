import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import { createReadStream, promises as fsPromises } from 'node:fs'
import path from 'node:path'
import type { ZodTypeAny } from 'zod'
import type { ApiErrorCode } from '@cycle-master/api-contract'
import { GameEngineError } from '@cycle-master/game-runtime'
import { GameService, HttpError } from './service.ts'

interface MatchedRoute {
  params: Record<string, string>
  pattern: RegExp
}

const routes = {
  gameStart: match('POST', '/api/game/start'),
  gameResume: match('POST', '/api/game/resume'),
  gameChoose: match('POST', '/api/game/choose'),
  discard: match('POST', '/api/game/inventory/discard'),
  savesCollection: match(['GET', 'POST'], '/api/saves'),
  saveItem: match(['GET', 'PUT', 'DELETE'], '/api/saves/:saveId'),
  health: match('GET', '/api/health'),
}

function match(method: string | string[], route: string): MatchedRoute {
  const methods = Array.isArray(method) ? method : [method]
  const patternSource = `^${route.replace(/:([A-Za-z][A-Za-z0-9_]*)/g, '(?<$1>[^/]+)')}$`
  return { pattern: new RegExp(patternSource), params: { __methods: methods.join(',') } }
}

function matched(route: MatchedOption | null, request: IncomingMessage, pathname: string): { params: Record<string, string> } | null {
  const matched = route?.pattern.exec(pathname)
  if (!matched || !route) return null
  if (!(route.params.__methods as string).split(',').includes(request.method ?? '')) return null
  return { params: matched.groups ?? {} }
}

type MatchedOption = MatchedRoute | null

function sendJson(response: ServerResponse, status: number, payload: unknown): void {
  const body = JSON.stringify(payload)
  response.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'access-control-allow-origin': '*',
  })
  response.end(body)
}

function sendError(response: ServerResponse, status: number, code: ApiErrorCode, message: string, details?: unknown): void {
  sendJson(response, status, details === undefined ? { error: { code, message } } : { error: { code, message, details } })
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  for await (const chunk of request) chunks.push(chunk as Buffer)
  if (!chunks.length) return {}
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'))
  } catch {
    throw new HttpError(400, 'VALIDATION_ERROR', '请求体必须是有效 JSON。')
  }
}

function parseBody<T>(schema: ZodTypeAny, payload: unknown): T {
  const result = schema.safeParse(payload)
  if (!result.success) {
    throw new HttpError(400, 'VALIDATION_ERROR', '请求参数无效。', result.error.issues)
  }
  return result.data as T
}

function runtimeError(error: GameEngineError): HttpError {
  const message = error.message
  const notFound = [
    'Unknown story node:', 'Unknown inventory item:', 'Unknown persistent item:', 'Unknown item:',
    'Item not in inventory:', "Node '", "Choice '", 'Target node \'',
  ]
  const conflict = ['State node mismatch:', 'Choice already selected', 'Terminal node has no exits:', 'Crossing interaction limit reached:', 'Missing entry attribute:']
  if (notFound.some(prefix => message.startsWith(prefix))) return new HttpError(404, 'NOT_FOUND', message)
  if (conflict.some(prefix => message.startsWith(prefix))) return new HttpError(409, 'GAME_RULE_ERROR', message)
  return new HttpError(400, 'GAME_RULE_ERROR', message)
}

export function createApp(service: GameService, assetRoot: string): Server {
  return createServer(async (request, response) => {
    const url = new URL(request.url ?? '/', 'http://localhost')
    const pathname = url.pathname

    try {
      if (request.method === 'OPTIONS') {
        response.writeHead(204, {
          'access-control-allow-origin': '*',
          'access-control-allow-methods': 'GET,POST,PUT,DELETE,OPTIONS',
          'access-control-allow-headers': 'content-type',
        }).end()
        return
      }

      const assetMatch = /^\/assets\/(?<file>.+)$/.exec(pathname)
      if (assetMatch?.groups?.file) {
        const relative = decodeURIComponent(assetMatch.groups.file)
        const target = path.resolve(assetRoot, relative)
        if (!target.startsWith(path.resolve(assetRoot) + path.sep)) throw new HttpError(403, 'VALIDATION_ERROR', '资源路径不允许。')
        const stat = await fsPromises.stat(target).catch(() => null)
        if (!stat?.isFile()) throw new HttpError(404, 'NOT_FOUND', '资源不存在。')
        response.writeHead(200, {
          'content-length': stat.size,
          'access-control-allow-origin': '*',
          'cache-control': 'public, max-age=3600',
        })
        createReadStream(target).pipe(response)
        return
      }

      const health = matched(routes.health, request, pathname)
      if (health) return sendJson(response, 200, service.health())

      const start = matched(routes.gameStart, request, pathname)
      if (start) return sendJson(response, 200, service.start())

      const resume = matched(routes.gameResume, request, pathname)
      if (resume) {
        const body = await readJson(request)
        const parsed = parseBody<{ saveId: string }>((await import('@cycle-master/api-contract')).ResumeRequestSchema, body)
        return sendJson(response, 200, service.resume(parsed.saveId))
      }

      const choose = matched(routes.gameChoose, request, pathname)
      if (choose) {
        const body = await readJson(request)
        const parsed = parseBody<{ nodeId: string; choiceId: string; turnId: string }>((await import('@cycle-master/api-contract')).ChooseRequestSchema, body)
        return sendJson(response, 200, service.choose(parsed.nodeId, parsed.choiceId, parsed.turnId))
      }

      const discard = matched(routes.discard, request, pathname)
      if (discard) {
        const body = await readJson(request)
        const parsed = parseBody<{ itemId: string; turnId: string }>((await import('@cycle-master/api-contract')).DiscardRequestSchema, body)
        return sendJson(response, 200, service.discard(parsed.itemId, parsed.turnId))
      }

      const saves = matched(routes.savesCollection, request, pathname)
      if (saves) {
        if (request.method === 'GET') return sendJson(response, 200, service.listSaves())
        const body = await readJson(request)
        const parsed = parseBody<{ name: string; turnId: string }>((await import('@cycle-master/api-contract')).SaveCreateRequestSchema, body)
        return sendJson(response, 200, service.createSave(parsed.name, parsed.turnId))
      }

      const save = matched(routes.saveItem, request, pathname)
      if (save) {
        const saveId = save.params.saveId!
        if (request.method === 'GET') return sendJson(response, 200, service.saveMetadata(saveId))
        if (request.method === 'DELETE') return sendJson(response, 200, service.deleteSave(saveId))
        const body = await readJson(request)
        const parsed = parseBody<{ turnId: string; name?: string }>((await import('@cycle-master/api-contract')).SaveUpdateRequestSchema, body)
        return sendJson(response, 200, service.updateSave(saveId, parsed.turnId, parsed.name))
      }

      return sendError(response, 404, 'NOT_FOUND', '接口不存在。')
    } catch (error) {
      if (error instanceof HttpError) {
        return sendError(response, error.status, error.code as ApiErrorCode, error.message, error.details)
      }
      if (error instanceof GameEngineError) {
        const mapped = runtimeError(error)
        return sendError(response, mapped.status, mapped.code as ApiErrorCode, mapped.message, mapped.details)
      }
      console.error(error)
      return sendError(response, 500, 'INTERNAL_ERROR', '服务器内部错误。')
    }
  })
}
