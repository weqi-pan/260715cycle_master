import {
  ChooseRequestSchema, DiscardRequestSchema, FrameSchema, ResumeRequestSchema,
  SaveCreateRequestSchema, SaveUpdateRequestSchema,
  type Frame, type SaveMetadata, type SaveSummary,
} from '@cycle-master/api-contract'

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly details?: unknown) {
    super(message)
    this.name = 'ApiError'
    if (details !== undefined) this.details = details
  }
}

async function request<T>(path: string, method: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, body === undefined
      ? { method }
      : { method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  } catch (error) {
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接服务器，请检查后端后手动读档或重新开始。')
  }
  const payload = await response.json().catch(() => ({ error: { code: 'INVALID_RESPONSE', message: '服务器响应无效。' } }))
  if (!response.ok) {
    const error = (payload as { error?: { code?: string; message?: string; details?: unknown } }).error
    throw new ApiError(response.status, error?.code ?? 'UNKNOWN_ERROR', error?.message ?? '请求失败。', error?.details)
  }
  return payload as T
}

export const gameApi = {
  health: () => request<{ status: string }>('/api/health', 'GET'),
  start: async (): Promise<Frame> => FrameSchema.parse(await request<unknown>('/api/game/start', 'POST')),
  resume: async (saveId: string): Promise<Frame> => {
    return FrameSchema.parse(await request<unknown>('/api/game/resume', 'POST', ResumeRequestSchema.parse({ saveId })))
  },
  choose: async (input: { nodeId: string; choiceId: string; turnId: string }): Promise<Frame> => {
    return FrameSchema.parse(await request<unknown>('/api/game/choose', 'POST', ChooseRequestSchema.parse(input)))
  },
  discard: async (input: { itemId: string; turnId: string }): Promise<Frame> => {
    return FrameSchema.parse(await request<unknown>('/api/game/inventory/discard', 'POST', DiscardRequestSchema.parse(input)))
  },
  listSaves: () => request<{ saves: SaveSummary[] }>('/api/saves', 'GET'),
  createSave: (name: string, turnId: string) => request('/api/saves', 'POST', SaveCreateRequestSchema.parse({ name, turnId })),
  updateSave: (saveId: string, turnId: string, name?: string) => {
    return request(`/api/saves/${encodeURIComponent(saveId)}`, 'PUT', SaveUpdateRequestSchema.parse({ turnId, ...(name ? { name } : {}) }))
  },
  saveMetadata: (saveId: string): Promise<SaveMetadata> => request(`/api/saves/${encodeURIComponent(saveId)}`, 'GET'),
  deleteSave: (saveId: string) => request(`/api/saves/${encodeURIComponent(saveId)}`, 'DELETE'),
}
