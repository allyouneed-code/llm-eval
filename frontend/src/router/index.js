import { createRouter, createWebHistory } from 'vue-router'
// 懒加载页面组件
const ModelView = () => import('../views/ModelView.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/models' // 默认跳到模型页
    },
    {
      path: '/models',
      name: 'models',
      component: ModelView
    },
    {
      path: '/datasets', // 新增路由
      name: 'datasets',
      component: () => import('../views/DatasetView.vue')
    },
    {
      path: '/tasks', // 新增
      name: 'tasks',
      component: () => import('../views/TaskView.vue')
    }
  ]
})

export default router