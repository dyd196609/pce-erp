<template>
  <div style="padding: 20px">
    <h2>供应商管理</h2>

    <!-- 工具栏 -->
    <div style="margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center">
      <el-button type="primary" @click="handleAdd">新增供应商</el-button>
      <el-button type="success" @click="downloadTemplate">下载导入模板</el-button>
      <el-button type="primary" plain @click="batchApprove">批量审核</el-button>
      <el-button type="primary" plain @click="batchReview">批量复核</el-button>
      <el-button type="primary" plain @click="batchFinalApprove">批量审批</el-button>
      <el-button type="primary" plain @click="batchReceive">批量收货</el-button>
      <el-button type="primary" plain @click="batchInspect">批量检验</el-button>
      <el-button type="primary" plain @click="batchStore">批量入库</el-button>
      <el-button type="primary" plain @click="batchClose">批量结案</el-button>
      <el-upload ref="uploadRef" :action="uploadUrl" :headers="uploadHeaders" :on-success="handleUploadSuccess"
        :on-error="handleUploadError" :before-upload="beforeUpload" :show-file-list="false">
        <el-button type="warning">导入Excel</el-button>
      </el-upload>
      <el-button type="info" @click="exportData">导出Excel</el-button>

      <el-input v-model="searchKeyword" placeholder="搜索供应商编码/名称" clearable style="width: 220px; margin-left: auto"
        @clear="loadSuppliers" @keyup.enter="loadSuppliers" />
      <el-button @click="loadSuppliers">搜索</el-button>
    </div>

    <!-- 供应商表格（横向滚动） -->
    <div class="table-scroll-container" ref="tableScrollContainer" @mousemove="handleTableMouseMove"
      @mouseleave="handleTableMouseLeave" style="overflow-x: auto; width: 100%; max-width: 100%">
      <el-table :data="supplierList" border stripe style="min-width: 1200px; width: 100%">
        <!-- 序号列 -->
        <el-table-column type="index" label="序号" width="60" fixed="left" :index="indexMethod" />

        <!-- 供应商编码 - 录入筛选 + 批量筛选 -->
        <el-table-column prop="code" label="供应商编码" width="150" column-key="code">
          <template #header>
            <div>
              <div>供应商编码</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.code" placeholder="输入筛选" size="small" clearable @input="handleTextFilter" />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedCodes">
                      <el-checkbox v-for="item in codeOptions" :key="item.value" :label="item.value">
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetCodeFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmCodeFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 供应商名称 - 录入筛选 + 批量筛选 -->
        <el-table-column prop="name" label="供应商名称" width="180" column-key="name">
          <template #header>
            <div>
              <div>供应商名称</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.name" placeholder="输入筛选" size="small" clearable @input="handleTextFilter" />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedNames">
                      <el-checkbox v-for="item in nameOptions" :key="item.value" :label="item.value">
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetNameFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmNameFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 联系人 - 录入筛选 + 批量筛选 -->
        <el-table-column prop="contact_person" label="联系人" width="100" column-key="contact_person">
          <template #header>
            <div>
              <div>联系人</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.contact_person" placeholder="输入筛选" size="small" clearable
                  @input="handleTextFilter" />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedContactPersons">
                      <el-checkbox v-for="item in contactPersonOptions" :key="item.value" :label="item.value">
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetContactPersonFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmContactPersonFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 联系电话 - 录入筛选 + 批量筛选 -->
        <el-table-column prop="contact_phone" label="联系电话" width="130" column-key="contact_phone">
          <template #header>
            <div>
              <div>联系电话</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.contact_phone" placeholder="输入筛选" size="small" clearable
                  @input="handleTextFilter" />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedPhones">
                      <el-checkbox v-for="item in phoneOptions" :key="item.value" :label="item.value">
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetPhoneFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmPhoneFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 邮箱 - 录入筛选 + 批量筛选 -->
        <el-table-column prop="contact_email" label="邮箱" width="180" column-key="contact_email">
          <template #header>
            <div>
              <div>邮箱</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.contact_email" placeholder="输入筛选" size="small" clearable
                  @input="handleTextFilter" />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedEmails">
                      <el-checkbox v-for="item in emailOptions" :key="item.value" :label="item.value">
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetEmailFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmEmailFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 信用等级 - 下拉筛选 + 批量筛选 -->
        <el-table-column prop="credit_rating_display" label="信用等级" width="100" column-key="credit_rating">
          <template #header>
            <div>
              <div>信用等级</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-select v-model="filters.credit_rating" placeholder="选择筛选" size="small" clearable
                  @change="handleSelectFilter">
                  <el-option label="A级" value="A" />
                  <el-option label="B级" value="B" />
                  <el-option label="C级" value="C" />
                  <el-option label="D级" value="D" />
                </el-select>
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedCreditRatings">
                      <el-checkbox label="A">A级</el-checkbox>
                      <el-checkbox label="B">B级</el-checkbox>
                      <el-checkbox label="C">C级</el-checkbox>
                      <el-checkbox label="D">D级</el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetCreditRatingFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmCreditRatingFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
          <template #default="{ row }">
            {{ row.credit_rating_display || row.credit_rating }}
          </template>
        </el-table-column>

        <!-- 状态 - 下拉筛选 + 批量筛选 -->
        <el-table-column prop="status_display" label="状态" width="80" column-key="is_active">
          <template #header>
            <div>
              <div>状态</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-select v-model="filters.is_active" placeholder="选择筛选" size="small" clearable
                  @change="handleSelectFilter">
                  <el-option label="启用" value="true" />
                  <el-option label="禁用" value="false" />
                </el-select>
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedStatuses">
                      <el-checkbox label="true">启用</el-checkbox>
                      <el-checkbox label="false">禁用</el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetStatusFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmStatusFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 操作列 -->
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <el-pagination :current-page="currentPage" :page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper" @current-change="handleCurrentChange"
      @size-change="handleSizeChange" style="margin-top: 20px; justify-content: flex-end" />

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="供应商编码" prop="code" required>
          <el-input v-model="form.code" placeholder="请输入供应商编码" />
        </el-form-item>
        <el-form-item label="供应商名称" prop="name" required>
          <el-input v-model="form.name" placeholder="请输入供应商名称" />
        </el-form-item>
        <el-form-item label="联系人" prop="contact_person">
          <el-input v-model="form.contact_person" placeholder="请输入联系人" />
        </el-form-item>
        <el-form-item label="联系电话" prop="contact_phone">
          <el-input v-model="form.contact_phone" placeholder="请输入联系电话" />
        </el-form-item>
        <el-form-item label="邮箱" prop="contact_email">
          <el-input v-model="form.contact_email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="信用等级" prop="credit_rating">
          <el-select v-model="form.credit_rating" placeholder="请选择信用等级">
            <el-option label="A级" value="A" />
            <el-option label="B级" value="B" />
            <el-option label="C级" value="C" />
            <el-option label="D级" value="D" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
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
import { ref, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import request from '../api/request';

// ========== 列表数据 ==========
const supplierList = ref([]);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);
const searchKeyword = ref('');
const selectedRows = ref([])

// ---------- 批量操作方法 ----------
const batchApprove = async () => {
  const ids = selectedRows.value.filter(r => r.status === 'submitted').map(r => r.id)
  if (!ids.length) return ElMessage.warning('请选择已提交状态的订单')
  await ElMessageBox.confirm(`确定审核 ${ids.length} 个订单吗？`, '提示', { type: 'info' })
  await request.post('/api/procurement/purchase_orders/batch_approve/', { ids })
  ElMessage.success('批量审核成功')
  loadOrders()
}

const batchReview = async () => {
  const ids = selectedRows.value.filter(r => r.status === 'approved').map(r => r.id)
  if (!ids.length) return ElMessage.warning('请选择已审核状态的订单')
  await request.post('/api/procurement/purchase_orders/batch_review/', { ids })
  ElMessage.success('批量复核成功')
  loadOrders()
}

const batchFinalApprove = async () => {
  const ids = selectedRows.value.filter(r => r.status === 'reviewed').map(r => r.id)
  if (!ids.length) return ElMessage.warning('请选择已复核状态的订单')
  await request.post('/api/procurement/purchase_orders/batch_final_approve/', { ids })
  ElMessage.success('批量审批成功')
  loadOrders()
}

const batchReceive = async () => {
  const ids = selectedRows.value.filter(r => r.status === 'final_approved').map(r => r.id)
  if (!ids.length) return ElMessage.warning('请选择已审批状态的订单')
  await request.post('/api/procurement/purchase_orders/batch_receive/', { ids })
  ElMessage.success('批量收货成功')
  loadOrders()
}

const batchInspect = async () => {
  const ids = selectedRows.value.filter(r => r.status === 'received').map(r => r.id)
  if (!ids.length) return ElMessage.warning('请选择已收货状态的订单')
  await request.post('/api/procurement/purchase_orders/batch_inspect/', { ids })
  ElMessage.success('批量检验成功')
  loadOrders()
}

const batchStore = async () => {
  const ids = selectedRows.value.filter(r => r.status === 'inspected').map(r => r.id)
  if (!ids.length) return ElMessage.warning('请选择已检验状态的订单')
  await request.post('/api/procurement/purchase_orders/batch_store/', { ids })
  ElMessage.success('批量入库成功')
  loadOrders()
}

const batchClose = async () => {
  const ids = selectedRows.value.filter(r => r.status === 'stored').map(r => r.id)
  if (!ids.length) return ElMessage.warning('请选择已入库状态的订单')
  await request.post('/api/procurement/purchase_orders/batch_close/', { ids })
  ElMessage.success('批量结案成功')
  loadOrders()
}

// ========== 输入框筛选条件 ==========
const filters = ref({
  code: '',
  name: '',
  contact_person: '',
  contact_phone: '',
  contact_email: '',
  credit_rating: '',
  is_active: ''
});

// ========== 批量筛选变量 ==========
const selectedCodes = ref([]);
const selectedNames = ref([]);
const selectedContactPersons = ref([]);
const selectedPhones = ref([]);
const selectedEmails = ref([]);
const selectedCreditRatings = ref([]);
const selectedStatuses = ref([]);

// ========== 批量筛选选项列表（从数据中动态生成） ==========
const codeOptions = computed(() => {
  const values = [...new Set(supplierList.value.map(item => item.code).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const nameOptions = computed(() => {
  const values = [...new Set(supplierList.value.map(item => item.name).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const contactPersonOptions = computed(() => {
  const values = [...new Set(supplierList.value.map(item => item.contact_person).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const phoneOptions = computed(() => {
  const values = [...new Set(supplierList.value.map(item => item.contact_phone).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const emailOptions = computed(() => {
  const values = [...new Set(supplierList.value.map(item => item.contact_email).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

// ========== 导入导出 ==========
const uploadUrl = computed(() => 'http://127.0.0.1:8000/api/procurement/suppliers/import_excel/');
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}));

// ========== 弹窗相关 ==========
const dialogVisible = ref(false);
const dialogTitle = ref('');
const submitting = ref(false);
const formRef = ref(null);

const form = ref({
  id: null,
  code: '',
  name: '',
  contact_person: '',
  contact_phone: '',
  contact_email: '',
  credit_rating: 'B',
  is_active: true
});

const rules = {
  code: [{ required: true, message: '请输入供应商编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }]
};

// ========== 构建筛选参数 ==========
const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize.value,
    search: searchKeyword.value
  };

  // 批量筛选优先（如果有选中的批量值）
  if (selectedCodes.value.length > 0) {
    params.code__in = selectedCodes.value.join(',');
  } else if (filters.value.code) {
    params.code = filters.value.code;
  }

  if (selectedNames.value.length > 0) {
    params.name__in = selectedNames.value.join(',');
  } else if (filters.value.name) {
    params.name = filters.value.name;
  }

  if (selectedContactPersons.value.length > 0) {
    params.contact_person__in = selectedContactPersons.value.join(',');
  } else if (filters.value.contact_person) {
    params.contact_person = filters.value.contact_person;
  }

  if (selectedPhones.value.length > 0) {
    params.contact_phone__in = selectedPhones.value.join(',');
  } else if (filters.value.contact_phone) {
    params.contact_phone = filters.value.contact_phone;
  }

  if (selectedEmails.value.length > 0) {
    params.contact_email__in = selectedEmails.value.join(',');
  } else if (filters.value.contact_email) {
    params.contact_email = filters.value.contact_email;
  }

  if (selectedCreditRatings.value.length > 0) {
    params.credit_rating__in = selectedCreditRatings.value.join(',');
  } else if (filters.value.credit_rating) {
    params.credit_rating = filters.value.credit_rating;
  }

  if (selectedStatuses.value.length > 0) {
    params.is_active__in = selectedStatuses.value.join(',');
  } else if (filters.value.is_active) {
    params.is_active = filters.value.is_active === 'true';
  }

  return params;
};

// ========== 加载供应商列表 ==========
const loadSuppliers = async () => {
  try {
    const params = buildParams();
    const res = await request.get('/api/procurement/suppliers/', { params });
    supplierList.value = res.results || [];
    total.value = res.count || 0;
  } catch (error) {
    console.error('加载失败:', error);
    ElMessage.error('加载供应商列表失败');
  }
};

// ========== 序号计算方法 ==========
const indexMethod = (index) => {
  return (currentPage.value - 1) * pageSize.value + index + 1;
};

// ========== 输入框筛选事件 ==========
const handleTextFilter = () => {
  currentPage.value = 1;
  loadSuppliers();
};

const handleSelectFilter = () => {
  currentPage.value = 1;
  loadSuppliers();
};

// ========== 批量筛选重置函数 ==========
const resetCodeFilter = () => { selectedCodes.value = []; };
const resetNameFilter = () => { selectedNames.value = []; };
const resetContactPersonFilter = () => { selectedContactPersons.value = []; };
const resetPhoneFilter = () => { selectedPhones.value = []; };
const resetEmailFilter = () => { selectedEmails.value = []; };
const resetCreditRatingFilter = () => { selectedCreditRatings.value = []; };
const resetStatusFilter = () => { selectedStatuses.value = []; };

// ========== 批量筛选确认函数 ==========
const confirmCodeFilter = () => {
  filters.value.code = '';
  loadSuppliers();
};
const confirmNameFilter = () => {
  filters.value.name = '';
  loadSuppliers();
};
const confirmContactPersonFilter = () => {
  filters.value.contact_person = '';
  loadSuppliers();
};
const confirmPhoneFilter = () => {
  filters.value.contact_phone = '';
  loadSuppliers();
};
const confirmEmailFilter = () => {
  filters.value.contact_email = '';
  loadSuppliers();
};
const confirmCreditRatingFilter = () => {
  filters.value.credit_rating = '';
  loadSuppliers();
};
const confirmStatusFilter = () => {
  filters.value.is_active = '';
  loadSuppliers();
};

// ========== 分页事件 ==========
const handleCurrentChange = (page) => {
  currentPage.value = page;
  loadSuppliers();
};

const handleSizeChange = (newSize) => {
  pageSize.value = newSize;
  currentPage.value = 1;
  loadSuppliers();
};

// ========== 导出数据 ==========
const exportData = () => {
  const token = localStorage.getItem('token')
  // 获取选中的订单 ID 列表
  const ids = selectedRows.value.map(row => row.id)
  let url = '/api/procurement/purchase_orders/export/'
  if (ids.length) {
    url += `?ids=${ids.join(',')}`
  }
  fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  })
    .then(res => res.blob())
    .then(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `purchase_orders_${new Date().toISOString().slice(0, 19)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    })
    .catch(() => ElMessage.error('导出失败'))
}

// ========== 下载导入模板 ==========
const downloadTemplate = () => {
  const token = localStorage.getItem('token');
  fetch('http://127.0.0.1:8000/api/procurement/suppliers/export_template/', {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  })
    .then(response => response.blob())
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'supplier_template.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    })
    .catch(() => ElMessage.error('下载模板失败'));
};

// ========== 导入文件校验 ==========
const beforeUpload = (file) => {
  const isAllowed = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    file.type === 'application/vnd.ms-excel' ||
    file.name.endsWith('.csv');
  if (!isAllowed) {
    ElMessage.error('只能上传 Excel 或 CSV 文件');
    return false;
  }
  return true;
};

const handleUploadSuccess = (response) => {
  if (response.success !== undefined) {
    ElMessage.success(`导入完成：成功 ${response.success} 条`);
    loadSuppliers();
  } else {
    ElMessage.error(response.message || '导入失败');
  }
};

const handleUploadError = () => {
  ElMessage.error('导入失败，请检查文件格式');
};

// ========== 新增/编辑/删除 ==========
const handleAdd = () => {
  dialogTitle.value = '新增供应商';
  form.value = {
    id: null,
    code: '',
    name: '',
    contact_person: '',
    contact_phone: '',
    contact_email: '',
    credit_rating: 'B',
    is_active: true
  };
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogTitle.value = '编辑供应商';
  form.value = { ...row };
  dialogVisible.value = true;
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除供应商“${row.name}”吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/procurement/suppliers/${row.id}/`);
      ElMessage.success('删除成功');
      loadSuppliers();
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
    const submitData = {
      ...form.value,
      company_id: 1,  // 添加这一行
      is_active: form.value.is_active !== undefined ? form.value.is_active : true
    };
    if (form.value.id) {
      await request.put(`/procurement/suppliers/${form.value.id}/`, submitData);
      ElMessage.success('编辑成功');
    } else {
      await request.post('/api/procurement/suppliers/', submitData);
      ElMessage.success('新增成功');
    }
    dialogVisible.value = false;
    loadSuppliers();
  } catch (error) {
    console.error('提交错误:', error);
    ElMessage.error(form.value.id ? '编辑失败' : '新增失败');
  } finally {
    submitting.value = false;
  }
};

// ========== 横向滚动（鼠标边缘触发） ==========
const tableScrollContainer = ref(null)
let scrollTimer = null
let scrollInterval = null

const handleTableMouseMove = (event) => {
  const container = tableScrollContainer.value
  if (!container) return

  const rect = container.getBoundingClientRect()
  const mouseX = event.clientX
  const threshold = 80  // 距离右侧多少像素时触发滚动

  // 清除之前的定时器
  if (scrollTimer) clearTimeout(scrollTimer)
  if (scrollInterval) clearInterval(scrollInterval)

  if (mouseX > rect.right - threshold) {
    // 鼠标在右侧边缘，开始向左滚动
    scrollTimer = setTimeout(() => {
      scrollInterval = setInterval(() => {
        if (container.scrollLeft < container.scrollWidth - container.clientWidth) {
          container.scrollBy({ left: 20, behavior: 'smooth' })
        } else {
          clearInterval(scrollInterval)
        }
      }, 50)
    }, 200)
  } else if (mouseX < rect.left + threshold) {
    // 鼠标在左侧边缘，向右滚动
    scrollTimer = setTimeout(() => {
      scrollInterval = setInterval(() => {
        if (container.scrollLeft > 0) {
          container.scrollBy({ left: -20, behavior: 'smooth' })
        } else {
          clearInterval(scrollInterval)
        }
      }, 50)
    }, 200)
  }
}

const handleTableMouseLeave = () => {
  // 鼠标离开表格区域，停止滚动
  if (scrollTimer) clearTimeout(scrollTimer)
  if (scrollInterval) clearInterval(scrollInterval)
}

onMounted(() => {
  loadSuppliers();
});
</script>

<style scoped>
:deep(.el-popover) {
  max-height: 300px;
  overflow-y: auto;
}

.table-scroll-container {
  overflow-x: scroll;
  width: 100%;
  cursor: default;
  scroll-behavior: smooth;
}

/* 自定义滚动条样式（可选） */
.table-scroll-container::-webkit-scrollbar {
  height: 8px;
}

.table-scroll-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.table-scroll-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.table-scroll-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>