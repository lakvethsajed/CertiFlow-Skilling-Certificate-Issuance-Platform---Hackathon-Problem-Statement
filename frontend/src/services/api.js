export async function api(path, { method = 'GET', data, signal } = {}) {
  const response = await fetch('/api' + path, {
    method,
    credentials: 'same-origin',
    signal,
    headers: data === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data)
  })
  if (response.status === 204) return
  const payload = await response.json().catch(() => null)
  if (!response.ok || !payload) {
    if (response.status === 401 && !path.startsWith('/auth/') && path !== '/student/auth/login') {
      window.dispatchEvent(new Event('certiflow-session-expired'))
    }
    const error = new Error(
      payload?.message ??
        'Could not reach the CertiFlow API. Check that the backend is running and try again.'
    )
    error.status = response.status
    error.details = payload?.details
    throw error
  }
  return payload
}

export const authApi = {
  session: async () => (await api('/auth/session')).user,
  login: async (data) => {
    await api('/auth/login', { method: 'POST', data })
    const { user } = await api('/auth/session')
    if (!user)
      throw new Error(
        'Your browser did not keep the session. Allow cookies for this site and try again.'
      )
    return user
  },
  logout: () => api('/auth/logout', { method: 'POST' })
}
async function downloadCredentialCsv(batchId, studentId) {
  const action = studentId ? 'regenerate' : 'export'
  const response = await fetch(
    '/api/centre/batches/' + encodeURIComponent(batchId) + '/activation-codes/' + action,
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: studentId ? { 'Content-Type': 'application/json' } : undefined,
      body: studentId ? JSON.stringify({ student_id: studentId }) : undefined
    }
  )
  if (response.status === 401) window.dispatchEvent(new Event('certiflow-session-expired'))
  if (!response.ok || !response.headers.get('content-type')?.startsWith('text/csv')) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.message ?? 'Unable to download activation codes.')
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = 'activation-codes-' + batchId + '.csv'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const centreApi = {
  list: (signal) => api('/centre/batches', { signal }),
  downloadActivationCodes: downloadCredentialCsv,
  save: ({ id, ...data }) =>
    api('/centre/batches' + (id ? '/' + encodeURIComponent(id) : ''), {
      method: id ? 'PUT' : 'POST',
      data
    })
}
export const districtApi = {
  dashboard: (signal) => api('/district/dashboard', { signal }),
  list: (view, signal) => api('/district/batches?view=' + encodeURIComponent(view), { signal }),
  details: (id, signal) => api('/district/batches/' + encodeURIComponent(id), { signal }),
  decide: (id, action, data) =>
    api('/district/batches/' + encodeURIComponent(id) + '/' + action, { method: 'POST', data })
}

export const qualityApi = {
  dashboard: (signal) => api('/quality/dashboard', { signal }),
  list: (query, signal) => api('/quality/batches?' + query, { signal }),
  details: (id, revision, signal) =>
    api(
      '/quality/batches/' +
        encodeURIComponent(id) +
        (revision ? '?revision=' + encodeURIComponent(revision) : ''),
      { signal }
    ),
  decide: (id, action, data) =>
    api('/quality/batches/' + encodeURIComponent(id) + '/' + action, { method: 'POST', data })
}

export const stateApi = {
  dashboard: (signal) => api('/state/dashboard', { signal }),
  list: (query, signal) => api('/state/batches?' + query, { signal }),
  details: (id, revision, signal) =>
    api(
      '/state/batches/' +
        encodeURIComponent(id) +
        (revision ? '?revision=' + encodeURIComponent(revision) : ''),
      { signal }
    ),
  decide: (id, action, data) =>
    api('/state/batches/' + encodeURIComponent(id) + '/' + action, { method: 'POST', data })
}

export const studentApi = {
  verifyCode: (data) => api('/student/activation/verify', { method: 'POST', data }),
  activate: (data) => api('/student/activation/complete', { method: 'POST', data }),
  login: async (data) => {
    await api('/student/auth/login', { method: 'POST', data })
    const user = await authApi.session()
    if (user?.role !== 'CANDIDATE')
      throw new Error('Allow cookies for this site and sign in again.')
    return user
  },
  logout: () => api('/student/auth/logout', { method: 'POST' }),
  changePassword: (data) => api('/student/auth/change-password', { method: 'POST', data }),
  profile: (signal) => api('/student/profile', { signal }),
  certificates: (page, signal) => api('/student/certificates?page=' + page, { signal }),
  certificate: (id, signal) => api('/student/certificates/' + encodeURIComponent(id), { signal }),
  download: async (id, number) => {
    const response = await fetch(
      '/api/student/certificates/' + encodeURIComponent(id) + '/download',
      {
        credentials: 'same-origin'
      }
    )
    if (response.status === 401) window.dispatchEvent(new Event('certiflow-session-expired'))
    if (!response.ok || !response.headers.get('content-type')?.startsWith('application/pdf')) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.message ?? 'The certificate PDF is unavailable.')
    }
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = number + '.pdf'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
