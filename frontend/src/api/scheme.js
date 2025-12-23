import request from '@/utils/request'

const URL = '/v1/schemes'

export function getSchemes() {
  return request.get(URL + '/')
}

export function createScheme(data) {
  return request.post(URL + '/', data)
}

export function deleteScheme(id) {
  return request.delete(URL + `/${id}`)
}