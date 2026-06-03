<template>
  <div style="padding: 20px">
    <h2>物料管理</h2>

    <!-- 工具栏：导入/导出/搜索 -->
    <div style="margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center">
      <el-button type="primary" @click="handleAdd">新增物料</el-button>
      <el-button type="success" @click="downloadTemplate">下载导入模板</el-button>
      <el-upload ref="uploadRef" :action="uploadUrl" :headers="uploadHeaders" :on-success="handleUploadSuccess"
        :on-error="handleUploadError" :before-upload="beforeUpload" :show-file-list="false">
        <el-button type="warning">导入Excel</el-button>
      </el-upload>
      <el-button type="info" @click="exportData">导出Excel</el-button>

      <el-input v-model="searchKeyword" placeholder="全局搜索物料编码/名称" clearable style="width: 250px; margin-left: auto"
        @clear="handleGlobalSearch" @keyup.enter="handleGlobalSearch" />
      <el-button @click="handleGlobalSearch">搜索</el-button>
    </div>

    <!-- 物料表格 -->
    <div style="overflow-x: auto; width: 100%">
      <el-table :data="materialList" border stripe @filter-change="handleFilterChange" style="min-width: 100%">
        <!-- 序号列 -->
        <el-table-column type="index" label="序号" width="60" fixed="left" :index="indexMethod" />

        <!-- 物料编码 -->
        <el-table-column prop="code" label="物料编码" width="150" column-key="code" :filters="codeFilterList"
          :filter-method="filterHandler" filter-placement="bottom-end">
          <template #header>
            <div class="filter-header">
              <span>物料编码</span>
              <el-input v-model="codeFilterText" placeholder="筛选" size="small" clearable
                @input="handleTextFilter('code', codeFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 物料名称 -->
        <el-table-column prop="name" label="物料名称" width="180" column-key="name" :filters="nameFilterList"
          :filter-method="filterHandler">
          <template #header>
            <div class="filter-header">
              <span>物料名称</span>
              <el-input v-model="nameFilterText" placeholder="筛选" size="small" clearable
                @input="handleTextFilter('name', nameFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 规格型号 -->
        <el-table-column prop="specification" label="规格型号" width="150" column-key="specification">
          <template #header>
            <div class="filter-header">
              <span>规格型号</span>
              <el-input v-model="specFilterText" placeholder="筛选" size="small" clearable
                @input="handleTextFilter('specification', specFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 单位 -->
        <el-table-column prop="unit" label="单位" width="80" column-key="unit">
          <template #header>
            <div class="filter-header">
              <span>单位</span>
              <el-input v-model="unitFilterText" placeholder="筛选" size="small" clearable
                @input="handleTextFilter('unit', unitFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 单价 -->
        <el-table-column prop="price" label="单价" width="120">
          <template #header>
            <div class="filter-header">
              <span>单价</span>
              <el-input v-model="priceMinText" placeholder="最低价" size="small" style="width: 45%"
                @input="handlePriceFilter" class="filter-input" />
              <span style="width: 10%; text-align: center">-</span>
              <el-input v-model="priceMaxText" placeholder="最高价" size="small" style="width: 45%"
                @input="handlePriceFilter" class="filter-input" />
            </div>
          </template>
          <template #default="{ row }">
            {{ row.price ? '¥' + Number(row.price).toFixed(2) : '-' }}
          </template>
        </el-table-column>

        <!-- 物料类型 -->
        <el-table-column prop="material_type_display" label="物料类型" width="100" column-key="material_type"
          :filters="materialTypeFilters" :filter-method="filterHandler" filter-placement="bottom-end">
          <template #header>
            <div class="filter-header">
              <span>物料类型</span>
              <el-select v-model="materialTypeFilterText" placeholder="筛选" size="small" clearable
                @change="handleSelectFilter('material_type', materialTypeFilterText)" class="filter-input">
                <el-option label="原材料" value="raw" />
                <el-option label="半成品" value="semi" />
                <el-option label="成品" value="finished" />
                <el-option label="辅料" value="auxiliary" />
              </el-select>
            </div>
          </template>
        </el-table-column>

        <!-- 物料分类 -->
        <el-table-column prop="category_name" label="物料分类" width="120" column-key="category">
          <template #header>
            <div class="filter-header">
              <span>物料分类</span>
              <el-select v-model="categoryFilterText" placeholder="筛选" size="small" clearable filterable
                @change="handleSelectFilter('category_name', categoryFilterText)" class="filter-input">
                <el-option v-for="cat in categoryList" :key="cat.id" :label="cat.name" :value="cat.name" />
              </el-select>
            </div>
          </template>
        </el-table-column>

        <!-- 安全库存 -->
        <el-table-column prop="safety_stock" label="安全库存" width="100">
          <template #header>
            <div class="filter-header">
              <span>安全库存</span>
              <el-input v-model="safetyStockFilterText" placeholder="筛选" size="small" clearable
                @input="handleNumberFilter('safety_stock', safetyStockFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 最高库存 -->
        <el-table-column prop="max_stock" label="最高库存" width="100">
          <template #header>
            <div class="filter-header">
              <span>最高库存</span>
              <el-input v-model="maxStockFilterText" placeholder="筛选" size="small" clearable
                @input="handleNumberFilter('max_stock', maxStockFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 补货点 -->
        <el-table-column prop="reorder_point" label="补货点" width="100">
          <template #header>
            <div class="filter-header">
              <span>补货点</span>
              <el-input v-model="reorderPointFilterText" placeholder="筛选" size="small" clearable
                @input="handleNumberFilter('reorder_point', reorderPointFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 采购件 -->
        <el-table-column label="采购件" width="80" column-key="is_purchased">
          <template #header>
            <div class="filter-header">
              <span>采购件</span>
              <el-select v-model="isPurchasedFilterText" placeholder="筛选" size="small" clearable
                @change="handleSelectFilter('is_purchased', isPurchasedFilterText)" class="filter-input">
                <el-option label="是" :value="true" />
                <el-option label="否" :value="false" />
              </el-select>
            </div>
          </template>
          <template #default="{ row }">{{ row.is_purchased ? '是' : '否' }}</template>
        </el-table-column>

        <!-- 生产件 -->
        <el-table-column label="生产件" width="80" column-key="is_produced">
          <template #header>
            <div class="filter-header">
              <span>生产件</span>
              <el-select v-model="isProducedFilterText" placeholder="筛选" size="small" clearable
                @change="handleSelectFilter('is_produced', isProducedFilterText)" class="filter-input">
                <el-option label="是" :value="true" />
                <el-option label="否" :value="false" />
              </el-select>
            </div>
          </template>
          <template #default="{ row }">{{ row.is_produced ? '是' : '否' }}</template>
        </el-table-column>

        <!-- 标准成本 -->
        <el-table-column prop="standard_cost" label="标准成本" width="100">
          <template #header>
            <div class="filter-header">
              <span>标准成本</span>
              <el-input v-model="standardCostFilterText" placeholder="筛选" size="small" clearable
                @input="handleNumberFilter('standard_cost', standardCostFilterText)" class="filter-input" />
            </div>
          </template>
        </el-table-column>

        <!-- 状态 -->
        <el-table-column label="状态" width="80" column-key="is_active">
          <template #header>
            <div class="filter-header">
              <span>状态</span>
              <el-select v-model="statusFilterText" placeholder="筛选" size="small" clearable
                @change="handleSelectFilter('is_active', statusFilterText)" class="filter-input">
                <el-option label="启用" :value="true" />
                <el-option label="禁用" :value="false" />
              </el-select>
            </div>
          </template>
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 操作列 -->
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <el-pagination :current-page="currentPage" :page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next" @current-change="handleCurrentChange" @size-change="handleSizeChange"
      style="margin-top: 20px; justify-content: flex-end" />

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="物料编码" prop="code" required>
              <el-input v-model="form.code" placeholder="留空则自动生成" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="物料名称" prop="name" required>
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="规格型号">
              <el-input v-model="form.specification" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位" prop="unit" required>
              <el-input v-model="form.unit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="单价">
              <el-input-number v-model="form.price" :min="0" :precision="2" controls-position="right"
                style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="物料类型">
              <el-select v-model="form.material_type">
                <el-option label="原材料" value="raw" />
                <el-option label="半成品" value="semi" />
                <el-option label="成品" value="finished" />
                <el-option label="辅料" value="auxiliary" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="物料分类">
              <el-select v-model="form.category_id" clearable placeholder="请选择">
                <el-option v-for="cat in categoryList" :key="cat.id" :label="cat.name" :value="cat.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标准成本">
              <el-input-number v-model="form.standard_cost" :precision="4" :step="0.01" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="安全库存">
              <el-input-number v-model="form.safety_stock" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最高库存">
              <el-input-number v-model="form.max_stock" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="补货点">
              <el-input-number v-model="form.reorder_point" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="采购提前期(天)">
              <el-input-number v-model="form.lead_time" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购件">
              <el-switch v-model="form.is_purchased" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="生产件">
              <el-switch v-model="form.is_produced" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import request from '../api/request';

// ========== 列表数据 ==========
const materialList = ref([]);
const filteredData = ref([]);
const categoryList = ref([]);
const dialogVisible = ref(false);
const dialogTitle = ref('');
const submitting = ref(false);
const formRef = ref(null);
const searchKeyword = ref('');
const currentPage = ref(1);
const pageSize = ref(100);
const total = ref(0);
const uploadRef = ref(null);

// ========== 筛选数据 ==========
const codeFilterText = ref('')
const nameFilterText = ref('')
const specFilterText = ref('')
const unitFilterText = ref('')
const priceMinText = ref('')
const priceMaxText = ref('')
const materialTypeFilterText = ref('')
const categoryFilterText = ref('')
const safetyStockFilterText = ref('')
const maxStockFilterText = ref('')
const reorderPointFilterText = ref('')
const isPurchasedFilterText = ref('')
const isProducedFilterText = ref('')
const standardCostFilterText = ref('')
const statusFilterText = ref('')

// 筛选选项列表
const codeFilterList = computed(() => {
  const codes = [...new Set(materialList.value.map(item => item.code).filter(Boolean))]
  return codes.map(code => ({ text: code, value: code }))
})
const nameFilterList = computed(() => {
  const names = [...new Set(materialList.value.map(item => item.name).filter(Boolean))]
  return names.map(name => ({ text: name, value: name }))
})
const materialTypeFilters = ref([
  { text: '原材料', value: 'raw' },
  { text: '半成品', value: 'semi' },
  { text: '成品', value: 'finished' },
  { text: '辅料', value: 'auxiliary' }
])

// 序号计算方法
const indexMethod = (index) => {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

// 筛选后的表格数据（前端筛选）
const filteredTableData = computed(() => {
  let result = [...materialList.value]

  // 文本筛选
  if (codeFilterText.value) {
    result = result.filter(item => item.code?.toLowerCase().includes(codeFilterText.value.toLowerCase()))
  }
  if (nameFilterText.value) {
    result = result.filter(item => item.name?.toLowerCase().includes(nameFilterText.value.toLowerCase()))
  }
  if (specFilterText.value) {
    result = result.filter(item => item.specification?.toLowerCase().includes(specFilterText.value.toLowerCase()))
  }
  if (unitFilterText.value) {
    result = result.filter(item => item.unit?.toLowerCase().includes(unitFilterText.value.toLowerCase()))
  }

  // 价格范围筛选
  if (priceMinText.value) {
    result = result.filter(item => (item.price || 0) >= Number(priceMinText.value))
  }
  if (priceMaxText.value) {
    result = result.filter(item => (item.price || 0) <= Number(priceMaxText.value))
  }

  // 数字筛选
  if (safetyStockFilterText.value) {
    result = result.filter(item => item.safety_stock === Number(safetyStockFilterText.value))
  }
  if (maxStockFilterText.value) {
    result = result.filter(item => item.max_stock === Number(maxStockFilterText.value))
  }
  if (reorderPointFilterText.value) {
    result = result.filter(item => item.reorder_point === Number(reorderPointFilterText.value))
  }
  if (standardCostFilterText.value) {
    result = result.filter(item => item.standard_cost === Number(standardCostFilterText.value))
  }

  // 下拉筛选
  if (materialTypeFilterText.value) {
    result = result.filter(item => item.material_type === materialTypeFilterText.value)
  }
  if (categoryFilterText.value) {
    result = result.filter(item => item.category_name === categoryFilterText.value)
  }
  if (isPurchasedFilterText.value !== '') {
    result = result.filter(item => item.is_purchased === isPurchasedFilterText.value)
  }
  if (isProducedFilterText.value !== '') {
    result = result.filter(item => item.is_produced === isProducedFilterText.value)
  }
  if (statusFilterText.value !== '') {
    result = result.filter(item => item.is_active === statusFilterText.value)
  }

  return result
})

// 文本筛选处理
const handleTextFilter = (field, value) => {
  // 自动触发重新计算
}

// 价格筛选处理
const handlePriceFilter = () => {
  // 自动触发重新计算
}

// 数字筛选处理
const handleNumberFilter = (field, value) => {
  // 自动触发重新计算
}

// 下拉筛选处理
const handleSelectFilter = (field, value) => {
  // 自动触发重新计算
}

// 列筛选变化
const handleFilterChange = (filters) => {
  // 处理element-ui自带的多选筛选
}

// 全局搜索
const handleGlobalSearch = () => {
  loadMaterials()
}

const form = ref({
  id: null,
  code: '',
  name: '',
  specification: '',
  unit: '',
  price: 0,
  material_type: 'raw',
  category_id: null,
  safety_stock: 0,
  max_stock: 0,
  reorder_point: 0,
  lead_time: 0,
  is_purchased: false,
  is_produced: false,
  standard_cost: 0,
  is_active: true
});

const rules = {
  code: [{ required: false }],
  name: [{ required: true, message: '请输入物料名称', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }]
};

const uploadUrl = computed(() => 'http://127.0.0.1:8000/api/masterdata/materials/import_excel/');
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}));

const loadCategories = async () => {
  try {
    const res = await request.get('/api/masterdata/categories/');
    categoryList.value = res.results || [];
  } catch (error) {
    console.error('加载分类失败:', error);
  }
};

const handleSizeChange = (newSize) => {
  pageSize.value = newSize;
  currentPage.value = 1;
  loadMaterials();
};

const loadMaterials = async () => {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchKeyword.value
    };
    console.log('=== 加载物料 ===');
    console.log('请求参数:', params);
    const res = await request.get('/api/masterdata/materials/', { params });
    console.log('API 返回:', res);
    console.log('count:', res.count);
    console.log('当前页:', currentPage.value);
    console.log('每页条数:', pageSize.value);
    materialList.value = res.results || [];
    total.value = res.count || 0;
  } catch (error) {
    console.error('加载失败:', error);
    ElMessage.error('加载物料列表失败');
  }
};

const handleCurrentChange = (page) => {
  console.log('切换到第', page, '页');
  currentPage.value = page;
  loadMaterials();
};

// 导出Excel
const exportData = () => {
  const token = localStorage.getItem('token');
  fetch('http://127.0.0.1:8000/api/masterdata/materials/export/', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
    .then(response => {
      if (!response.ok) throw new Error('导出失败');
      return response.blob();
    })
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `materials_${new Date().toISOString().slice(0, 19)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      ElMessage.success('导出成功');
    })
    .catch(error => {
      console.error('导出失败:', error);
      ElMessage.error('导出失败');
    });
};

// 下载导入模板
const downloadTemplate = () => {
  const token = localStorage.getItem('token');
  fetch('http://127.0.0.1:8000/api/masterdata/materials/export_template/', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
    .then(response => {
      if (!response.ok) throw new Error('下载失败');
      return response.blob();
    })
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'material_template.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    })
    .catch(error => {
      ElMessage.error('下载模板失败');
    });
};

const beforeUpload = (file) => {
  const isAllowed = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    file.type === 'application/vnd.ms-excel' ||
    file.type === 'text/csv' ||
    file.name.endsWith('.csv');

  if (!isAllowed) {
    ElMessage.error('只能上传 Excel 或 CSV 文件');
    return false;
  }

  return true;
};

const handleUploadSuccess = (response) => {
  if (response.code === 200 || response.success !== undefined) {
    ElMessage.success(`导入完成：成功 ${response.success || response.data?.success || 0} 条`);
    loadMaterials();
  } else {
    ElMessage.error(response.message || '导入失败');
  }
};

const handleUploadError = (error) => {
  console.error('上传错误:', error);
  ElMessage.error('导入失败，请检查文件格式');
};

const handleAdd = () => {
  dialogTitle.value = '新增物料';
  form.value = {
    id: null, code: '', name: '', specification: '', unit: '',
    price: 0,
    material_type: 'raw', category_id: null, safety_stock: 0, max_stock: 0,
    reorder_point: 0, lead_time: 0, is_purchased: false, is_produced: false,
    standard_cost: 0, is_active: true
  };
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogTitle.value = '编辑物料';
  form.value = {
    ...row,
    price: row.price || 0,
    category_id: row.category
  };
  dialogVisible.value = true;
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除物料“${row.name}”吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/masterdata/materials/${row.id}/`);
      ElMessage.success('删除成功');
      loadMaterials();
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
      company_id: 1,
      category: form.value.category_id,
      price: form.value.price || 0
    };
    delete data.category_id;
    if (form.value.id) {
      await request.put(`/masterdata/materials/${form.value.id}/`, data);
      ElMessage.success('编辑成功');
    } else {
      await request.post('/api/masterdata/materials/', data);
      ElMessage.success('新增成功');
    }
    dialogVisible.value = false;
    loadMaterials();
  } catch (error) {
    console.error('提交错误:', error);
    ElMessage.error(form.value.id ? '编辑失败' : '新增失败');
  } finally {
    submitting.value = false;
  }
};

onMounted(() => {
  loadCategories();
  loadMaterials();
});
</script>

<style scoped>
.filter-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-input {
  width: 100%;
}

.filter-input :deep(.el-input__inner) {
  height: 28px;
  line-height: 28px;
}

:deep(.el-table th) {
  padding: 8px 0;
}

:deep(.el-table .cell) {
  line-height: 32px;
}
</style>