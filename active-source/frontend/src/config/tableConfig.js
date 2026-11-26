// 员工管理表格配置
export const employeeTableConfig = {
  columns: [
    { field: 'employee_no', title: '工号', type: 'text', required: true, width: 120 },
    { field: 'full_name', title: '姓名', type: 'text', required: true, width: 120 },
    { field: 'phone', title: '手机号', type: 'text', required: true, width: 150 },
    { 
      field: 'status', 
      title: '状态', 
      type: 'select', 
      options: [
        { value: 'active', label: '在职' },
        { value: 'quit', label: '离职' }
      ],
      width: 100 
    },
    { field: 'department_name', title: '部门', type: 'text', width: 150 },
    { field: 'position', title: '职位', type: 'text', width: 120 },
    { field: 'gender', title: '性别', type: 'select', options: [{ value: 'M', label: '男' }, { value: 'F', label: '女' }], width: 80 },
    { field: 'birth_date', title: '生日', type: 'date', width: 140 },
    { field: 'hire_date', title: '入职日期', type: 'date', width: 120 },
    { field: 'resignation_date', title: '离职日期', type: 'date', width: 140 },
    { field: 'seniority', title: '工龄(年)', type: 'text', width: 100 }
  ]
};

// 班次管理表格配置
export const shiftTableConfig = {
  columns: [
    { field: 'code', title: '班次编码', type: 'text', required: true, width: 120 },
    { field: 'name', title: '班次名称', type: 'text', required: true, width: 120 },
    { field: 'start_time', title: '开始时间', type: 'time', width: 120 },
    { field: 'end_time', title: '结束时间', type: 'time', width: 120 },
    { field: 'break_start', title: '休息开始', type: 'time', width: 120 },
    { field: 'break_end', title: '休息结束', type: 'time', width: 120 },
    { field: 'is_active', title: '状态', type: 'boolean', width: 100 }
  ]
};
// 物料分类表格配置
export const materialCategoryConfig = {
  columns: [
    { field: 'code', title: '分类编码', type: 'text', required: true, width: 120 },
    { field: 'name', title: '分类名称', type: 'text', required: true, width: 150 },
    { field: 'sort_order', title: '排序号', type: 'number', width: 80 },
    { field: 'is_active', title: '状态', type: 'boolean', width: 80 },
  ]
};

// 物料管理表格配置
export const materialConfig = {
  columns: [
    { field: 'code', title: '物料编码', type: 'text', required: true, width: 150 },
    { field: 'name', title: '物料名称', type: 'text', required: true, width: 180 },
    { field: 'specification', title: '规格型号', type: 'text', width: 150 },
    { field: 'unit', title: '单位', type: 'text', required: true, width: 80 },
    { field: 'material_type_display', title: '物料类型', type: 'text', width: 100 },
    { field: 'category_name', title: '物料分类', type: 'text', width: 120 },
    { field: 'safety_stock', title: '安全库存', type: 'number', width: 100 },
    { field: 'max_stock', title: '最高库存', type: 'number', width: 100 },
    { field: 'reorder_point', title: '补货点', type: 'number', width: 100 },
    { field: 'is_purchased', title: '采购件', type: 'boolean', width: 80 },
    { field: 'is_produced', title: '生产件', type: 'boolean', width: 80 },
    { field: 'standard_cost', title: '标准成本', type: 'number', width: 100 },
    { field: 'is_active', title: '状态', type: 'boolean', width: 80 },
  ]
};