<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>掌云智造</h2>
      <el-form :model="form" :rules="rules" ref="formRef">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input type="password" v-model="form.password" placeholder="密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleLogin" :loading="loading">登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useUserStore } from '../stores/counter';
import request from '../api/request';

const router = useRouter();
const userStore = useUserStore();
const form = reactive({ username: '', password: '' });
const loading = ref(false);
const formRef = ref(null);

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
};

const handleLogin = async () => {
  if (!formRef.value) return;
  await formRef.value.validate();
  loading.value = true;
  try {
    const res = await request.post('/api/auth/login/', {
      username: form.username,
      password: form.password
    });
    if (res.token) {
      localStorage.setItem('token', res.token);
      userStore.setToken(res.token);
      userStore.setUserInfo(res.user);
      ElMessage.success('登录成功');
      router.push('/');
    } else if (res.success) {
      // 如果没有 token 但有 success，用假的 token
      localStorage.setItem('token', 'fake_token');
      userStore.setToken('fake_token');
      userStore.setUserInfo({
        username: res.username,
        real_name: res.real_name
      });
      ElMessage.success('登录成功');
      router.push('/');
    } else {
      ElMessage.error(res.error || '登录失败');
    }
  } catch (error) {
    console.error('登录失败:', error);
    ElMessage.error(error.response?.data?.error || '登录失败');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f0f2f5;
}

.login-card {
  width: 400px;
  padding: 20px;
}

h2 {
  text-align: center;
  margin-bottom: 20px;
}
</style>