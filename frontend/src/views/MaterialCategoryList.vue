<template>
  <div style="padding: 20px">
    <h2>物料分类</h2>
    <el-button type="primary" @click="handleAdd" style="margin-bottom: 20px">新增分类</el-button>

    <div style="overflow-x: auto; width: 100%">
      <el-table :data="categoryList" border stripe>
        <el-table-column prop="code" label="分类编码" width="120" />
        <el-table-column prop="name" label="分类名称" width="150" />
        <el-table-column prop="parent_name" label="上级分类" width="120" />
        <el-table-column prop="sort_order" label="排序号" width="80" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
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
        <el-form-item label="分类编码" prop="code" required>
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="分类名称" prop="name" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
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

const categoryList = ref([]);
const dialogVisible = ref(false);
const dialogTitle = ref('');
const submitting = ref(false);
const formRef = ref(null);

const form = ref({
  id: null,
  code: '',
  name: '',
  sort_order: 0,
  is_active: true
});

const rules = {
  code: [{ required: true, message: '请输入分类编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }]
};

const loadCategories = async () => {
  try {
    const res = await request.get('/api/masterdata/categories/');
    categoryList.value = res.results || [];
  } catch (error) {
    ElMessage.error('加载分类列表失败');
  }
};

const handleAdd = () => {
  dialogTitle.value = '新增分类';
  form.value = { id: null, code: '', name: '', sort_order: 0, is_active: true };
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogTitle.value = '编辑分类';
  form.value = { ...row };
  dialogVisible.value = true;
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除分类“${row.name}”吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/masterdata/categories/${row.id}/`);
      ElMessage.success('删除成功');
      loadCategories();
    } catch (error) {
      ElMessage.error('删除失败');
    }
  }).catch(() => { });
};

const submitForm = async () => {
  if (!formRef.value) return;
  await formRef.value.validate();
  submitting.value = true;
  try {
    const data = {
      ...form.value,
      company_id: 1
    };
    if (form.value.id) {
      await request.put(`/masterdata/categories/${form.value.id}/`, data);
      ElMessage.success('编辑成功');
    } else {
      await request.post('/api/masterdata/categories/', data);
      ElMessage.success('新增成功');
    }
    dialogVisible.value = false;
    loadCategories();
  } catch (error) {
    console.error('提交错误:', error);
    ElMessage.error(form.value.id ? '编辑失败' : '新增失败');
  } finally {
    submitting.value = false;
  }
};

onMounted(() => {
  loadCategories();
});
</script>