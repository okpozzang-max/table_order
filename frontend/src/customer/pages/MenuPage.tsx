import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Menu } from '../../shared/api/types'
import { messageForError } from '../../shared/utils/errorMessages'
import { Button, EmptyState, ErrorNotice, Spinner, useToast } from '../../shared/ui'
import { useMenus } from '../hooks/useMenus'
import { useCart } from '../cart/CartProvider'
import { CategorySidebar } from '../components/CategorySidebar'
import { MenuCard } from '../components/MenuCard'
import { CartPanel } from '../components/CartPanel'
import { OrderConfirmModal } from '../components/OrderConfirmModal'
import styles from './MenuPage.module.css'

const MAX_QUANTITY_MESSAGE = '한 메뉴는 최대 20개까지 담을 수 있어요.'

export function MenuPage() {
  const { data, isLoading, isError, error, refetch } = useMenus()
  const cart = useCart()
  const toast = useToast()

  const [orderOpen, setOrderOpen] = useState(false)
  const [activeCategory, setActiveCategory] = useState<string | null>(null)

  const sectionRefs = useRef(new Map<string, HTMLElement>())
  const categories = useMemo(() => (data ?? []).map((g) => g.category), [data])

  useEffect(() => {
    if (activeCategory === null && categories.length > 0) {
      setActiveCategory(categories[0])
    }
  }, [categories, activeCategory])

  const setSectionRef = useCallback((category: string, el: HTMLElement | null) => {
    if (el) sectionRefs.current.set(category, el)
    else sectionRefs.current.delete(category)
  }, [])

  const handleSelectCategory = useCallback((category: string) => {
    setActiveCategory(category)
    sectionRefs.current.get(category)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // 스크롤 스파이: 보이는 섹션을 현재 카테고리로 강조한다.
  useEffect(() => {
    if (categories.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (visible) {
          const cat = (visible.target as HTMLElement).dataset.category
          if (cat) setActiveCategory(cat)
        }
      },
      { rootMargin: '0px 0px -60% 0px', threshold: [0, 0.25, 0.5, 1] },
    )
    sectionRefs.current.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [categories])

  const handleAdd = useCallback(
    (menu: Menu) => {
      const r = cart.add(menu)
      if (r === 'max') toast.show('info', MAX_QUANTITY_MESSAGE)
    },
    [cart, toast],
  )

  const handleIncreaseBlocked = useCallback(() => {
    toast.show('info', MAX_QUANTITY_MESSAGE)
  }, [toast])

  if (isLoading) return <Spinner />
  if (isError) {
    return (
      <div className={styles.errorWrap}>
        <ErrorNotice message={messageForError(error)} />
        <Button variant="primary" onClick={() => void refetch()} data-testid="menu-page-retry-button">
          다시 시도
        </Button>
      </div>
    )
  }

  const groups = data ?? []

  return (
    <div className={styles.layout} data-testid="menu-page">
      <CategorySidebar
        categories={categories}
        activeCategory={activeCategory}
        onSelect={handleSelectCategory}
      />

      <main className={styles.menus}>
        {groups.length === 0 ? (
          <EmptyState message="등록된 메뉴가 없어요" data-testid="menu-page-empty" />
        ) : (
          groups.map((group) => (
            <section
              key={group.category}
              ref={(el) => setSectionRef(group.category, el)}
              data-category={group.category}
              className={styles.section}
              data-testid={`menu-page-section-${group.category}`}
            >
              <h2 className={styles.sectionTitle}>{group.category}</h2>
              <div className={styles.grid}>
                {group.menus.map((menu) => (
                  <MenuCard key={menu.id} menu={menu} onAdd={handleAdd} />
                ))}
              </div>
            </section>
          ))
        )}
      </main>

      <CartPanel onOrder={() => setOrderOpen(true)} onIncreaseBlocked={handleIncreaseBlocked} />

      <OrderConfirmModal open={orderOpen} onClose={() => setOrderOpen(false)} />
    </div>
  )
}
