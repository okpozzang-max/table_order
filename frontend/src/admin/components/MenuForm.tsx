import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button, FormField, Modal, useToast } from '../../shared/ui'
import { validateMenuForm } from '../../shared/utils/validators'
import type { FieldErrors } from '../../shared/utils/validators'
import { messageForError } from '../../shared/utils/errorMessages'
import { ApiError } from '../../shared/api/errors'
import type { Menu } from '../../shared/api/types'
import { useCreateMenu, useUpdateMenu } from '../hooks/useAdminQueries'
import styles from './MenuForm.module.css'

export interface MenuFormProps {
  open: boolean
  /** 수정 대상 메뉴. null이면 등록 모드 */
  menu: Menu | null
  /** datalist 자동완성용 기존 카테고리 목록 */
  categories: string[]
  onClose: () => void
}

export function MenuForm({ open, menu, categories, onClose }: MenuFormProps) {
  const toast = useToast()
  const createMenu = useCreateMenu()
  const updateMenu = useUpdateMenu()

  const [name, setName] = useState(menu?.name ?? '')
  const [price, setPrice] = useState(menu ? String(menu.price) : '')
  const [description, setDescription] = useState(menu?.description ?? '')
  const [category, setCategory] = useState(menu?.category ?? '')
  const [imageUrl, setImageUrl] = useState(menu?.imageUrl ?? '')
  const [errors, setErrors] = useState<FieldErrors>({})

  const isEdit = menu != null
  const pending = createMenu.isPending || updateMenu.isPending

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const result = validateMenuForm({ name, price, description, category, imageUrl })
    if (!result.value) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    const input = result.value

    const onError = (err: unknown) => {
      if (err instanceof ApiError && err.code === 'VALIDATION_ERROR') {
        setErrors(err.fields)
      } else {
        toast.error(messageForError(err))
      }
    }

    if (isEdit && menu) {
      updateMenu.mutate(
        { menuId: menu.id, input },
        {
          onSuccess: () => {
            toast.success('메뉴를 수정했어요.')
            onClose()
          },
          onError,
        },
      )
    } else {
      createMenu.mutate(input, {
        onSuccess: () => {
          toast.success('메뉴를 등록했어요.')
          onClose()
        },
        onError,
      })
    }
  }

  return (
    <Modal
      open={open}
      title={isEdit ? '메뉴 수정' : '메뉴 등록'}
      onClose={onClose}
      data-testid="menu-form-modal"
      footer={
        <>
          <Button onClick={onClose} disabled={pending} data-testid="menu-form-cancel-button">
            취소
          </Button>
          <Button
            type="submit"
            form="menu-form"
            variant="primary"
            loading={pending}
            data-testid="menu-form-submit-button"
          >
            저장
          </Button>
        </>
      }
    >
      <form id="menu-form" className={styles.form} onSubmit={handleSubmit} noValidate>
        <FormField label="메뉴명" error={errors.name} data-testid="menu-form-name-field">
          {(p) => (
            <input
              {...p}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={styles.input}
              data-testid="menu-form-name-input"
            />
          )}
        </FormField>
        <FormField label="가격" error={errors.price} data-testid="menu-form-price-field">
          {(p) => (
            <input
              {...p}
              type="text"
              inputMode="numeric"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className={styles.input}
              data-testid="menu-form-price-input"
            />
          )}
        </FormField>
        <FormField label="설명" error={errors.description} data-testid="menu-form-description-field">
          {(p) => (
            <textarea
              {...p}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={styles.textarea}
              rows={3}
              data-testid="menu-form-description-input"
            />
          )}
        </FormField>
        <FormField label="카테고리" error={errors.category} data-testid="menu-form-category-field">
          {(p) => (
            <>
              <input
                {...p}
                type="text"
                list="menu-form-category-list"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className={styles.input}
                data-testid="menu-form-category-input"
              />
              <datalist id="menu-form-category-list">
                {categories.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </>
          )}
        </FormField>
        <FormField label="이미지 주소 (선택)" error={errors.imageUrl} data-testid="menu-form-image-field">
          {(p) => (
            <input
              {...p}
              type="text"
              inputMode="url"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              className={styles.input}
              data-testid="menu-form-image-input"
            />
          )}
        </FormField>
      </form>
    </Modal>
  )
}
