import request from '@/utils/request'


export function getSchemes() {
  return request({
    url: '/api/v1/schemes/',
    method: 'get'
  })
}

export function createScheme(data) {
  return request({
    url: '/api/v1/schemes/',
    method: 'post',
    data
  })
}

export function deleteScheme(id) {
  return request({
    url: `/api/v1/schemes/${id}`,
    method: 'delete'
  })
}