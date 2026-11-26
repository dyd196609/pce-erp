from django.urls import path
from . import views
from .access_control_views import (
    AccessControlFoundationView,
    AccessControlProfileView,
    OrganizationImportCommitView,
    OrganizationImportPreviewView,
    OrganizationImportTemplateView,
    ResponsibilityCatalogView,
)
from .authorization_views import (
    AuthorizationDecisionView,
    BusinessActionCatalogView,
    EnterpriseOrganizationModelView,
    MasterDataExecutorPreviewView,
    OrganizationDirectoryView,
)

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="api_login"),
    path("auth/logout/", views.api_logout, name="api_logout"),
    path("auth/tab-handoff/issue/", views.TabAuthenticationHandoffIssueView.as_view(), name="tab-auth-handoff-issue"),
    path("auth/tab-handoff/exchange/", views.TabAuthenticationHandoffExchangeView.as_view(), name="tab-auth-handoff-exchange"),
    path("departments/", views.department_list, name="department-list"),
    path("org-tree/", views.org_tree, name="org-tree"),
    path("positions/", views.position_list, name="position-list"),
    path("roles/", views.role_list, name="role-list"),
    path("roles/<int:role_id>/menus/", views.role_menu_ids, name="role-menu-ids"),
    path(
        "roles/<int:role_id>/menus/save/", views.save_role_menus, name="save-role-menus"
    ),
    path("permissions/", views.permission_list, name="permission-list"),
    path("users/", views.user_list, name="user-list"),
    path("menus/", views.MenuTreeView.as_view(), name="menu-tree"),
    path("my-menus/", views.my_menus, name="my-menus"),
    path("access-control/profile/", AccessControlProfileView.as_view(), name="access-control-profile"),
    path("access-control/responsibilities/", ResponsibilityCatalogView.as_view(), name="responsibility-catalog"),
    path("access-control/decisions/", AuthorizationDecisionView.as_view(), name="access-control-decision"),
    path("access-control/actions/", BusinessActionCatalogView.as_view(), name="business-action-catalog"),
    path("access-control/organization-directory/", OrganizationDirectoryView.as_view(), name="organization-directory"),
    path("access-control/enterprise-organization-model/", EnterpriseOrganizationModelView.as_view(), name="enterprise-organization-model"),
    path("access-control/master-data-executor-preview/", MasterDataExecutorPreviewView.as_view(), name="master-data-executor-preview"),
    path("access-control/foundation/", AccessControlFoundationView.as_view(), name="access-control-foundation"),
    path("access-control/organization-import/<slug:entity>/template/", OrganizationImportTemplateView.as_view(), name="organization-import-template"),
    path("access-control/organization-import/<slug:entity>/preview/", OrganizationImportPreviewView.as_view(), name="organization-import-preview"),
    path("access-control/organization-import/<slug:entity>/commit/", OrganizationImportCommitView.as_view(), name="organization-import-commit"),
]
