import pandas as pd
from django import forms
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django.shortcuts import render, redirect
from .models import Company, Department, Workshop, Team, Process, Position, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# 注册所有模型（不包括 Group，稍后单独处理）
admin.site.register(Company)
admin.site.register(Department)
admin.site.register(Workshop)
admin.site.register(Team)
admin.site.register(Process)
admin.site.register(Position)


# 导入视图（保持不变）
@staff_member_required
def import_org_view(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            xls = pd.ExcelFile(excel_file)

            # 导入公司
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

            # 导入部门
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
                # 设置父级关系
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

            # 导入岗位（创建为 Group）
            if '岗位' in xls.sheet_names:
                df = pd.read_excel(excel_file, sheet_name='岗位')
                for _, row in df.iterrows():
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
                messages.success(request, '岗位数据导入成功')

            messages.success(request, '所有数据导入完成')
        except Exception as e:
            messages.error(request, f'导入失败: {str(e)}')
        return redirect('import_org')

    return render(request, 'admin/import_org.html', {})


# 自定义 Group 表单（从岗位下拉选择）
class GroupForm(forms.ModelForm):
    name = forms.ModelChoiceField(
        queryset=Group.objects.all(),  # 改为从 Group 获取
        label='岗位名称',
        to_field_name='name',
        help_text='请从已有岗位中选择'
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']

    def save(self, commit=True):
        group = super().save(commit=False)
        # 这里 name 已经是选中的 Group 对象，直接取其 name
        group.name = self.cleaned_data['name'].name
        if commit:
            group.save()
            self.save_m2m()
        return group


class GroupAdmin(admin.ModelAdmin):
    form = GroupForm
    list_display = ('name',)
    filter_horizontal = ('permissions',)


# 注销默认的 Group 注册，再注册自定义的
admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)


class UserCreationForm(forms.ModelForm):
    """用户创建表单，自定义用户名和公司ID字段"""
    username = forms.CharField(
        label='用户名',
        widget=forms.TextInput(attrs={
            'list': 'group_names',
            'style': 'width: 300px;',
        }),
        help_text='可从下拉列表选择岗位编号，也可手动修改以避免重复'
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        label='所属公司',
        required=True,
        help_text='请选择用户所属公司'
    )
    password1 = forms.CharField(label='密码', widget=forms.PasswordInput)
    password2 = forms.CharField(label='密码确认', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('username', 'real_name', 'company',
                  'is_active', 'is_staff', 'groups')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("两次输入的密码不一致")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        # 将公司对象ID赋给 company_id
        user.company_id = self.cleaned_data['company'].id
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserChangeForm(forms.ModelForm):
    """用户编辑表单"""
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        label='所属公司',
        required=True,
        help_text='选择公司'
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # 编辑时，根据 company_id 设置初始公司
            self.initial['company'] = self.instance.company_id
        # 将 company_id 字段隐藏，因为我们用 company 替代
        self.fields.pop('company_id')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.company_id = self.cleaned_data['company'].id
        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm      # 编辑表单
    add_form = UserCreationForm  # 新增表单
    list_display = ('username', 'real_name',
                    'company_display', 'is_active', 'is_staff')
    search_fields = ('username', 'real_name')
    list_filter = ('is_active', 'is_staff', 'is_superuser')

    def company_display(self, obj):
        try:
            return Company.objects.get(id=obj.company_id).name
        except Company.DoesNotExist:
            return '-'
    company_display.short_description = '所属公司'

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('real_name', 'email', 'mobile')}),
        ('公司信息', {'fields': ('company',)}),
        ('权限', {'fields': ('is_active', 'is_staff',
         'is_superuser', 'groups', 'user_permissions')}),
        ('重要日期', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'real_name', 'company', 'password1', 'password2', 'is_active', 'is_staff', 'groups'),
        }),
    )
    filter_horizontal = ('groups', 'user_permissions')
    ordering = ('username',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # 为用户名输入框添加 datalist 建议（岗位编号列表）
        groups = Group.objects.all()
        suggestions = [g.name.split(' - ')[0]
                       for g in groups if ' - ' in g.name]  # 提取编码部分
        # 也包含完整名称作为备选
        suggestions.extend([g.name for g in groups])
        suggestions = list(set(suggestions))  # 去重
        datalist_html = '<datalist id="group_names">' + \
            ''.join(
                f'<option value="{s}">' for s in suggestions) + '</datalist>'
        # 注意：这需要在模板中渲染，但直接附加到 help_text 或使用自定义 widget 更简单
        # 简便方法：在表单字段的 widget 中指定 attrs 已经添加了 list='group_names'，但 datalist 需要放在模板中。
        # 由于 Django Admin 默认模板不会自动包含，我们需要在 Media 中动态插入或直接覆盖模板。
        # 为了简化，我们可以覆盖 admin 模板，或者采用更简单的方式：使用 autocomplete 插件。
        # 这里提供一种更干净的实现：将 datalist 添加到 add_form 的 Media 中通过 JavaScript 注入。
        # 为了不复杂化，我建议使用 django-autocomplete-light，但为了快速实现，可以将以下 JavaScript 添加到自定义模板。
        # 但为了用户友好，我已在上面的 widget 中设置了 list='group_names'，现在只需在 Admin 页面中增加 datalist 元素。
        # 我们通过 Media 类注入一段 script 来动态添加 datalist。
        return form

    class Media:
        js = ('admin/js/user_datalist.js',)
