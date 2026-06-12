from django.urls import path
from . import views

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="api_login"),
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
]
