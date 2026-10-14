import styles from './CategorySidebar.module.css'

export interface CategorySidebarProps {
  categories: string[]
  activeCategory: string | null
  onSelect(category: string): void
}

/** 좌측 세로 카테고리 사이드바. 클릭 시 해당 섹션으로 이동, 스크롤 스파이로 현재 항목 강조. */
export function CategorySidebar({ categories, activeCategory, onSelect }: CategorySidebarProps) {
  return (
    <nav className={styles.sidebar} aria-label="카테고리" data-testid="category-sidebar">
      <ul className={styles.list}>
        {categories.map((category) => {
          const active = category === activeCategory
          return (
            <li key={category}>
              <button
                type="button"
                className={`${styles.item} ${active ? styles.active : ''}`}
                aria-current={active ? 'true' : undefined}
                onClick={() => onSelect(category)}
                data-testid={`category-sidebar-item-${category}`}
              >
                {category}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
