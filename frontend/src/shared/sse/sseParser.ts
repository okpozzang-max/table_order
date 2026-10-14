export interface ParsedSseEvent {
  event: string
  data: string
}

/**
 * text/event-stream 증분 파서.
 * - 청크가 줄 중간에서 끊겨도 처리한다.
 * - `:`로 시작하는 줄(주석, keep-alive)은 무시한다.
 * - 빈 줄에서 이벤트를 확정한다. data 줄이 여러 개면 \n으로 이어 붙인다.
 */
export class SseParser {
  private buffer = ''
  private eventName = ''
  private dataLines: string[] = []

  push(chunk: string): ParsedSseEvent[] {
    this.buffer += chunk
    const out: ParsedSseEvent[] = []

    for (;;) {
      const idx = this.nextLineEnd()
      if (idx === null) break
      const { end, next } = idx
      const line = this.buffer.slice(0, end)
      this.buffer = this.buffer.slice(next)

      if (line === '') {
        if (this.dataLines.length > 0) {
          out.push({ event: this.eventName || 'message', data: this.dataLines.join('\n') })
        }
        this.eventName = ''
        this.dataLines = []
        continue
      }
      if (line.startsWith(':')) continue

      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      let value = colon === -1 ? '' : line.slice(colon + 1)
      if (value.startsWith(' ')) value = value.slice(1)

      if (field === 'event') this.eventName = value
      else if (field === 'data') this.dataLines.push(value)
      // id, retry 등은 사용하지 않는다
    }
    return out
  }

  private nextLineEnd(): { end: number; next: number } | null {
    for (let i = 0; i < this.buffer.length; i++) {
      const ch = this.buffer[i]
      if (ch === '\n') return { end: i, next: i + 1 }
      if (ch === '\r') {
        if (i + 1 >= this.buffer.length) return null // \r\n의 \n이 다음 청크에 올 수 있음
        return { end: i, next: this.buffer[i + 1] === '\n' ? i + 2 : i + 1 }
      }
    }
    return null
  }
}
