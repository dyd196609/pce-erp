<template>
  <div style="padding: 20px">
    <h2>证书管理</h2>
    <div style="margin-bottom: 20px">
      <el-button type="primary" @click="handleAdd">新增证书</el-button>
      <el-select v-model="filterEmployeeId" placeholder="筛选员工" clearable @change="loadCertificates" style="width: 200px; margin-left: 10px">
        <el-option v-for="emp in employeeList" :key="emp.id" :label="emp.full_name" :value="emp.id" />
      </el-select>
    </div>

    <div style="overflow-x: auto; width: 100%">
      <el-table :data="certificateList" border stripe>
        <el-table-column prop="employee_name" label="员工姓名" width="120" />
        <el-table-column prop="certificate_name" label="证书名称" width="150" />
        <el-table-column prop="certificate_no" label="证书编号" width="150" />
        <el-table-column prop="issue_date" label="发证日期" width="120">
          <template #default="{ row }">{{ row.issue_date ? new Date(row.issue_date).toLocaleDateString('zh-CN') : '' }}</template>
        </el-table-column>
        <el-table-column prop="expiry_date" label="有效期至" width="120">
          <template #default="{ row }">{{ row.expiry_date ? new Date(row.expiry_date).toLocaleDateString('zh-CN') : '' }}</template>
        </el-table-column>
        <el-table-column prop="issuing_authority" label="发证机构" width="150" />
        <el-table-column label="提醒" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.expiry_date && getDaysBeforeExpiry(row.expiry_date) <= row.remind_before_days" type="danger">即将到期</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="员工" prop="employee_id" required>
          <el-select v-model="form.employee_id" placeholder="请选择员工">
            <el-option v-for="emp in employeeList" :key="emp.id" :label="emp.full_name" :value="emp.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="证书名称" prop="certificate_name" required>
          <el-input v-model="form.certificate_name" />
        </el-form-item>
        <el-form-item label="证书编号" prop="certificate_no">
          <el-input v-model="form.certificate_no" />
        </el-form-item>
        <el-form-item label="发证日期">
          <el-date-picker v-model="form.issue_date" type="date" value-format="YYYY-MM-DD" placeholder="请选择" />
        </el-form-item>
        <el-form-item label="有效期至">
          <el-date-picker v-model="form.expiry_date" type="date" value-format="YYYY-MM-DD" placeholder="请选择" />
        </el-form-item>
        <el-form-item label="发证机构">
          <el-input v-model="form.issuing_authority" />
        </el-form-item>
        <el-form-item label="提前提醒天数">
          <el-input-number v-model="form.remind_before_days" :min="0" :max="365" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import request from '../api/request';

const certificateList = ref([]);
const employeeList = ref([]);
const filterEmployeeId = ref('');
const dialogVisible = ref(false);
const dialogTitle = ref('');
const submitting = ref(false);
const formRef = ref(null);

const form = ref({
  id: null,
  employee_id: null,
  certificate_name: '',
  certificate_no: '',
  issue_date: '',
  expiry_date: '',
  issuing_authority: '',
  remind_before_days: 30
});

const rules = {
  employee_id: [{ required: true, message: '请选择员工', trigger: 'change' }],
  certificate_name: [{ required: true, message: '请输入证书名称', trigger: 'blur' }]
};

const getDaysBeforeExpiry = (expiryDate) => {
  const today = new Date();
  const expiry = new Date(expiryDate);
  const diffTime = expiry - today;
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

const loadEmployees = async () => {
  const res = await request.get('/pfm/employees/');
  employeeList.value = res.results || [];
};

const loadCertificates = async () => {
  const params = filterEmployeeId.value ? { employee_id: filterEmployeeId.value } : {};
  const res = await request.get('/pfm/certificates/', { params });
  certificateList.value = res.results || [];
};

const handleAdd = () => {
  dialogTitle.value = '新增证书';
  form.value = { id: null, employee_id: null, certificate_name: '', certificate_no: '', issue_date: '', expiry_date: '', issuing_authority: '', remind_before_days: 30 };
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogTitle.value = '编辑证书';
  form.value = { ...row };
  dialogVisible.value = true;
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除证书“${row.certificate_name}”吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    await request.delete(`/pfm/certificates/${row.id}/`);
    ElMessage.success('删除成功');
    loadCertificates();
  }).catch(() => {});
};

// 修改后的 submitForm 函数
const submitForm = async () => {
  if (!formRef.value) return;
  await formRef.value.validate();
  submitting.value = true;
  try {
    // 将 employee_id 转换为后端期望的 employee 字段
    const data = { ...form.value, employee: form.value.employee_id };
    delete data.employee_id;
    
    if (form.value.id) {
      await request.put(`/pfm/certificates/${form.value.id}/`, data);
      ElMessage.success('编辑成功');
    } else {
      await request.post('/pfm/certificates/', data);
      ElMessage.success('新增成功');
    }
    dialogVisible.value = false;
    loadCertificates();
  } catch (error) {
    ElMessage.error(form.value.id ? '编辑失败' : '新增失败');
  } finally {
    submitting.value = false;
  }
};

onMounted(() => {
  loadEmployees();
  loadCertificates();
});
</script>