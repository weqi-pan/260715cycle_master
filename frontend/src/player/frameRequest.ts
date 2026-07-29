export interface FrameRequestOutcome<T> {
  frame: T | null
  error: unknown | null
}


export async function resolveFrameRequest<T>(
  currentFrame: T | null,
  request: () => Promise<T>,
): Promise<FrameRequestOutcome<T>> {
  try {
    return { frame: await request(), error: null }
  } catch (error: unknown) {
    return { frame: currentFrame, error }
  }
}
