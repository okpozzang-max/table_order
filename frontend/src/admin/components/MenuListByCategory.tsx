import { Button } from '../../shared/ui'
import { formatKRW } from '../../shared/utils/format'
import type { CategoryMenus, Menu } from '../../shared/api/types'
import styles from './MenuListByCategory.module.css'

export interface MenuListByCategoryProps {
  groups: CategoryMenus[]
  /** 재정렬 요청이 진행 중이면 이동 버튼을 비활성화 */
  reorderPending: boolean
  onEdit: (menu: Menu) => void
  onDelete: (menu: Menu) => void
  /** 같은 카테고리 내에서 메뉴를 한 칸 이동. 전체 ID 순서를 재계산해 호출자에게 전달 */
  onMove: (category: string, orderedIds: number[]) => void
}

function moveWithin(ids: number[], index: number, direction: -1 | 1): number[] {
  const target = index + direction
  if (target < 0 || target >= ids.length) return ids
  const next = [...ids]
  const tmp = next[index]
  next[index] = next[target]
  next[target] = tmp
  return next
}

export function MenuListByCategory({
  groups,
  reorderPending,
  onEdit,
  onDelete,
  onMove,
}: MenuListByCategoryProps) {
  return (
    <div className={styles.wrap}>
      {groups.map((group) => {
        const orderedIds = group.menus.map((m) => m.id)
        return (
          <section key={group.category} className={styles.group} data-testid={`menu-category-${group.category}`}>
            <h3 className={styles.categoryTitle}>{group.category}</h3>
            <ul className={styles.list}>
              {group.menus.map((menu, idx) => (
                <li key={menu.id} className={styles.row} data-testid={`menu-row-${menu.id}`}>
                  <div className={styles.thumb} aria-hidden="true">
                    {menu.imageUrl ? (
                      <img src={menu.imageUrl} alt="" className={styles.thumbImg} />
                    ) : (
                      <span className={styles.thumbPlaceholder}>{menu.name.charAt(0)}</span>
                    )}
                  </div>
                  <div className={styles.info}>
                    <span className={styles.name}>{menu.name}</span>
                    <span className={styles.price}>{formatKRW(menu.price)}</span>
                  </div>
                  <div className={styles.actions}>
                    <Button onClick={() => onEdit(menu)} data-testid={`menu-row-edit-button-${menu.id}`}>
                      수정
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => onDelete(menu)}
                      data-testid={`menu-row-delete-button-${menu.id}`}
                    >
                      삭제
                    </Button>
                    <Button
                      disabled={idx === 0 || reorderPending}
                      onClick={() => onMove(group.category, moveWithin(orderedIds, idx, -1))}
                      aria-label={`${menu.name} 위로`}
                      data-testid={`menu-row-move-up-button-${menu.id}`}
                    >
                      위로
                    </Button>
                    <Button
                      disabled={idx === group.menus.length - 1 || reorderPending}
                      onClick={() => onMove(group.category, moveWithin(orderedIds, idx, 1))}
                      aria-label={`${menu.name} 아래로`}
                      data-testid={`menu-row-move-down-button-${menu.id}`}
                    >
                      아래로
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
