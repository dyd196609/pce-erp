import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/Login.vue';
import EmployeeList from '../views/EmployeeList.vue';
import ShiftList from '../views/ShiftList.vue';
import MaterialCategoryList from '../views/MaterialCategoryList.vue';
import MaterialList from '../views/MaterialList.vue';
import SupplierList from '../views/SupplierList.vue';
import PurchaseOrderList from '../views/PurchaseOrderList.vue';

const routes = [
  { path: '/login', component: Login, meta: { requiresAuth: false } },
  { path: '/employees', component: EmployeeList, meta: { requiresAuth: true } },
  { path: '/shifts', component: ShiftList, meta: { requiresAuth: true } },
  { path: '/certificates', component: () => import('../views/CertificateList.vue'), meta: { requiresAuth: true } },
  { path: '/material-categories', component: MaterialCategoryList, meta: { requiresAuth: true } },
  { path: '/materials', component: MaterialList, meta: { requiresAuth: true } },
  { path: '/suppliers', component: SupplierList, meta: { requiresAuth: true } },
  { path: '/purchase-orders', component: PurchaseOrderList, meta: { requiresAuth: true } },
  { path: '/', redirect: '/employees' }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token');
  if (to.meta.requiresAuth && !token) {
    next('/login');
  } else {
    next();
  }
});

export default router;