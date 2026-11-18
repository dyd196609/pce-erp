from django.db import migrations
CODE='procurement.price_approval_preparation.review'
def register(apps,schema_editor):
    Permission=apps.get_model('system','Permission')
    row,created=Permission.objects.get_or_create(code=CODE,defaults={'name':'核价准备审核','module':'SCM'})
    if not created and (row.name!='核价准备审核' or row.module!='SCM'):
        raise RuntimeError('PREPARATION_REVIEW_PERMISSION_CONFLICT')
def reverse(apps,schema_editor):
    if apps.get_model('system','RolePermission').objects.filter(permission__code=CODE).exists():
        raise RuntimeError('PREPARATION_REVIEW_PERMISSION_STILL_ASSIGNED')
    apps.get_model('system','Permission').objects.filter(code=CODE).delete()
class Migration(migrations.Migration):
    dependencies=[('procurement','0095_quote_comparison_register_permission')]
    operations=[migrations.RunPython(register,reverse)]
