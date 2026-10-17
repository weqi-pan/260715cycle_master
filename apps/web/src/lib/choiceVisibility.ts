import type { ChoiceView } from '@cycle-master/api-contract'

export function visibleChoices(choices: readonly ChoiceView[]): ChoiceView[] {
  return choices.filter(choice => Boolean(
    choice.available
    && choice.id
    && choice.text
    && choice.nextNodeId
  ))
}

export function orderedChoices(choices: readonly ChoiceView[]): ChoiceView[] {
  return visibleChoices(choices)
}
