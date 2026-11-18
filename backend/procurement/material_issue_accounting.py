"""Validated issue consumption, never a second stock or quantity ledger."""
from decimal import Decimal
from .material_stock_authority import fail

def consumed(allocations):
 from .models import ProductionMaterialIssue
 from .material_issue_service import verify_issue
 ids=[a.pk for a in allocations];totals={i:Decimal('0') for i in ids}
 for row in ProductionMaterialIssue.objects.filter(allocation_id__in=ids).select_related('allocation__audit_record','audit_record','outbound_transaction','receipt_audit').order_by('pk'):
  verify_issue(row);totals[row.allocation_id]+=row.quantity
 for a in allocations:
  if totals[a.pk]>a.quantity:fail('MATERIAL_ISSUE_OCCUPANCY_CONFLICT','合法已发量超过原分配，保留历史及尚余占用待核。')
 return totals
