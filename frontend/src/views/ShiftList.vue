<template>
  <div style="padding: 20px">
    <h2>班次管理</h2>
    <el-button type="primary" @click="handleAdd" style="margin-bottom: 20px">新增班次</el-button>
  <div style="overflow-x: auto; width: 100%">
    <el-table :data="shiftList" border stripe>
      <el-table-column
        v-for="col in config.columns"
        :key="col.field"
        :prop="col.field"
        :label="col.title"
        :width="col.width"
      >
        <template #default="{ row }">
          <span v-if="col.type === 'select'">
            {{ col.options?.find(opt => opt.value === row[col.field])?.label || row[col.field] }}
          </span>
          <span v-else-if="col.type === 'boolean'">
            {{ row[col.field] ? '启用' : '禁用' }}
          </span>
          <span v-else>{{ row[col.field] }}</span>
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
    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item
          v-for="col in config.columns"
          :key="col.field"
          :label="col.title"
          :prop="col.field"
          :required="col.required"
        >
          <el-input
            v-if="col.type === 'text'"
            v-model="form[col.field]"
            :placeholder="`请输入${col.title}`"
          />
          <el-select
            v-else-if="col.type === 'select'"
            v-model="form[col.field]"
            :placeholder="`请选择${col.title}`"
          >
            <el-option
              v-for="opt in col.options"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-time-picker
            v-else-if="col.type === 'time'"
            v-model="form[col.field]"
            format="HH:mm:ss"
            value-format="HH:mm:ss"
            :placeholder="`请选择${col.title}`"
          />
          <el-switch
            v-else-if="col.type === 'boolean'"
            v-model="form[col.field]"
            active-text="启用"
            inactive-text="禁用"
          />
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
import { ref, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import request from '../api/request';
import { shiftTableConfig } from '../config/tableConfig';

const config = shiftTableConfig;

const shiftList = ref([]);
const dialogVisible = ref(false);
const dialogTitle = ref('');
const submitting = ref(false);
const formRef = ref(null);

const rules = computed(() => {
  const rulesObj = {};
  config.columns.forEach(col => {
    if (col.required) {
      rulesObj[col.field] = [{ required: true, message: `请输入${col.title}`, trigger: 'blur' }];
    }
  });
  return rulesObj;
});

const emptyForm = () => {
  const obj = { company_id: 1 };
  config.columns.forEach(col => {
    if (col.type === 'boolean') obj[col.field] = true;
    else obj[col.field] = null;
  });
  return obj;
};

const form = ref(emptyForm());

const loadShifts = async () => {
  try {
    const res = await request.get('/pfm/shifts/');
    shiftList.value = res.results || [];
  } catch (error) {
    ElMessage.error('加载班次列表失败');
  }
};

const handleAdd = () => {
  dialogTitle.value = '新增班次';
  form.value = emptyForm();
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogTitle.value = '编辑班次';
  form.value = { ...row };
  dialogVisible.value = true;
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除班次“${row.name}”吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/pfm/shifts/${row.id}/`);
      ElMessage.success('删除成功');
      loadShifts();
    } catch (error) {
      ElMessage.error('删除失败');
    }
  }).catch(() => {});
};

const submitForm = async () => {
  if (!formRef.value) return;
  await formRef.value.validate();
  submitting.value = true;
  try {
    if (form.value.id) {
      await request.put(`/pfm/shifts/${form.value.id}/`, form.value);
      ElMessage.success('编辑成功');
    } else {
      await request.post('/pfm/shifts/', form.value);
      ElMessage.success('新增成功');
    }
    dialogVisible.value = false;
    loadShifts();
  } catch (error) {
    ElMessage.error(form.value.id ? '编辑失败' : '新增失败');
  } finally {
    submitting.value = false;
  }
};

onMounted(() => {
  loadShifts();
});
</script>