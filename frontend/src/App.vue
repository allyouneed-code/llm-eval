<script setup>
import { ref, watch, computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
// 引入图标
import { 
  Monitor, 
  Files, 
  List, 
  DataLine, 
  Histogram, 
  UserFilled, 
  ArrowDown, 
  Tools,        // <--- 用于字典管理
  Expand,       // <--- 用于折叠按钮
  Fold,         // <--- 用于折叠按钮
  SwitchButton
} from '@element-plus/icons-vue'
import { getUserRole } from '@/utils/auth'

const route = useRoute()
const router = useRouter()


// ==========================
// 1. 用户状态管理
// ==========================
const username = ref('')
const roleLabel = ref('')
const roleType = ref('info')
const isAdmin = ref(false)

const updateUserInfo = () => {
  username.value = sessionStorage.getItem('username') || 'Admin'

  const role = getUserRole()
  isAdmin.value = (role === 'admin')
  if (role === 'admin') {
    roleLabel.value = '管理员'
    roleType.value = 'danger' // 红色，醒目
  } else {
    roleLabel.value = '普通用户'
    roleType.value = 'primary' // 蓝色，常规
  }
}
// 初始化与路由监听
updateUserInfo()
watch(() => route.path, updateUserInfo)

// ==========================
// 2. 交互逻辑
// ==========================
const isCollapse = ref(false) // 侧边栏折叠状态
const toggleSidebar = () => isCollapse.value = !isCollapse.value

// 退出登录
const handleLogout = () => {
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('username')
  sessionStorage.removeItem('role')
  router.push('/login')
}
const handleCommand = (cmd) => {
  if (cmd === 'logout') handleLogout()
}

// 获取当前页面标题 (用于 Header 显示)
const currentPageTitle = computed(() => {
  return route.meta.title || route.name || 'LLM Eval Platform'
})
</script>

<template>
  <div class="app-wrapper">
    <div v-if="route.path === '/login'" class="login-container">
      <RouterView />
    </div>

    <el-container v-else class="main-layout">
      
      <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar-container">
        <div class="logo-wrapper" :class="{ 'collapsed': isCollapse }">
          <img src="@/assets/vue.svg" alt="logo" class="logo-img" />
          <span v-show="!isCollapse" class="logo-text">LLM Eval</span>
        </div>
        
        <el-menu
          :default-active="route.path"
          class="el-menu-vertical"
          :collapse="isCollapse"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
          router
          :collapse-transition="false"
        >
          <el-menu-item index="/models">
            <el-icon><Monitor /></el-icon>
            <template #title>模型管理</template>
          </el-menu-item>
          
          <el-menu-item index="/datasets">
            <el-icon><Files /></el-icon>
            <template #title>数据集管理</template>
          </el-menu-item>
          
          <el-menu-item index="/schemes">
            <el-icon><List /></el-icon>
            <template #title>评测方案</template>
          </el-menu-item>
          
          <el-menu-item index="/tasks">
            <el-icon><DataLine /></el-icon>
            <template #title>评测任务</template>
          </el-menu-item>
          
          <el-menu-item index="/tasks/compare">
            <el-icon><Histogram /></el-icon>
            <template #title>评测对比</template>
          </el-menu-item>

          <el-menu-item index="/dicts" v-if="isAdmin">
            <el-icon><Tools /></el-icon>
            <template #title>字典管理</template>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header style="text-align: right; font-size: 12px; border-bottom: 1px solid #eee; line-height: 60px;">
          <div style="display: flex; justify-content: flex-end; align-items: center; height: 100%;">
            
            <el-tag 
              v-if="roleLabel" 
              :type="roleType" 
              effect="dark" 
              size="small" 
              style="margin-right: 12px; border: none;"
            >
              {{ roleLabel }}
            </el-tag>

            <el-dropdown @command="handleCommand" trigger="click">
              <span class="el-dropdown-link" style="cursor: pointer; display: flex; align-items: center; color: var(--el-text-color-primary);">
                <el-icon style="margin-right: 8px"><UserFilled /></el-icon>
                {{ username }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <el-main class="app-main">
          <router-view v-slot="{ Component }">
            <transition name="fade-transform" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
        
      </el-container>
    </el-container>
  </div>
</template>

<style scoped>
/* 全局容器 */
.app-wrapper {
  height: 100vh;
  width: 100%;
}
.main-layout {
  height: 100%;
  overflow: hidden;
}

/* ==================
   侧边栏样式
   ================== */
.sidebar-container {
  background-color: #304156;
  transition: width 0.3s;
  overflow-x: hidden;
  box-shadow: 2px 0 6px rgba(0,21,41,.35);
  z-index: 1001;
  display: flex;
  flex-direction: column;
}

.logo-wrapper {
  height: 60px;
  line-height: 60px;
  background: #2b2f3a;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  gap: 12px;
}
.logo-img {
  width: 28px;
  height: 28px;
}
.logo-text {
  color: #fff;
  font-weight: 600;
  font-size: 18px;
  white-space: nowrap;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
}

.el-menu-vertical {
  border-right: none; /* 去除 Element 默认的右边框 */
  width: 100%;
}

/* ==================
   顶部 Header 样式
   ================== */
.navbar {
  height: 60px;
  overflow: hidden;
  position: relative;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,21,41,.08); /* 关键：底部阴影 */
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  z-index: 1000;
}

.left-panel {
  display: flex;
  align-items: center;
  gap: 15px;
}
.hamburger {
  font-size: 20px;
  cursor: pointer;
  color: #5a5e66;
  transition: all 0.3s;
}
.hamburger:hover {
  color: #409EFF;
}
.breadcrumb-text {
  font-size: 16px;
  color: #303133;
  font-weight: 500;
}

.right-panel {
  display: flex;
  align-items: center;
}
.avatar-wrapper {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #5a5e66;
  padding: 5px;
  border-radius: 4px;
  transition: background 0.3s;
}
.avatar-wrapper:hover {
  background: rgba(0,0,0,0.025);
}
.user-avatar {
  background-color: #409EFF;
}
.username {
  font-size: 14px;
}

/* ==================
   主内容区样式
   ================== */
.content-container {
  display: flex;
  flex-direction: column;
  background-color: #f0f2f5; /* 关键：浅灰背景 */
  height: 100vh;
}

.app-main {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  position: relative;
}

/* ==================
   过渡动画
   ================== */
.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.3s;
}
.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}
.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* 登录页占位 */
.login-container {
  height: 100vh;
  width: 100vw;
}
</style>