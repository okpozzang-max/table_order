import { useEffect, useRef } from 'react'
import { messageForError } from '../../shared/utils/errorMessages'
import { Button, EmptyState, ErrorNotice, Spinner } from '../../shared/ui'
import { useSessionOrders } from '../hooks/useSessionOrders'
import { OrderListItem } from '../components/OrderListItem'
import styles from './OrderHistoryPage.module.css'

export function OrderHistoryPage() {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isRefetchError,
  } = useSessionOrders()

  const sentinelRef = useRef<HTMLDivElement>(null)

  // 무한 스크롤: sentinel이 보이면 다음 페이지를 불러온다.
  useEffect(() => {
    const el = sentinelRef.current
    if (!el || !hasNextPage) return
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && hasNextPage && !isFetchingNextPage) {
        void fetchNextPage()
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const orders = data?.pages.flatMap((p) => p.items) ?? []
  const hasData = orders.length > 0

  // 초기 로딩 오류 (데이터 없음).
  if (isLoading) return <Spinner />
  if (isError && !hasData) {
    return (
      <div className={styles.errorWrap}>
        <ErrorNotice message={messageForError(error)} />
        <Button variant="primary" onClick={() => void refetch()} data-testid="order-history-retry-button">
          다시 시도
        </Button>
      </div>
    )
  }

  return (
    <div className={styles.wrap} data-testid="order-history-page">
      {/* 백그라운드 재조회 실패 + 기존 데이터 유지 시 작은 안내 */}
      {isRefetchError && hasData ? (
        <div role="status" className={styles.notice} data-testid="order-history-polling-notice">
          연결이 불안정해요. 다시 불러오는 중...
        </div>
      ) : null}

      {!hasData ? (
        <EmptyState message="주문 내역이 없어요" data-testid="order-history-empty" />
      ) : (
        <ul className={styles.list}>
          {orders.map((order) => (
            <li key={order.id}>
              <OrderListItem order={order} />
            </li>
          ))}
        </ul>
      )}

      <div ref={sentinelRef} data-testid="order-history-sentinel" aria-hidden="true" />
      {isFetchingNextPage ? <Spinner label="더 불러오는 중..." /> : null}
    </div>
  )
}
