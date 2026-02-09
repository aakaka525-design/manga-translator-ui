import {
  clearSessionToken,
  getSessionToken,
  setSessionToken,
  translateApi,
} from '@/api'

describe('auth api helpers', () => {
  beforeEach(() => {
    clearSessionToken()
  })

  it('stores and clears session token', () => {
    setSessionToken('token-123')
    expect(getSessionToken()).toBe('token-123')

    clearSessionToken()
    expect(getSessionToken()).toBe('')
  })

  it('appends token to translate events url', () => {
    setSessionToken('abc123')
    const url = translateApi.getEventsUrl()
    expect(url).toContain('/api/v1/translate/events?token=')
    expect(url).toContain('abc123')
  })
})
