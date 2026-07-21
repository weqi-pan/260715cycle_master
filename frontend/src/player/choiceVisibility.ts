interface ChoiceAvailability {
  available: boolean
}

/** 后端是权威来源；前端仍防御性过滤旧响应中的锁定选项。 */
export function visibleChoices<T extends ChoiceAvailability>(choices: readonly T[]): T[] {
  return choices.filter(choice => choice.available)
}
