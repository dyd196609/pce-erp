from django.apps import AppConfig


class BankSendTaskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bank_send_task"
    verbose_name = "银行发送任务"
