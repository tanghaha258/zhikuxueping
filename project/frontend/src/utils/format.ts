// ============================================================
// 工具函数
// ============================================================

/**
 * 将 snake_case 字符串转换为 camelCase
 */
export function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

/**
 * 递归将对象的所有 key 从 snake_case 转为 camelCase
 */
export function transformKeysToCamel<T>(data: T): T {
  if (data === null || data === undefined) return data
  if (Array.isArray(data)) {
    return data.map(transformKeysToCamel) as unknown as T
  }
  if (typeof data === 'object' && !(data instanceof Date)) {
    const obj = data as Record<string, unknown>
    const newObj: Record<string, unknown> = {}
    for (const key of Object.keys(obj)) {
      const camelKey = snakeToCamel(key)
      newObj[camelKey] = transformKeysToCamel(obj[key])
    }
    return newObj as T
  }
  return data
}

/**
 * 格式化日期
 * @param date 日期字符串或 Date 对象
 * @param format 格式模板，默认为 'YYYY-MM-DD HH:mm:ss'
 */
export function formatDate(
  date: string | Date | undefined | null,
  format: string = 'YYYY-MM-DD HH:mm:ss'
): string {
  if (!date) return '-'
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '-'

  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')

  return format
    .replace('YYYY', String(year))
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds)
}

/**
 * 截断文本
 * @param text 原始文本
 * @param maxLength 最大长度
 * @param suffix 后缀，默认为 '...'
 */
export function truncateText(
  text: string,
  maxLength: number,
  suffix: string = '...'
): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + suffix
}

/**
 * 获取角色颜色
 * @param role 角色标识
 */
export function getRoleColor(role: string): string {
  const colorMap: Record<string, string> = {
    admin: '#E74C3C',
    school_admin: '#E67E22',
    teacher: '#3498DB',
    student: '#2ECC71',
    parent: '#9B59B6',
  }
  return colorMap[role] || '#909399'
}
