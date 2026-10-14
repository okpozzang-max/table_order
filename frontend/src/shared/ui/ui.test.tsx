import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { act } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './Button'
import { ConfirmDialog } from './ConfirmDialog'
import { FormField } from './FormField'
import { Modal } from './Modal'
import { StatusBadge } from './StatusBadge'
import { ToastProvider, useToast } from './Toast'

describe('Button', () => {
  it('loading 중에는 클릭이 무시되고 비활성화된다', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick} data-testid="b">
        저장
      </Button>,
    )
    const btn = screen.getByTestId('b')
    expect(btn).toBeDisabled()
    await userEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('Modal', () => {
  it('role=dialog 이고 제목과 연결된다', () => {
    render(
      <Modal open title="제목" onClose={() => {}}>
        내용
      </Modal>,
    )
    expect(screen.getByRole('dialog', { name: '제목' })).toBeInTheDocument()
  })

  it('open=false이면 렌더링하지 않는다', () => {
    render(
      <Modal open={false} title="제목" onClose={() => {}}>
        내용
      </Modal>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('Esc로 닫는다. dismissible=false이면 닫지 않는다', async () => {
    const onClose = vi.fn()
    const { rerender } = render(
      <Modal open title="t" onClose={onClose}>
        <button>확인</button>
      </Modal>,
    )
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    rerender(
      <Modal open title="t" onClose={onClose} dismissible={false}>
        <button>확인</button>
      </Modal>,
    )
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Tab 포커스가 모달 안에서 순환한다', async () => {
    render(
      <Modal open title="t" onClose={() => {}} footer={<button>둘째</button>}>
        <button>첫째</button>
      </Modal>,
    )
    expect(screen.getByText('첫째')).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByText('둘째')).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByText('첫째')).toHaveFocus()
    await userEvent.tab({ shift: true })
    expect(screen.getByText('둘째')).toHaveFocus()
  })
})

describe('ConfirmDialog', () => {
  it('확인/취소 콜백을 호출한다', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(<ConfirmDialog open message="삭제할까요?" onConfirm={onConfirm} onCancel={onCancel} />)
    await userEvent.click(screen.getByTestId('confirm-dialog-confirm-button'))
    await userEvent.click(screen.getByTestId('confirm-dialog-cancel-button'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('처리 중에는 확인/취소가 비활성이고 Esc로 닫히지 않는다', async () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog open pending message="처리 중" onConfirm={() => {}} onCancel={onCancel} />)
    expect(screen.getByTestId('confirm-dialog-confirm-button')).toBeDisabled()
    expect(screen.getByTestId('confirm-dialog-cancel-button')).toBeDisabled()
    await userEvent.keyboard('{Escape}')
    expect(onCancel).not.toHaveBeenCalled()
  })
})

describe('FormField', () => {
  it('오류가 있으면 role=alert 로 표시하고 입력과 연결한다', () => {
    render(
      <FormField label="이름" error="필수입니다">
        {(p) => <input {...p} />}
      </FormField>,
    )
    const input = screen.getByLabelText('이름')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('필수입니다')
    expect(input.getAttribute('aria-describedby')).toContain(alert.id)
  })

  it('오류가 없으면 alert가 없다', () => {
    render(<FormField label="이름">{(p) => <input {...p} />}</FormField>)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByLabelText('이름')).toHaveAttribute('aria-invalid', 'false')
  })
})

describe('StatusBadge', () => {
  it('상태를 텍스트로 표시한다', () => {
    const { rerender } = render(<StatusBadge status="PENDING" />)
    expect(screen.getByText('대기중')).toBeInTheDocument()
    rerender(<StatusBadge status="PREPARING" />)
    expect(screen.getByText('준비중')).toBeInTheDocument()
    rerender(<StatusBadge status="COMPLETED" />)
    expect(screen.getByText('완료')).toBeInTheDocument()
  })
})

describe('Toast', () => {
  function Trigger() {
    const toast = useToast()
    return (
      <>
        <button onClick={() => toast.success('성공했어요')}>성공</button>
        <button onClick={() => toast.error('실패했어요')}>실패</button>
      </>
    )
  }

  it('성공은 3초, 오류는 5초 뒤에 사라진다', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      render(
        <ToastProvider>
          <Trigger />
        </ToastProvider>,
      )
      await userEvent.click(screen.getByText('성공'))
      await userEvent.click(screen.getByText('실패'))
      expect(screen.getByText('성공했어요')).toBeInTheDocument()
      expect(screen.getByRole('alert')).toHaveTextContent('실패했어요')

      await act(async () => {
        await vi.advanceTimersByTimeAsync(3100)
      })
      await waitFor(() => expect(screen.queryByText('성공했어요')).not.toBeInTheDocument())
      expect(screen.getByText('실패했어요')).toBeInTheDocument()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2100)
      })
      await waitFor(() => expect(screen.queryByText('실패했어요')).not.toBeInTheDocument())
    } finally {
      vi.useRealTimers()
    }
  })
})
