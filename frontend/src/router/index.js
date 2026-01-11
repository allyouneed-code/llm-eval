import { createRouter, createWebHistory } from 'vue-router'
import ModelView from '../views/ModelView.vue'
import DatasetView from '../views/DatasetView.vue'
import TaskView from '../views/TaskView.vue'
import SchemeView from '../views/SchemeView.vue'
import TaskCompareView from '../views/TaskCompareView.vue'
import DictView from '../views/DictView.vue'
// [新增] 引入登录页
import LoginView from '../views/LoginView.vue'

const routes = [
  // [新增] 登录路由
  {
    path: '/login',
    name: 'Login',
    component: LoginView
  },
  {
    path: '/',
    redirect: '/models'
  },
  {
    path: '/models',
    name: 'Models',
    component: ModelView
  },
  {
    path: '/datasets',
    name: 'Datasets',
    component: DatasetView
  },
  {
    path: '/schemes',
    name: 'Schemes',
    component: SchemeView
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: TaskView
  },
  {
    path: '/tasks/compare',
    name: 'TaskCompare',
    component: TaskCompareView
  },
{
    path: '/dicts',   // 👈 2. 必须有这个路由配置
    name: 'Dicts',
    component: DictView,
    meta: { title: '字典管理' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// === [新增] 全局前置守卫 ===
router.beforeEach((to, from, next) => {
  const token = sessionStorage.getItem('token')
  
  // 如果要去的地方不是登录页，且没有 Token
  if (to.path !== '/login' && !token) {
    next('/login') // 强制去登录
  } else {
    next() // 放行
  }
})

export default router