import request from './request'

export function getDepartments() {
    return request.get('/api/departments/')
}

export function getPositions() {
    return request.get('/api/positions/')
}

export function getRoles() {
    return request.get('/api/roles/')
}

export function getUsers() {
    return request.get('/api/users/')
}

export function getPermissions() {
    return request.get('/api/permissions/')
}

export function getOrgTree() {
    return request.get('/api/org-tree/')
}

export function getMenus() {
    return request.get('/api/menus/')
}

export function getRoleMenuIds(roleId) {
    return request.get(`/api/roles/${roleId}/menus/`)
}

export function saveRoleMenus(roleId, menuIds) {
    return request.post(`/api/roles/${roleId}/menus/save/`, {
        menu_ids: menuIds
    })
}

export function getMyMenus() {
    return request.get('/api/my-menus/')
}