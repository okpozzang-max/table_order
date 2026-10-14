import { describe, expect, it } from 'vitest'
import { SseParser } from './sseParser'

describe('SseParser', () => {
  it('완결된 이벤트를 파싱한다', () => {
    const p = new SseParser()
    const out = p.push('event: order_created\ndata: {"a":1}\n\n')
    expect(out).toEqual([{ event: 'order_created', data: '{"a":1}' }])
  })

  it('청크가 줄 중간에서 나뉘어도 처리한다', () => {
    const p = new SseParser()
    expect(p.push('event: order_cr')).toEqual([])
    expect(p.push('eated\nda')).toEqual([])
    expect(p.push('ta: {"x":')).toEqual([])
    expect(p.push('2}\n')).toEqual([])
    expect(p.push('\n')).toEqual([{ event: 'order_created', data: '{"x":2}' }])
  })

  it('한 청크의 여러 이벤트를 모두 반환한다', () => {
    const p = new SseParser()
    const out = p.push('event: a\ndata: 1\n\nevent: b\ndata: 2\n\n')
    expect(out.map((e) => e.event)).toEqual(['a', 'b'])
  })

  it('주석(keep-alive)은 무시한다', () => {
    const p = new SseParser()
    expect(p.push(': keep-alive\n\n')).toEqual([])
    expect(p.push(': ping\nevent: x\ndata: y\n\n')).toEqual([{ event: 'x', data: 'y' }])
  })

  it('data 줄이 여러 개면 줄바꿈으로 잇는다', () => {
    const p = new SseParser()
    expect(p.push('data: a\ndata: b\n\n')).toEqual([{ event: 'message', data: 'a\nb' }])
  })

  it('CRLF 줄바꿈과 \\r\\n이 청크 경계에서 나뉘는 경우를 처리한다', () => {
    const p = new SseParser()
    expect(p.push('event: a\r\ndata: 1\r')).toEqual([])
    expect(p.push('\n\r\n')).toEqual([{ event: 'a', data: '1' }])
  })

  it('data 없이 빈 줄만 오면 이벤트를 만들지 않는다', () => {
    const p = new SseParser()
    expect(p.push('event: a\n\n')).toEqual([])
  })
})
