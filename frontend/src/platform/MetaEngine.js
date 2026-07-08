export default {
  compile(meta) {
    return {
      formRuntime: {
        model: {},
        fields: meta.form || [],
      },

      table: {
        columns: meta.table || [],
      },
    }
  },
}
