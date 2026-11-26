export const JOB_FAMILY_LOAD_STATUS = Object.freeze({
  LOADED: 'LOADED',
  EMPTY_VALID: 'EMPTY_VALID',
  READ_FAILED: 'READ_FAILED',
})

export function mapJobFamilyResponse(response) {
  if (!response?.success) {
    return {
      status: JOB_FAMILY_LOAD_STATUS.READ_FAILED,
      options: [],
      error: response?.error?.message || '岗位族服务端事实读取失败。',
    }
  }
  if (!Array.isArray(response?.data?.jobFamilies)) {
    return {
      status: JOB_FAMILY_LOAD_STATUS.READ_FAILED,
      options: [],
      error: '岗位族服务端响应缺少 jobFamilies 数组。',
    }
  }
  const options = response.data.jobFamilies.map(row => ({ ...row }))
  return {
    status: options.length
      ? JOB_FAMILY_LOAD_STATUS.LOADED
      : JOB_FAMILY_LOAD_STATUS.EMPTY_VALID,
    options,
    error: '',
  }
}

export async function loadJobFamilyOptions(readOrganizationModel) {
  try {
    return mapJobFamilyResponse(await readOrganizationModel())
  } catch (error) {
    return {
      status: JOB_FAMILY_LOAD_STATUS.READ_FAILED,
      options: [],
      error: error?.message || String(error) || '岗位族服务端事实读取失败。',
    }
  }
}
