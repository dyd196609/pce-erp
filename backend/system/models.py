"""
PCE 用户模型（对应数据库 user 表）
"""
import threading
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('用户名必须提供')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('company_id', 1)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField('登录账号', max_length=50, unique=True)
    real_name = models.CharField('真实姓名', max_length=50)
    email = models.EmailField('邮箱', blank=True, null=True)
    mobile = models.CharField('手机号', max_length=20, blank=True, null=True)
    company_id = models.BigIntegerField('所属公司ID')
    is_active = models.BooleanField('是否启用', default=True)
    is_staff = models.BooleanField('是否员工', default=False)
    last_login = models.DateTimeField('最后登录时间', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['real_name']

    objects = UserManager()

    class Meta:
        db_table = 'user_system'
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return f"{self.username}({self.real_name})"


class Company(models.Model):
    name = models.CharField('公司名称', max_length=100, unique=True)
    code = models.CharField('公司编码', max_length=20, unique=True)
    address = models.CharField('地址', max_length=200, blank=True)
    contact = models.CharField('联系人', max_length=50, blank=True)
    phone = models.CharField('联系电话', max_length=20, blank=True)
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        verbose_name = "公司"
        verbose_name_plural = "公司"

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField('部门名称', max_length=100)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True,
                               blank=True, related_name='children', verbose_name='上级部门')
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='departments', verbose_name='所属公司')
    code = models.CharField('部门编码', max_length=20, blank=True)
    manager = models.CharField('负责人', max_length=50, blank=True)
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        verbose_name = "部门"
        verbose_name_plural = "部门"
        unique_together = [['name', 'company']]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class Workshop(models.Model):
    name = models.CharField('车间名称', max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE,
                                   null=True, blank=True, related_name='workshops', verbose_name='所属部门')
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='workshops', verbose_name='所属公司')
    code = models.CharField('车间编码', max_length=20, blank=True)
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        verbose_name = "车间"
        verbose_name_plural = "车间"

    def __str__(self):
        return f"{self.department.name if self.department else self.company.name} - {self.name}"


class Team(models.Model):
    name = models.CharField('班组名称', max_length=100)
    workshop = models.ForeignKey(
        Workshop, on_delete=models.CASCADE, related_name='teams', verbose_name='所属车间')
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, null=True, blank=True, verbose_name='所属部门')
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='teams', verbose_name='所属公司')
    code = models.CharField('班组编码', max_length=20, blank=True)
    leader = models.CharField('班组长', max_length=50, blank=True)
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        verbose_name = "班组"
        verbose_name_plural = "班组"

    def __str__(self):
        return f"{self.workshop.name} - {self.name}"


class Process(models.Model):
    name = models.CharField('工序名称', max_length=100)
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='processes', verbose_name='所属班组')
    code = models.CharField('工序编码', max_length=20, blank=True)
    description = models.TextField('描述', blank=True)
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        verbose_name = "工序"
        verbose_name_plural = "工序"

    def __str__(self):
        return f"{self.team.name} - {self.name}"


class Position(models.Model):
    name = models.CharField('岗位名称', max_length=100, unique=True)
    code = models.CharField('岗位编码', max_length=20, unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属部门')
    workshop = models.ForeignKey(
        Workshop, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属车间')
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属班组')
    process = models.ForeignKey(
        Process, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属工序')
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='positions', verbose_name='所属公司')
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, null=True, blank=True, verbose_name='权限组')
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        verbose_name = "岗位"
        verbose_name_plural = "岗位"

    def __str__(self):
        return f"{self.name} ({self.code})"


# @receiver(pre_save, sender=Position)
# def handle_position_group(sender, instance, **kwargs):
#     """在保存 Position 之前，自动关联或创建 Group"""
#     if instance.is_active:
#         group_name = f"pos_{instance.code}"
#         group, _ = Group.objects.get_or_create(name=group_name)
#         if instance.group_id != group.id:
#             instance.group = group
#     else:
#         # 如果停用，断开与 Group 的关联（Group 保留，不自动删除）
#         if instance.group_id:
#             instance.group = None


# @receiver(post_delete, sender=Position)
# def delete_orphan_group(sender, instance, **kwargs):
#     """删除 Position 时，如果关联的 Group 没有其他 Position 使用，则删除（可选）"""
#     if instance.group and not Position.objects.filter(group=instance.group).exclude(pk=instance.pk).exists():
#         instance.group.delete()
