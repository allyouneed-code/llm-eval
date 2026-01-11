<script setup>
import { ref, watch } from 'vue' // [新增] 引入 ref 和 watch
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router' // [新增] 引入 useRouter

const route = useRoute()
const router = useRouter() // [新增] 获取 router 实例

// [新增] 用户名状态
const username = ref('')

// [新增] 更新用户名的函数
const updateUsername = () => {
  username.value = sessionStorage.getItem('username') || 'Admin'
}

// [新增] 初始化调用
updateUsername()

// [新增] 监听路由变化，当从登录页跳转过来时，刷新用户名
watch(() => route.path, () => {
  updateUsername()
})

// [新增] 退出登录处理函数
const handleLogout = () => {
  // 1. 清除缓存
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('username')
  // 2. 跳转至登录页
  router.push('/login')
}

// [新增] 下拉菜单指令处理
const handleCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  }
}
</script>

<template>
  <div class="common-layout">
    <el-container v-if="route.path !== '/login'" style="height: 100vh;">
      <el-aside width="200px" style="background-color: #304156;">
        <div class="logo">LLM Eval 平台</div>
        
        <el-menu
          active-text-color="#409EFF"
          background-color="#304156"
          text-color="#fff"
          router
          :default-active="route.path" 
        > 
        <el-menu-item index="/models">
            <el-icon><Monitor /></el-icon>
            <span>模型管理</span>
          </el-menu-item>
          <el-menu-item index="/datasets">
            <el-icon><Files /></el-icon>
            <span>数据集管理</span>
          </el-menu-item>
          <el-menu-item index="/schemes">
            <el-icon><List /></el-icon>
            <span>评测方案</span>
          </el-menu-item>
          <el-menu-item index="/tasks">
            <el-icon><DataLine /></el-icon>
            <span>评测任务</span>
          </el-menu-item>
          <el-menu-item index="/tasks/compare">
            <el-icon><Histogram /></el-icon>
            <span>评测对比</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header style="text-align: right; font-size: 12px; border-bottom: 1px solid #eee; line-height: 60px;">
          <div style="display: flex; justify-content: flex-end; align-items: center; height: 100%;">
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
        
        <el-main>
          <RouterView />
        </el-main>
      </el-container>
    </el-container>

    <div v-else style="height: 100vh;">
      <RouterView />
    </div>
  </div>
</template>

<style>
/* ... 样式保持不变 ... */
body {
  margin: 0;
  padding: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: white;
  font-weight: bold;
  font-size: 20px;
  background-color: #2b3a4d;
}
</style>