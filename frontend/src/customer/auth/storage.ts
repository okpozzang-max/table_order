export interface TableCredentials {
  storeId: string
  tableNumber: number
  password: string
}

export const TABLE_CREDENTIALS_KEY = 'tableorder.table.credentials'

/** 저장된 테이블 자격 증명을 읽는다. 없거나 형식이 깨졌으면 null. */
export function readTableCredentials(): TableCredentials | null {
  const raw = localStorage.getItem(TABLE_CREDENTIALS_KEY)
  if (!raw) return null
  try {
    const v = JSON.parse(raw) as unknown
    if (
      v &&
      typeof v === 'object' &&
      typeof (v as TableCredentials).storeId === 'string' &&
      typeof (v as TableCredentials).tableNumber === 'number' &&
      typeof (v as TableCredentials).password === 'string'
    ) {
      return v as TableCredentials
    }
    return null
  } catch {
    return null
  }
}

/** 초기 설정이 성공했을 때만 호출한다. */
export function writeTableCredentials(creds: TableCredentials): void {
  localStorage.setItem(TABLE_CREDENTIALS_KEY, JSON.stringify(creds))
}

export function clearTableCredentials(): void {
  localStorage.removeItem(TABLE_CREDENTIALS_KEY)
}

/** 현재 테이블을 가리키는 키 "<storeId>:<tableNumber>" (장바구니 영속화에 사용). */
export function tableKeyOf(creds: Pick<TableCredentials, 'storeId' | 'tableNumber'> | null): string | null {
  return creds ? `${creds.storeId}:${creds.tableNumber}` : null
}
