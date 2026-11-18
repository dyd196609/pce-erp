from django.db import migrations
CODE='procurement.price_confirmation.confirm'
def register(apps,schema_editor):
 row,created=apps.get_model('system','Permission').objects.get_or_create(code=CODE,defaults={'name':'正式价格确认及登记','module':'SCM'})
 if not created and (row.name!='正式价格确认及登记' or row.module!='SCM'):raise RuntimeError('FORMAL_PRICE_PERMISSION_CONFLICT')
def reverse(apps,schema_editor):
 if apps.get_model('system','RolePermission').objects.filter(permission__code=CODE).exists():raise RuntimeError('FORMAL_PRICE_PERMISSION_STILL_ASSIGNED')
 apps.get_model('system','Permission').objects.filter(code=CODE).delete()
class Migration(migrations.Migration):
 dependencies=[('procurement','0096_price_preparation_review_permission')]
 operations=[migrations.RunPython(register,reverse)]
