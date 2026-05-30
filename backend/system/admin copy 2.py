import pandas as pd
from django import forms
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import render, redirect
from .models import Company, Department, Workshop, Team, Process, Position, User

# 注意：User 模型将在后面通过自定义 UserAdmin 注册，此处不注册
admin.site.register(Company)
admin.site.register(Department)
admin.site.register(Workshop)
admin.site.register(Team)
admin.site.register(Process)
admin.site.register(Position)


# ==================== 导入视图 ====================
@staff_member_required
def import_org_view(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            xls = pd.ExcelFile(excel_file)

            if '公司' in xls.sheet_names:
                df = pd.read_excel(excel_file, sheet_name='公司')
                for _, row in df.iterrows():
                    Company.objects.update_or_create(
                        code=row['公司编码'],
                        defaults={
                            'name': row['公司名称'],
                            'address': row.get('地址', ''),
                            'contact': row.get('联系人', ''),
                            'phone': row.get('电话', ''),
                            'is_active': True
                        }
                    )
                messages.success(request, '公司数据导入成功')

            if '部门' in xls.sheet_names:
                df = pd.read_excel(excel_file, sheet_name='部门')
                company_map = {c.code: c for c in Company.objects.all()}
                dept_map = {}
                for _, row in df.iterrows():
                    code = row['部门编码']
                    company = company_map.get(row['公司编码'])
                    if not company:
                        messages.warning(
                            request, f'公司 {row["公司编码"]} 不存在，跳过部门 {code}')
                        continue
                    dept, _ = Department.objects.update_or_create(
                        code=code,
                        defaults={
                            'name': row['部门名称'],
                            'company': company,
                            'manager': row.get('负责人', ''),
                            'is_active': True
                        }
                    )
                    dept_map[code] = dept
                for _, row in df.iterrows():
                    code = row['部门编码']
                    parent_code = row.get('父级编码')
                    if parent_code and pd.notna(parent_code) and parent_code:
                        dept = dept_map.get(code)
                        parent = dept_map.get(parent_code)
                        if dept and parent:
                            dept.parent = parent
                            dept.save()
                messages.success(request, '部门数据导入成功')

            if '岗位' in xls.sheet_names:
                df = pd.read_excel(excel_file, sheet_name='岗位')
                for _, row in df.iterrows():
                    # 1. 处理 Group（保持不变）
                    group_name = f"{row['岗位编码']} - {row['岗位名称']}"
                    group, _ = Group.objects.get_or_create(name=group_name)
                    perms_str = row.get('权限代码列表')
                    if perms_str and pd.notna(perms_str):
                        perm_codes = [p.strip() for p in perms_str.split(',')]
                        perms = []
                        for code in perm_codes:
                            try:
                                perm = Permission.objects.get(codename=code)
                                perms.append(perm)
                            except Permission.DoesNotExist:
                                messages.warning(request, f'权限 {code} 不存在，跳过')
                        group.permissions.set(perms)

                    # 2. 处理 Position（新增）
                    position_code = str(row['岗位编码']).strip()
                    position_name = str(row['岗位名称']).strip()
                    company_code = str(row.get('公司编码', '')).strip()
                    dept_code = str(row.get('部门编码', '')).strip()

                    if company_code and dept_code:
                        try:
                            company = Company.objects.get(code=company_code)
                            department = Department.objects.get(
                                code=dept_code, company=company)
                        except Company.DoesNotExist:
                            messages.warning(
                                request, f'岗位 {position_code} 对应的公司编码 {company_code} 不存在，跳过')
                            continue
                        except Department.DoesNotExist:
                            messages.warning(
                                request, f'岗位 {position_code} 对应的部门编码 {dept_code} 在公司的 {company_code} 下不存在，跳过')
                            continue

                        # 获取权限字符串（可选）
                        perm_codes_str = perms_str if pd.notna(
                            perms_str) else ''

                        # 更新或创建 Position
                        Position.objects.update_or_create(
                            code=position_code,
                            defaults={
                                'name': position_name,
                                'department': department,
                                'company': company,
                                'permission_codes': perm_codes_str,
                                'is_active': True  # 根据你的模型需求调整
                            }
                        )
                    else:
                        messages.warning(
                            request, f'岗位 {position_code} 缺少公司编码或部门编码，跳过创建 Position')

                messages.success(request, '岗位数据导入成功')


# ==================== 自定义 Group 表单 ====================
class GroupForm(forms.ModelForm):
    name = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        label='岗位名称',
        to_field_name='name',
        help_text='请从已有岗位中选择'
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']

    def save(self, commit=True):
        group = super().save(commit=False)
        group.name = self.cleaned_data['name'].name
        if commit:
            group.save()
            self.save_m2m()
        return group


class GroupAdmin(admin.ModelAdmin):
    form = GroupForm
    list_display = ('name',)
    filter_horizontal = ('permissions',)


admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)


# ==================== 用户表单（编辑） ====================
class UserChangeForm(forms.ModelForm):
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        label='所属公司',
        required=True,
        help_text='选择用户所属公司'
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['company'] = self.instance.company_id
        self.fields.pop('company_id', None)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.company_id = self.cleaned_data['company'].id
        if commit:
            user.save()
            self.save_m2m()
        return user


# ==================== 用户表单（新增） ====================
class UserCreationForm(forms.ModelForm):
    position_code = forms.ChoiceField(
        label='岗位编码',
        choices=[],
        help_text='选择用户的岗位编码'
    )
    username_suffix = forms.CharField(
        label='自定义后缀',
        required=False,
        help_text='可选，如同岗位多人时添加 "_01" 等，留空则只使用岗位编码',
        widget=forms.TextInput(attrs={'placeholder': '例如 _02'})
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        label='所属公司',
        required=True
    )
    real_name = forms.CharField(label='真实姓名', max_length=50, required=True)
    password1 = forms.CharField(label='密码', widget=forms.PasswordInput)
    password2 = forms.CharField(label='密码确认', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('position_code', 'username_suffix', 'real_name',
                  'company', 'is_active', 'is_staff', 'groups')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        groups = Group.objects.all()
        choices = []
        for g in groups:
            if ' - ' in g.name:
                code = g.name.split(' - ')[0]
                choices.append((code, code))
        choices = sorted(set(choices), key=lambda x: x[0])
        self.fields['position_code'].choices = choices
        if choices:
            self.fields['position_code'].initial = choices[0][0]

    def clean(self):
        cleaned_data = super().clean()
        code = cleaned_data.get('position_code')
        suffix = cleaned_data.get('username_suffix', '').strip()
        if not code:
            raise forms.ValidationError('请选择岗位编码')
        full_username = code + suffix
        if User.objects.filter(username=full_username).exists():
            raise forms.ValidationError(f'用户名 {full_username} 已存在，请修改后缀')
        cleaned_data['username'] = full_username
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        user.set_password(self.cleaned_data['password1'])
        user.company_id = self.cleaned_data['company'].id
        if commit:
            user.save()
            self.save_m2m()
        return user


# ==================== 自定义 UserAdmin ====================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = ('username', 'real_name',
                    'company_name', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'real_name')

    def company_name(self, obj):
        try:
            return Company.objects.get(id=obj.company_id).name
        except Company.DoesNotExist:
            return '-'
    company_name.short_description = '所属公司'

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('real_name', 'email', 'mobile')}),
        ('公司信息', {'fields': ('company',)}),
        # 移除了 'user_permissions'
        ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        ('重要日期', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('position_code', 'username_suffix', 'real_name', 'company', 'password1', 'password2', 'is_active', 'is_staff', 'groups'),
        }),
    )
    filter_horizontal = ('groups',)
    ordering = ('username',)
