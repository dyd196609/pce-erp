import hashlib
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


PROCESS_CODE = "SALES_ORDER_TO_SUPPLY_PLAN"
PERMISSIONS = (
    ("sales.order.view", "查看销售订单"),
    ("sales.order.create", "创建销售订单"),
    ("sales.order.confirm", "确认销售订单"),
    ("sales.order.generate_demand", "销售订单生成正式需求"),
)
NODES = (
    ("CREATE_SALES_ORDER", "创建销售订单", 10, "sales.order.create"),
    ("CONFIRM_SALES_ORDER", "确认销售订单", 20, "sales.order.confirm"),
    ("GENERATE_DEMAND", "生成正式需求", 30, "sales.order.generate_demand"),
)


def seed_sales_foundation(apps, schema_editor):
    Permission=apps.get_model("system","Permission"); Role=apps.get_model("system","Role")
    RolePermission=apps.get_model("system","RolePermission"); Position=apps.get_model("system","Position")
    Responsibility=apps.get_model("system","Responsibility"); Mapping=apps.get_model("system","PositionWorkflowResponsibility")
    Company=apps.get_model("system","Company"); Customer=apps.get_model("sales","Customer")
    Process=apps.get_model("workflow_runtime","ProcessDefinition"); Node=apps.get_model("workflow_runtime","WorkflowNodeDefinition")
    role,_=Role.objects.update_or_create(code="sales_order_operator",defaults={"name":"销售订单执行员","description":"销售订单创建、确认及需求生成最小执行角色"})
    for code,name in PERMISSIONS:
        permission,_=Permission.objects.update_or_create(code=code,defaults={"name":name,"module":"SALES"})
        RolePermission.objects.get_or_create(role=role,permission=permission)
    digest=hashlib.sha256("|".join(f"{a}:{b}:{c}" for a,b,c in [(x[0],x[2],x[3]) for x in NODES]).encode()).hexdigest()
    process,_=Process.objects.update_or_create(definition_code=PROCESS_CODE,defaults={"definition_name":"销售订单至供应计划主链","business_domain":"SALES/PLAN","description":"销售订单确认后生成正式需求，并由现有计划引擎形成供应计划。","document_type":"SalesOrder","version":1,"active":True,"definition_hash":digest})
    position=Position.objects.filter(code="YXB-SALES",is_active=True).first()
    responsibility=Responsibility.objects.filter(code="RESP_SALES_ORDER_002",is_active=True).first()
    for node_code,node_name,sequence,action_code in NODES:
        node,_=Node.objects.update_or_create(process_definition=process,node_code=node_code,defaults={"node_name":node_name,"sequence":sequence,"business_action_code":action_code,"active":True,"description":"PCE订单驱动计划 V1.0 最小正式节点"})
        if position and responsibility:
            Mapping.objects.update_or_create(position=position,workflow_code=PROCESS_CODE,node_code=node_code,ownership_type="OWNER",defaults={"responsibility":responsibility,"workflow_node":node,"active":True})
    company=Company.objects.order_by("pk").first()
    if company:
        Customer.objects.update_or_create(company=company,code="CUST-PCE-ACCEPT-001",defaults={"name":"PCE系统流程验收客户","is_active":True,"acceptance_marker":"PCE-SO-PLAN-V1.0 / TEST"})


class Migration(migrations.Migration):
    initial=True
    dependencies=[("masterdata","0007_supplier_material_price_manual_source_r5"),("system","0010_positionworkflowresponsibility_workflow_node"),("workflow_runtime","0006_merge_formal_definitions_and_payment_backfill"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="Customer",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("code",models.CharField(max_length=40)),("name",models.CharField(max_length=120)),("is_active",models.BooleanField(default=True)),("acceptance_marker",models.CharField(blank=True,default="",max_length=120)),("created_at",models.DateTimeField(auto_now_add=True)),("company",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="sales_customers",to="system.company"))],options={"db_table":"sales_customer","ordering":["code"]}),
        migrations.CreateModel(name="SalesOrder",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("order_no",models.CharField(max_length=80,unique=True)),("order_date",models.DateField()),("required_delivery_date",models.DateField()),("currency",models.CharField(default="CNY",max_length=8)),("status",models.CharField(choices=[("draft","草稿"),("confirmed","已确认"),("closed","已关闭"),("cancelled","已取消")],max_length=20)),("version",models.PositiveIntegerField(default=1)),("acceptance_marker",models.CharField(blank=True,default="",max_length=120)),("remark",models.CharField(blank=True,default="",max_length=300)),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),("company",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="sales_orders",to="system.company")),("department",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="sales_orders",to="system.department")),("customer",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="sales_orders",to="sales.customer")),("created_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="created_sales_orders",to=settings.AUTH_USER_MODEL)),("confirmed_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="confirmed_sales_orders",to=settings.AUTH_USER_MODEL))],options={"db_table":"sales_order","ordering":["-id"]}),
        migrations.CreateModel(name="SalesOrderItem",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("line_no",models.PositiveIntegerField()),("quantity",models.DecimalField(decimal_places=4,max_digits=18)),("unit_price",models.DecimalField(decimal_places=4,default=0,max_digits=18)),("required_date",models.DateField()),("material",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="sales_order_items",to="masterdata.material")),("sales_order",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="items",to="sales.salesorder"))],options={"db_table":"sales_order_item","ordering":["sales_order_id","line_no"]}),
        migrations.AddConstraint(model_name="customer",constraint=models.UniqueConstraint(fields=("company","code"),name="uniq_sales_customer_company_code")),
        migrations.AddConstraint(model_name="salesorderitem",constraint=models.UniqueConstraint(fields=("sales_order","line_no"),name="uniq_sales_order_line")),
        migrations.AddConstraint(model_name="salesorderitem",constraint=models.CheckConstraint(condition=models.Q(("quantity__gt",0)),name="sales_order_item_qty_positive")),
        migrations.RunPython(seed_sales_foundation,migrations.RunPython.noop),
    ]
