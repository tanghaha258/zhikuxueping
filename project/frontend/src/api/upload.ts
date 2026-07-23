import http from './index'
import type { ApiResponse } from '@/types'

export interface UploadResult {
  url: string
  fileName: string
  size: number
}

export function uploadFileApi(
  file: File,
  onProgress?: (percent: number) => void
) {
  const formData = new FormData()
  formData.append('file', file)
  return http.post<ApiResponse<UploadResult>>('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
}

export function uploadImageApi(file: File) {
  const form = new FormData()
  form.append('file', file)
  return http.post<ApiResponse<{ url: string }>>('/upload/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
