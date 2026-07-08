const schemaState = {
  agents: [],
  workflows: [],
  rules: [],
}

export function mutateStructure(event) {
  switch (event.type) {
    case 'STRUCTURE_EXTENSION':
      schemaState.agents.push('DYNAMIC_AGENT')
      break

    case 'AGENT_RECONFIG':
      schemaState.agents = schemaState.agents.reverse()
      break

    case 'KERNEL_EVOLUTION':
      schemaState.rules.push('SELF_EVOLVING_RULE')
      break
  }

  return schemaState
}

export function getStructureState() {
  return schemaState
}
