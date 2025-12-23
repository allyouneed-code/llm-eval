<script setup>
import { RouterView, RouterLink, useRoute } from 'vue-router' // <--- 修改点 1：引入 useRoute

const route = useRoute() // <--- 修改点 2：获取当前路由对象
</script>

<template>
  <div class="common-layout">
    <el-container style="height: 100vh;">
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
        </el-menu>
      </el-aside>

      <el-container>
        <el-header style="text-align: right; font-size: 12px; border-bottom: 1px solid #eee; line-height: 60px;">
          <span>Admin User</span>
        </el-header>
        
        <el-main>
          <RouterView />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<style>
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