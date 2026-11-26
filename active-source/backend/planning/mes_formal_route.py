"""Exact formal immutable operation DAG for the shared custody proof reader."""
from copy import deepcopy
from .work_order_execution_service import _verify
from .services import PlanningBusinessError

def route_nodes(order):
    operations,_=_verify(order);nodes={}
    for op in operations:
        row=deepcopy(op.source_snapshot);step=op.effective_step
        applicability=row['frozenStep'].get('applicability',{})
        if applicability.get('result') not in ('REQUIRED','NOT_APPLICABLE'):
            raise PlanningBusinessError('MES_FORMAL_ROUTE_DECISION_UNPROVEN','本接续仅消费已核实必经正式工序；未将未知适用性当作必经或跳过。',http_status=409)
        row.update(stepId=op.effective_step_id,decision=applicability['result'],decisionBasis=deepcopy(applicability))
        nodes[op.sequence]={'frozenPredecessors':deepcopy(row['predecessorSequences']),
            'currentPredecessors':deepcopy(step.predecessor_sequences),'active':step.is_active,
            'versionId':step.routing_version_id,'expectedVersionId':op.effective_routing_version_id,
            'operationId':step.operation_id,'expectedOperationId':op.operation_id,'row':row}
    return nodes
