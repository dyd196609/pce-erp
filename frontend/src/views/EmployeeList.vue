<template>
  <div style="padding: 20px">
    <h2>员工管理</h2>
    
    <!-- 工具栏 -->
    <div style="margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center">
      <el-button type="primary" @click="handleAdd">新增员工</el-button>
      <el-button type="success" @click="downloadTemplate">下载导入模板</el-button>
      <el-upload
        ref="uploadRef"
        :action="uploadUrl"
        :headers="uploadHeaders"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :before-upload="beforeUpload"
        :show-file-list="false"
      >
        <el-button type="warning">导入Excel</el-button>
      </el-upload>
      <el-button type="info" @click="exportData">导出Excel</el-button>
      
      <el-input
        v-model="searchKeyword"
        placeholder="全局搜索"
        clearable
        style="width: 200px; margin-left: auto"
        @clear="loadEmployees"
        @keyup.enter="loadEmployees"
      />
      <el-button @click="loadEmployees">搜索</el-button>
    </div>

     <!-- 员工表格 -->
     <div style="overflow-x: auto; width: 100%">
       <el-table :data="employeeList" border stripe style="min-width: 100%">
        <!-- 序号列 -->
        <el-table-column type="index" label="序号" width="60" fixed="left" :index="indexMethod" />
        
        <!-- 工号 - 输入框 + 弹出多选 -->
        <el-table-column prop="employee_no" label="工号" width="180" column-key="employee_no">
          <template #header>
            <div>
              <div>工号</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input 
                  v-model="filters.employee_no" 
                  placeholder="输入筛选" 
                  size="small"
                  clearable
                  @input="handleTextFilter"
                />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedEmployeeNos">
                      <el-checkbox
                        v-for="item in employeeNoOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetEmployeeNoFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmEmployeeNoFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 姓名 - 输入框 + 弹出多选 -->
        <el-table-column prop="full_name" label="姓名" width="160" column-key="full_name">
          <template #header>
            <div>
              <div>姓名</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input 
                  v-model="filters.full_name" 
                  placeholder="输入筛选" 
                  size="small"
                  clearable
                  @input="handleTextFilter"
                />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedNames">
                      <el-checkbox
                        v-for="item in nameOptions"
                        :key="item.value"
                        :value="item.value"
                      >
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
        
        <!-- 手机号 - 输入框 + 弹出多选 -->
        <el-table-column prop="phone" label="手机号" width="180" column-key="phone">
          <template #header>
            <div>
              <div>手机号</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input 
                  v-model="filters.phone" 
                  placeholder="输入筛选" 
                  size="small"
                  clearable
                  @input="handleTextFilter"
                />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedPhones">
                      <el-checkbox
                        v-for="item in phoneOptions"
                        :key="item.value"
                        :value="item.value"
                      >
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
        
        <!-- 状态 - 下拉 + 弹出多选 -->
        <el-table-column prop="status" label="状态" width="140" column-key="status">
          <template #header>
            <div>
              <div>状态</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-select 
                  v-model="filters.status" 
                  placeholder="选择筛选" 
                  size="small"
                  clearable
                  @change="handleSelectFilter"
                >
                  <el-option label="在职" value="active" />
                  <el-option label="离职" value="inactive" />
                </el-select>
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedStatuses">
                      <el-checkbox value="active">在职</el-checkbox>
                      <el-checkbox value="inactive">离职</el-checkbox>
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
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '在职' : '离职' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 部门 - 输入框 + 弹出多选 -->
        <el-table-column prop="department_name" label="部门" width="160" column-key="department_name">
          <template #header>
            <div>
              <div>部门</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input 
                  v-model="filters.department_name" 
                  placeholder="输入筛选" 
                  size="small"
                  clearable
                  @input="handleTextFilter"
                />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedDepartments">
                      <el-checkbox
                        v-for="item in departmentOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetDepartmentFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmDepartmentFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 职位 - 输入框 + 弹出多选 -->
        <el-table-column prop="position" label="职位" width="180" column-key="position">
          <template #header>
            <div>
              <div>职位</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input 
                  v-model="filters.position" 
                  placeholder="输入筛选" 
                  size="small"
                  clearable
                  @input="handleTextFilter"
                />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedPositions">
                      <el-checkbox
                        v-for="item in positionOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetPositionFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmPositionFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 性别 - 下拉 + 弹出多选 -->
        <el-table-column prop="gender" label="性别" width="120" column-key="gender">
          <template #header>
            <div>
              <div>性别</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-select 
                  v-model="filters.gender" 
                  placeholder="选择筛选" 
                  size="small"
                  clearable
                  @change="handleSelectFilter"
                >
                  <el-option label="男" value="M" />
                  <el-option label="女" value="F" />
                </el-select>
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedGenders">
                      <el-checkbox value="M">男</el-checkbox>
                      <el-checkbox value="F">女</el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetGenderFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmGenderFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
          <template #default="{ row }">
            {{ row.gender === 'M' ? '男' : row.gender === 'F' ? '女' : '' }}
          </template>
        </el-table-column>
        
        <!-- 生日 - 日期范围 + 清除按钮 -->
        <el-table-column prop="birth_date" label="生日" width="300" column-key="birth_date">
        <template #header>
            <div>
            <div>生日</div>
            <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-date-picker
                v-model="dateRange.birth_date"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                size="small"
                value-format="YYYY-MM-DD"
                :unlink-panels="true"
                :default-value="new Date()"   
                @change="handleDateRangeFilter"
                style="flex: 1"
                />
                <el-button size="small" @click="clearDateRange('birth_date')">清除</el-button>
            </div>
            </div>
        </template>
        </el-table-column>
        
        <!-- 入职日期 - 日期范围 + 弹出多选 -->
        <el-table-column prop="hire_date" label="入职日期" width="260" column-key="hire_date">
          <template #header>
            <div>
              <div>入职日期</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-date-picker
                  v-model="dateRange.hire_date"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  size="small"
                  value-format="YYYY-MM-DD"
                  :unlink-panels="true"
                  :default-value="new Date()"   
                  @change="handleDateRangeFilter"
                  style="flex: 1"
                />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedHireDates">
                      <el-checkbox
                        v-for="item in hireDateOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetHireDateFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmHireDateFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 离职日期 - 日期范围 + 弹出多选 -->
        <el-table-column prop="resignation_date" label="离职日期" width="260" column-key="resignation_date">
          <template #header>
            <div>
              <div>离职日期</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-date-picker
                  v-model="dateRange.resignation_date"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  size="small"
                  value-format="YYYY-MM-DD"
                  :unlink-panels="true"
                  :default-value="new Date()"   
                  @change="handleDateRangeFilter"
                  style="flex: 1"
                />
                <el-popover placement="bottom-end" width="220" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <el-checkbox-group v-model="selectedResignationDates">
                      <el-checkbox
                        v-for="item in resignationDateOptions"
                        :key="item.value"
                        :value="item.value"
                      >
                        {{ item.text }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <div style="margin-top: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px">
                      <el-button size="small" @click="resetResignationDateFilter">重置</el-button>
                      <el-button size="small" type="primary" @click="confirmResignationDateFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 工龄 - 只显示，不筛选 -->
        <el-table-column prop="seniority" label="工龄" width="80" />
        
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
    <el-pagination
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @current-change="handleCurrentChange"
      @size-change="handleSizeChange"
      style="margin-top: 20px; justify-content: flex-end"
    />

    <!-- 弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="工号" prop="employee_no">
          <el-input v-model="form.employee_no" placeholder="请输入工号" />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name" required>
          <el-input v-model="form.full_name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-select v-model="form.gender" placeholder="请选择性别">
            <el-option label="男" value="M" />
            <el-option label="女" value="F" />
          </el-select>
        </el-form-item>
        <el-form-item label="生日" prop="birth_date">
          <el-date-picker v-model="form.birth_date" type="date" value-format="YYYY-MM-DD" placeholder="请选择生日" />
        </el-form-item>
        <el-form-item label="部门" prop="department_name">
          <el-input v-model="form.department_name" placeholder="请输入部门" />
        </el-form-item>
        <el-form-item label="职位" prop="position">
          <el-input v-model="form.position" placeholder="请输入职位" />
        </el-form-item>
        <el-form-item label="入职日期" prop="hire_date">
          <el-date-picker v-model="form.hire_date" type="date" value-format="YYYY-MM-DD" placeholder="请选择入职日期" />
        </el-form-item>
        <el-form-item label="离职日期" prop="resignation_date">
          <el-date-picker v-model="form.resignation_date" type="date" value-format="YYYY-MM-DD" placeholder="请选择离职日期" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" placeholder="请选择状态">
            <el-option label="在职" value="active" />
            <el-option label="离职" value="inactive" />
          </el-select>
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

// 清除指定日期范围
const clearDateRange = (field) => {
  dateRange.value[field] = []
  loadEmployees()
}

// ========== 列表数据 ==========
const employeeList = ref([]);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);
const searchKeyword = ref('');

// ========== 输入框筛选条件 ==========
const filters = ref({
  employee_no: '',
  full_name: '',
  phone: '',
  status: '',
  department_name: '',
  position: '',
  gender: '',
  birth_date: '',
  hire_date: '',
  resignation_date: ''
});

// ========== 日期范围筛选变量 ==========
const dateRange = ref({
  birth_date: [],
  hire_date: [],
  resignation_date: []
});

// ========== 批量筛选变量 ==========
const selectedEmployeeNos = ref([]);
const selectedNames = ref([]);
const selectedPhones = ref([]);
const selectedStatuses = ref([]);
const selectedDepartments = ref([]);
const selectedPositions = ref([]);
const selectedGenders = ref([]);
const selectedBirthDates = ref([]);
const selectedHireDates = ref([]);
const selectedResignationDates = ref([]);

// ========== 批量筛选选项列表（从数据中动态生成） ==========
const employeeNoOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.employee_no).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const nameOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.full_name).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const phoneOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.phone).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const departmentOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.department_name).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const positionOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.position).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const birthDateOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.birth_date).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const hireDateOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.hire_date).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

const resignationDateOptions = computed(() => {
  const values = [...new Set(employeeList.value.map(item => item.resignation_date).filter(Boolean))];
  return values.map(v => ({ text: v, value: v }));
});

// ========== 导入导出 ==========
const uploadUrl = computed(() => 'http://127.0.0.1:8000/api/pfm/employees/import_excel/');
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
  employee_no: '',
  full_name: '',
  phone: '',
  gender: '',
  birth_date: '',
  department_name: '',
  position: '',
  hire_date: '',
  resignation_date: '',
  status: 'active'
});

const rules = {
  full_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }]
};

// ========== 构建筛选参数 ==========
const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize.value,
    search: searchKeyword.value
  };
  
  // 批量筛选优先（如果有选中的批量值）
  if (selectedEmployeeNos.value.length > 0) {
    params.employee_no__in = selectedEmployeeNos.value.join(',');
  } else if (filters.value.employee_no) {
    params.employee_no = filters.value.employee_no;
  }
  
  if (selectedNames.value.length > 0) {
    params.full_name__in = selectedNames.value.join(',');
  } else if (filters.value.full_name) {
    params.full_name = filters.value.full_name;
  }
  
  if (selectedPhones.value.length > 0) {
    params.phone__in = selectedPhones.value.join(',');
  } else if (filters.value.phone) {
    params.phone = filters.value.phone;
  }
  
  if (selectedStatuses.value.length > 0) {
    params.status__in = selectedStatuses.value.join(',');
  } else if (filters.value.status) {
    params.status = filters.value.status;
  }
  
  if (selectedDepartments.value.length > 0) {
    params.department_name__in = selectedDepartments.value.join(',');
  } else if (filters.value.department_name) {
    params.department_name = filters.value.department_name;
  }
  
  if (selectedPositions.value.length > 0) {
    params.position__in = selectedPositions.value.join(',');
  } else if (filters.value.position) {
    params.position = filters.value.position;
  }
  
  if (selectedGenders.value.length > 0) {
    params.gender__in = selectedGenders.value.join(',');
  } else if (filters.value.gender) {
    params.gender = filters.value.gender;
  }
  
  if (selectedBirthDates.value.length > 0) {
    params.birth_date__in = selectedBirthDates.value.join(',');
  } else if (filters.value.birth_date) {
    params.birth_date = filters.value.birth_date;
  }
  
  if (selectedHireDates.value.length > 0) {
    params.hire_date__in = selectedHireDates.value.join(',');
  } else if (filters.value.hire_date) {
    params.hire_date = filters.value.hire_date;
  }
  
  if (selectedResignationDates.value.length > 0) {
    params.resignation_date__in = selectedResignationDates.value.join(',');
  } else if (filters.value.resignation_date) {
    params.resignation_date = filters.value.resignation_date;
  }
  
  // 日期范围筛选
  if (dateRange.value.birth_date && dateRange.value.birth_date.length === 2) {
    params.birth_date_start = dateRange.value.birth_date[0];
    params.birth_date_end = dateRange.value.birth_date[1];
  }
  if (dateRange.value.hire_date && dateRange.value.hire_date.length === 2) {
    params.hire_date_start = dateRange.value.hire_date[0];
    params.hire_date_end = dateRange.value.hire_date[1];
  }
  if (dateRange.value.resignation_date && dateRange.value.resignation_date.length === 2) {
    params.resignation_date_start = dateRange.value.resignation_date[0];
    params.resignation_date_end = dateRange.value.resignation_date[1];
  }
  
  return params;
};

// ========== 加载员工列表 ==========
const loadEmployees = async () => {
  try {
    const params = buildParams();
    const res = await request.get('/pfm/employees/', { params });
    employeeList.value = res.results || [];
    total.value = res.count || 0;
  } catch (error) {
    console.error('加载失败:', error);
    ElMessage.error('加载员工列表失败');
  }
};

// ========== 输入框筛选事件 ==========
const handleTextFilter = () => {
  currentPage.value = 1;
  loadEmployees();
};

const handleSelectFilter = () => {
  currentPage.value = 1;
  loadEmployees();
};

// ========== 日期范围筛选事件 ==========
const handleDateRangeFilter = () => {
  console.log('=== 日期范围变化 ===');
  console.log('birth_date:', JSON.parse(JSON.stringify(dateRange.value.birth_date)));
  console.log('hire_date:', JSON.parse(JSON.stringify(dateRange.value.hire_date)));
  console.log('resignation_date:', JSON.parse(JSON.stringify(dateRange.value.resignation_date)));
  console.log('生日范围:', dateRange.value.birth_date);
  console.log('入职日期范围:', dateRange.value.hire_date);
  console.log('离职日期范围:', dateRange.value.resignation_date);
  currentPage.value = 1;
  loadEmployees();
};

// ========== 序号计算方法 ==========
const indexMethod = (index) => {
  return (currentPage.value - 1) * pageSize.value + index + 1;
};

// ========== 批量筛选重置函数 ==========
const resetEmployeeNoFilter = () => { selectedEmployeeNos.value = []; };
const resetNameFilter = () => { selectedNames.value = []; };
const resetPhoneFilter = () => { selectedPhones.value = []; };
const resetStatusFilter = () => { selectedStatuses.value = []; };
const resetDepartmentFilter = () => { selectedDepartments.value = []; };
const resetPositionFilter = () => { selectedPositions.value = []; };
const resetGenderFilter = () => { selectedGenders.value = []; };
const resetBirthDateFilter = () => { selectedBirthDates.value = []; };
const resetHireDateFilter = () => { selectedHireDates.value = []; };
const resetResignationDateFilter = () => { selectedResignationDates.value = []; };

// ========== 批量筛选确认函数（点击确认时清空对应的输入框） ==========
const confirmEmployeeNoFilter = () => {
  filters.value.employee_no = '';
  loadEmployees();
};
const confirmNameFilter = () => {
  filters.value.full_name = '';
  loadEmployees();
};
const confirmPhoneFilter = () => {
  filters.value.phone = '';
  loadEmployees();
};
const confirmStatusFilter = () => {
  filters.value.status = '';
  loadEmployees();
};
const confirmDepartmentFilter = () => {
  filters.value.department_name = '';
  loadEmployees();
};
const confirmPositionFilter = () => {
  filters.value.position = '';
  loadEmployees();
};
const confirmGenderFilter = () => {
  filters.value.gender = '';
  loadEmployees();
};
const confirmBirthDateFilter = () => {
  filters.value.birth_date = '';
  loadEmployees();
};
const confirmHireDateFilter = () => {
  filters.value.hire_date = '';
  loadEmployees();
};
const confirmResignationDateFilter = () => {
  filters.value.resignation_date = '';
  loadEmployees();
};

// ========== 分页事件 ==========
const handleCurrentChange = (page) => {
  currentPage.value = page;
  loadEmployees();
};

const handleSizeChange = (newSize) => {
  pageSize.value = newSize;
  currentPage.value = 1;
  loadEmployees();
};

// ========== 导入模板下载 ==========
const downloadTemplate = () => {
  const token = localStorage.getItem('token');
  fetch('http://127.0.0.1:8000/api/pfm/employees/export_template/', {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  })
  .then(response => response.blob())
  .then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'employee_template.xlsx';
    a.click();
    window.URL.revokeObjectURL(url);
  })
  .catch(() => ElMessage.error('下载模板失败'));
};

// ========== 导出数据 ==========
const exportData = () => {
  const token = localStorage.getItem('token');
  fetch('http://127.0.0.1:8000/api/pfm/employees/export/', {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  })
  .then(response => response.blob())
  .then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `employees_${new Date().toISOString().slice(0,19)}.xlsx`;
    a.click();
    window.URL.revokeObjectURL(url);
    ElMessage.success('导出成功');
  })
  .catch(() => ElMessage.error('导出失败'));
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
    loadEmployees();
  } else {
    ElMessage.error(response.message || '导入失败');
  }
};

const handleUploadError = () => {
  ElMessage.error('导入失败，请检查文件格式');
};

// ========== 新增/编辑/删除 ==========
const handleAdd = () => {
  dialogTitle.value = '新增员工';
  form.value = {
    id: null,
    employee_no: '',
    full_name: '',
    phone: '',
    gender: '',
    birth_date: '',
    department_name: '',
    position: '',
    hire_date: '',
    resignation_date: '',
    status: 'active'
  };
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogTitle.value = '编辑员工';
  form.value = { ...row };
  dialogVisible.value = true;
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除员工“${row.full_name}”吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/pfm/employees/${row.id}/`);
      ElMessage.success('删除成功');
      loadEmployees();
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
      await request.put(`/pfm/employees/${form.value.id}/`, form.value);
      ElMessage.success('编辑成功');
    } else {
      await request.post('/pfm/employees/', form.value);
      ElMessage.success('新增成功');
    }
    dialogVisible.value = false;
    loadEmployees();
  } catch (error) {
    console.error('提交错误:', error);
    ElMessage.error(form.value.id ? '编辑失败' : '新增失败');
  } finally {
    submitting.value = false;
  }
};

onMounted(() => {
  loadEmployees();
});
</script>

<style scoped>
:deep(.el-popover) {
  max-height: 300px;
  overflow-y: auto;
}
</style>