import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '../../shared/ui'
import styles from './OrderCompletePage.module.css'

const COUNTDOWN_START = 5

interface OrderCompleteState {
  orderNumber?: string
}

export function OrderCompletePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = (location.state ?? {}) as OrderCompleteState
  const orderNumber = state.orderNumber

  const [remaining, setRemaining] = useState(COUNTDOWN_START)
  const navigatedRef = useRef(false)

  const goToMenu = () => {
    if (navigatedRef.current) return
    navigatedRef.current = true
    navigate('/customer/menu')
  }

  useEffect(() => {
    if (!orderNumber) return
    const timer = setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
    // orderNumber가 바뀌지 않는 전제 (한 번만 설정)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderNumber])

  // 0초에 도달하면 메뉴로 이동한다 (렌더 중이 아니라 effect에서).
  useEffect(() => {
    if (orderNumber && remaining <= 0) goToMenu()
    // goToMenu는 navigatedRef로 1회만 실행된다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, orderNumber])

  // 주문 번호 상태가 없으면(새로고침 등) 메뉴로 되돌린다.
  if (!orderNumber) {
    return <Navigate to="/customer/menu" replace />
  }

  return (
    <div className={styles.wrap} data-testid="order-complete-page">
      <div className={styles.card}>
        <div className={styles.check} aria-hidden="true">
          ✓
        </div>
        <h1 className={styles.title}>주문이 접수되었어요</h1>
        <p className={styles.number} data-testid="order-complete-number">
          주문 번호 #{orderNumber}
        </p>
        <p className={styles.countdown} data-testid="order-complete-countdown">
          {remaining}초 후 메뉴 화면으로 이동해요.
        </p>
        <Button variant="primary" onClick={goToMenu} data-testid="order-complete-go-menu-button">
          바로 메뉴로 이동
        </Button>
      </div>
    </div>
  )
}
