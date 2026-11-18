from django.db import models
from django.conf import settings
from .operation_handover_models import HandoverRecord

class ProductionFinishedGoodsTransfer(HandoverRecord):
    """Whole-order native completion evidence plus one explicit finished batch."""
    no=models.CharField(max_length=80,unique=True)
    work_order=models.ForeignKey('planning.ProductionWorkOrder',on_delete=models.PROTECT,related_name='finished_goods_transfers')
    task=models.ForeignKey('planning.ProductionWorkshopTask',on_delete=models.PROTECT)
    material=models.ForeignKey('masterdata.Material',on_delete=models.PROTECT)
    quantity=models.CharField(max_length=100)
    uom=models.ForeignKey('masterdata.UnitOfMeasure',on_delete=models.PROTECT)
    warehouse=models.ForeignKey('procurement.Warehouse',on_delete=models.PROTECT)
    location=models.ForeignKey('procurement.WarehouseLocation',on_delete=models.PROTECT)
    receiver=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    sender_employee=models.ForeignKey('pfm.Employee',null=True,on_delete=models.PROTECT,related_name='+')
    receiver_employee=models.ForeignKey('pfm.Employee',null=True,on_delete=models.PROTECT,related_name='+')
    dispatched_at=models.DateTimeField(null=True)
    data=models.JSONField(default=dict)
    class Meta:
        db_table='planning_finished_goods_transfer'
        default_permissions=()
        constraints=[models.CheckConstraint(condition=models.Q(status__in=('prepared','in_transit','received','cancelled')),name='fg_transfer_status'),
            models.UniqueConstraint(fields=['company','work_order'],condition=models.Q(status__in=('prepared','in_transit','received')),name='fg_one_effective_whole_batch')]
