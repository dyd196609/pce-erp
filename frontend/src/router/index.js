import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import Workbench from '../views/Workbench.vue'
import Login from '../views/Login.vue'

import EmployeeList from '../views/EmployeeList.vue'
import ShiftList from '../views/ShiftList.vue'
import CertificateList from '../views/CertificateList.vue'

import MaterialCategoryList from '../views/MaterialCategoryList.vue'
import MaterialList from '../views/MaterialList.vue'
import SupplierList from '../views/SupplierList.vue'

import PurchaseOrderList from '../views/PurchaseOrderList.vue'
import PurchaseReports from '../views/PurchaseReports.vue'
import PurchaseOrderV2 from '../views/PurchaseOrderV2.vue'
import ComingSoon from '../views/ComingSoon.vue'

import SystemOrg from '../views/SystemOrg.vue'
import SystemDepartment from '../views/SystemDepartment.vue'
import SystemPosition from '../views/SystemPosition.vue'
import SystemPermission from '../views/SystemPermission.vue'
import SystemRole from '../views/SystemRole.vue'
import SystemUser from '../views/SystemUser.vue'
import SystemMenu from '../views/SystemMenu.vue'


const routes = [
  {
    path: '/login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true },
    children: [
      // 默认首页
      {
        path: '',
        redirect: '/dashboard/workbench'
      },

      // 仪表盘
      {
        path: 'dashboard',
        redirect: '/dashboard/workbench'
      },
      {
        path: 'dashboard/workbench',
        component: Workbench
      },
      {
        path: 'dashboard/business',
        component: ComingSoon
      },
      {
        path: 'dashboard/warning',
        component: ComingSoon
      },

      // 主数据
      {
        path: 'masterdata/material-category',
        component: MaterialCategoryList
      },
      {
        path: 'masterdata/material',
        component: MaterialList
      },
      {
        path: 'masterdata/supplier',
        component: SupplierList
      },
      {
        path: 'masterdata/customer',
        component: ComingSoon
      },

      // 采购管理
      {
        path: 'purchase/request',
        component: ComingSoon
      },
      {
        path: 'purchase/order',
        component: PurchaseOrderV2
      },
      {
        path: 'purchase/arrival',
        component: ComingSoon
      },
      {
        path: 'purchase/report',
        component: PurchaseReports
      },

      // 员工中心
      {
        path: 'hr/employee',
        component: EmployeeList
      },
      {
        path: 'hr/certificate',
        component: CertificateList
      },
      {
        path: 'hr/shift',
        component: ShiftList
      },
      {
        path: 'hr/training',
        component: ComingSoon
      },
      {
        path: 'hr/attendance',
        component: ComingSoon
      },

      // 效益管理
      {
        path: 'profit/realtime',
        component: ComingSoon
      },
      {
        path: 'profit/cost',
        component: ComingSoon
      },
      {
        path: 'profit/analysis',
        component: ComingSoon
      },
      {
        path: 'profit/improvement',
        component: ComingSoon
      },
      {
        path: 'profit/ranking',
        component: ComingSoon
      },

      // 系统管理
      {
        path: 'system/org',
        component: SystemOrg
      },
      {
        path: 'system/department',
        component: SystemDepartment
      },
      {
        path: 'system/position',
        component: SystemPosition
      },
      {
        path: 'system/user',
        component: SystemUser
      },
      {
        path: 'system/role',
        component: SystemRole
      },
      {
        path: 'system/permission',
        component: SystemPermission
      },
      {
        path: 'system/menu',
        component: SystemMenu
      },
      {
        path: 'system/log',
        component: ComingSoon
      },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  if (requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router