import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Login from '../views/Login.vue'
import EmployeeList from '../views/EmployeeList.vue'
import ShiftList from '../views/ShiftList.vue'
import MaterialCategoryList from '../views/MaterialCategoryList.vue'
import MaterialList from '../views/MaterialList.vue'
import SupplierList from '../views/SupplierList.vue'
import PurchaseOrderList from '../views/PurchaseOrderList.vue'

// 临时占位，采购报表页面稍后创建
import PurchaseReports from '../views/PurchaseReports.vue'

const routes = [
  { path: '/login', component: Login, meta: { requiresAuth: false } },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true },
    children: [
      { path: 'employees', component: EmployeeList },
      { path: 'shifts', component: ShiftList },
      { path: 'material-categories', component: MaterialCategoryList },
      { path: 'materials', component: MaterialList },
      { path: 'suppliers', component: SupplierList },
      { path: 'purchase-orders', component: PurchaseOrderList },
      { path: 'reports', component: PurchaseReports },
      { path: '', redirect: '/employees' }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router