<template>
  <el-table :data="data" border>
    <el-table-column
      v-for="col in meta.table.columns"
      :key="col.prop"
      :prop="col.prop"
      :label="col.label"
    >
      <template #default="scope">
        <!-- index -->
        <span v-if="col.type === 'index'">
          {{ scope.$index + 1 }}
        </span>

        <!-- tag -->
        <el-tag v-else-if="col.type === 'tag'" :type="getTagType(col, scope.row[col.prop])">
          {{ scope.row[col.prop] }}
        </el-tag>

        <!-- default -->
        <span v-else>
          {{ scope.row[col.prop] }}
        </span>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
defineProps({
  meta: Object,
  data: Array,
})

const getTagType = (col, value) => {
  if (col.tagMap) return col.tagMap[value] || 'info'
  if (value === 'HIGH') return 'danger'
  if (value === 'MEDIUM') return 'warning'
  return 'success'
}
</script>
