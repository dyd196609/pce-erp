"""Native iterative exact-edge/cycle validator, fact-shaped for formal or TEST source adapters."""
def validate_graph(by_sequence,target_sequence):
    colors = {}
    stack = [(target_sequence, False)]
    while stack:
        sequence, leaving = stack.pop()
        if leaving:
            colors[sequence] = 2
            continue
        if colors.get(sequence) == 1:
            return '正式路线前序依赖存在循环，不能开工。'
        if colors.get(sequence) == 2:
            continue
        operation = by_sequence.get(sequence)
        if operation is None:
            return '正式路线前序对象缺失，不能开工。'
        frozen = operation['frozenPredecessors']
        step = operation
        if (not isinstance(frozen, list) or any(type(value) is not int or value <= 0 for value in frozen)
                or len(frozen) != len(set(frozen)) or sequence in frozen
                or not step['active'] or step['versionId'] != operation['expectedVersionId']
                or step['operationId'] != operation['expectedOperationId'] or step['currentPredecessors'] != frozen):
            return '正式路线前序关系、有效步骤或冻结版本不一致。'
        colors[sequence] = 1
        stack.append((sequence, True))
        stack.extend((previous, False) for previous in reversed(frozen))
    return None
