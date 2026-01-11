import request from '@/utils/request'

const URL = '/v1/dicts'

export function getDicts(params) {
  return request.get(URL + '/', { params })
}

export function createDict(data) {
  return request.post(URL + '/', data)
}

export function deleteDict(id) {
  return request.delete(URL + `/${id}`)
}