import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach } from 'vitest'
import { cleanup } from '@testing-library/react'

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

afterEach(() => {
  cleanup()
})

// jsdom에는 IntersectionObserver / scrollIntoView / matchMedia가 없다.
class NoopIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}
if (!('IntersectionObserver' in globalThis)) {
  Object.defineProperty(globalThis, 'IntersectionObserver', {
    value: NoopIntersectionObserver,
    writable: true,
  })
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
