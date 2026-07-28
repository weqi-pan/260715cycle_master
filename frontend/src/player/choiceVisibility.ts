interface ChoiceEntry {
  id: string
  text: string
  next_node_id: string
  available: boolean
}

/** The backend authors visibility; this only rejects malformed response entries. */
export function visibleChoices<T extends ChoiceEntry>(choices: readonly T[]): T[] {
  return choices.filter(choice => Boolean(
    choice.id
    && choice.text
    && choice.next_node_id
    && typeof choice.available === 'boolean',
  ))
}
