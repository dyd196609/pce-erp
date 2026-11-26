"""Persistent usage classification does not grant manufacturing eligibility."""
from django.core.exceptions import ValidationError

def calculation_purpose(record):
    if record.pk:
        previous=type(record).all_records.filter(pk=record.pk).values_list('usage_purpose',flat=True).first()
        if previous is not None: return previous
    if record.scope == 'test_business':
        from .test_calculation_persistence import validate_record_binding
        validate_record_binding(record)
        return 'TEST_BUSINESS'
    if record.scope == 'fact_extension' and record.origin_calculation_id:
        parent=record.origin_calculation
        fields=('company_id','source_record_id','sales_order_item_id','engineering_instance_id')
        if all(getattr(record,k) is not None and getattr(record,k)==getattr(parent,k) for k in fields):
            return parent.usage_purpose
    if record.scope == 'operation_requirement':
        snapshot=(record.trace or {}).get('sourceSnapshot',{})
        source=type(record).all_records.filter(pk=snapshot.get('sourceCalculationId')).first()
        fields=('company_id','source_record_id','sales_order_item_id','engineering_instance_id')
        if source and all(getattr(record,k) is not None and getattr(record,k)==getattr(source,k) for k in fields):
            return source.usage_purpose
    # Formal roots require existing formal source authority, not caller labels.
    if record.scope == 'order_engineering' and record.source_record_id and record.sales_order_item_id and record.engineering_instance_id:
        source=record.source_record; instance=record.engineering_instance
        if source.company_id==record.company_id==instance.company_id==record.sales_order_item.sales_order.company_id and source.status=='confirmed' and instance.source_record_id==source.pk and instance.sales_order_item_id==record.sales_order_item_id:
            return 'PRODUCTION_USE'
    return 'UNCLASSIFIED'
