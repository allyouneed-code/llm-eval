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
    // 下次再加 Tasks 和 Datasets
  ]
})

export default router