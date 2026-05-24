import request from './request';

export const getEmployees = (params) => request.get('/pfm/employees/', { params });
export const createEmployee = (data) => request.post('/pfm/employees/', data);
export const updateEmployee = (id, data) => request.put(`/pfm/employees/${id}/`, data);
export const deleteEmployee = (id) => request.delete(`/pfm/employees/${id}/`);