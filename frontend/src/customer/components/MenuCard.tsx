import { useState } from 'react'
import type { Menu } from '../../shared/api/types'
import { formatKRW } from '../../shared/utils/format'
import { Button } from '../../shared/ui'
import styles from './MenuCard.module.css'

export interface MenuCardProps {
  menu: Menu
  onAdd(menu: Menu): void
}

export function MenuCard({ menu, onAdd }: MenuCardProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const showImage = Boolean(menu.imageUrl) && !imageFailed

  return (
    <article className={styles.card} data-testid={`menu-card-${menu.id}`}>
      <div className={styles.imageWrap}>
        {showImage ? (
          <img
            className={styles.image}
            src={menu.imageUrl as string}
            alt=""
            onError={() => setImageFailed(true)}
            data-testid={`menu-card-image-${menu.id}`}
          />
        ) : (
          <div className={styles.placeholder} aria-hidden="true" data-testid={`menu-card-placeholder-${menu.id}`}>
            {menu.name.slice(0, 1)}
          </div>
        )}
      </div>
      <div className={styles.body}>
        <h3 className={styles.name}>{menu.name}</h3>
        {menu.description ? <p className={styles.description}>{menu.description}</p> : null}
        <div className={styles.footer}>
          <span className={styles.price}>{formatKRW(menu.price)}</span>
          <Button
            variant="primary"
            onClick={() => onAdd(menu)}
            aria-label={`${menu.name} 담기`}
            data-testid={`menu-card-add-button-${menu.id}`}
          >
            담기
          </Button>
        </div>
      </div>
    </article>
  )
}
