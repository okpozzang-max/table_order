import { useState } from 'react'
import { Button, ConfirmDialog, EmptyState, ErrorNotice, Spinner, useToast } from '../../shared/ui'
import { messageForError } from '../../shared/utils/errorMessages'
import type { Menu } from '../../shared/api/types'
import { useAdminMenus, useDeleteMenu, useReorderMenus } from '../hooks/useAdminQueries'
import { MenuListByCategory } from '../components/MenuListByCategory'
import { MenuForm } from '../components/MenuForm'
import styles from './MenuManagementPage.module.css'

type FormState = { open: boolean; menu: Menu | null }

export function MenuManagementPage() {
  const toast = useToast()
  const menusQuery = useAdminMenus()
  const deleteMenu = useDeleteMenu()
  const reorderMenus = useReorderMenus()

  const [form, setForm] = useState<FormState>({ open: false, menu: null })
  const [deleteTarget, setDeleteTarget] = useState<Menu | null>(null)

  const groups = menusQuery.data ?? []
  const categories = groups.map((g) => g.category)

  const handleMove = (category: string, orderedIds: number[]) => {
    reorderMenus.mutate(
      { category, orderedIds },
      {
        onError: (err) => toast.error(messageForError(err)),
      },
    )
  }

  const handleDelete = () => {
    if (!deleteTarget) return
    const target = deleteTarget
    deleteMenu.mutate(target.id, {
      onSuccess: () => {
        setDeleteTarget(null)
        toast.success('메뉴를 삭제했어요.')
      },
      onError: () => {
        setDeleteTarget(null)
        toast.error('메뉴를 삭제하지 못했어요.')
      },
    })
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>메뉴 관리</h1>
        <Button
          variant="primary"
          onClick={() => setForm({ open: true, menu: null })}
          data-testid="menu-create-button"
        >
          메뉴 등록
        </Button>
      </header>

      {menusQuery.isLoading ? <Spinner /> : null}
      {menusQuery.isError ? (
        <ErrorNotice message={messageForError(menusQuery.error)} data-testid="menu-list-error" />
      ) : null}
      {!menusQuery.isLoading && groups.length === 0 ? (
        <EmptyState message="등록된 메뉴가 없어요" data-testid="menu-list-empty" />
      ) : (
        <MenuListByCategory
          groups={groups}
          reorderPending={reorderMenus.isPending}
          onEdit={(menu) => setForm({ open: true, menu })}
          onDelete={(menu) => setDeleteTarget(menu)}
          onMove={handleMove}
        />
      )}

      {form.open ? (
        <MenuForm
          key={form.menu ? `edit-${form.menu.id}` : 'create'}
          open={form.open}
          menu={form.menu}
          categories={categories}
          onClose={() => setForm({ open: false, menu: null })}
        />
      ) : null}

      <ConfirmDialog
        open={deleteTarget != null}
        title="메뉴 삭제"
        message={deleteTarget ? `'${deleteTarget.name}'을(를) 삭제할까요?` : ''}
        confirmLabel="삭제"
        danger
        pending={deleteMenu.isPending}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        data-testid="menu-delete-confirm"
      />
    </div>
  )
}
