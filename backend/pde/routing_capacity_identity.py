"""Resolve the formally declared routing subject; missing identity never defaults."""
def routing_capacity_identity(route,company_id):
    if not route or route.company_id!=company_id or not route.is_active:
        return None,None
    if route.applicability_scope=='ORDER_ENGINEERING':
        instance=route.order_engineering_instance
        if (not instance or instance.company_id!=company_id or instance.status=='inactive'
                or not instance.product_category_id or not instance.selected_process_type_id
                or not instance.product_category.is_active or not instance.selected_process_type.is_active
                or (route.manufacturing_process_type_id and route.manufacturing_process_type_id!=instance.selected_process_type_id)):
            return None,None
        return instance.product_category_id,instance.selected_process_type_id
    return route.product_category_id,route.manufacturing_process_type_id


def routing_capacity_key(route,company_id):
    category_id,process_id=routing_capacity_identity(route,company_id)
    code=route.routing_code if route else ''
    if route and route.applicability_scope=='ORDER_ENGINEERING':
        from .models import CapacityProductType
        kinds=list(CapacityProductType.objects.filter(company_id=company_id,is_active=True,
            product_category_id=category_id,manufacturing_process_type_id=process_id)) if category_id and process_id else []
        code=kinds[0].code if len(kinds)==1 else None
    return code,category_id,process_id
