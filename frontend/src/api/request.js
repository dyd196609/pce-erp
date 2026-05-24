import axios from 'axios';

const request = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',  // 直接指向后端地址
  timeout: 10000,
});

// 请求拦截器：自动添加 token
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

// 响应拦截器：统一处理错误
request.interceptors.response.use(
  response => response.data,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default request;