import type { ChoiceView } from '@cycle-master/api-contract'

export function visibleChoices(choices: readonly ChoiceView[]): ChoiceView[] {
  return choices.filter(choice => Boolean(choice.id && choice.text && choice.nextNodeId && typeof choice.available === 'boolean'))
}

export function orderedChoices(choices: readonly ChoiceView[]): ChoiceView[] {
  return [...visibleChoices(choices)].sort((left, right) => Number(right.available) - Number(left.available) || left.text.localeCompare(right.text, 'zh-Hans-CN'))
}
