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
      path: '/datasets', 
      name: 'datasets',
      component: () => import('../views/DatasetView.vue')
    },
    {
      path: '/tasks', 
      name: 'tasks',
      component: () => import('../views/TaskView.vue')
    },
    {
      path: '/tasks/compare',
      name: 'TaskCompare',
      component: () => import('../views/TaskCompareView.vue'), // 下面会创建这个文件
      meta: { title: '评测对比' }
    },
    { 
      path: '/schemes', 
      name: 'Schemes', 
      component: () => import('../views/SchemeView.vue')
    }
  ]
})

export default router