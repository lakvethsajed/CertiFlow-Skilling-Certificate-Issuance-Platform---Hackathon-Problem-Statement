import React, { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, BadgeCheck, Eye, EyeOff, ShieldCheck } from 'lucide-react'

import { api, authApi, studentApi } from '../services/api'

export function Login({ onLogin, student = false }) {
  const [params] = useSearchParams()
  const notice =
    student &&
    (params.get('notice') === 'activated'
      ? 'Account activated. Sign in with your registered email.'
      : params.get('notice') === 'password'
        ? 'Password updated. Sign in with your new password.'
        : '')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  async function signIn(event) {
    event.preventDefault()
    const credentials = Object.fromEntries(new FormData(event.currentTarget))
    setPending(true)
    setError('')
    try {
      onLogin(await (student ? studentApi : authApi).login(credentials))
    } catch (failure) {
      setError(failure.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="signed-out">
      <form className="card auth-card" onSubmit={signIn}>
        <span className="brand-mark">
          <ShieldCheck />
        </span>
        <div className="auth-heading">
          <h1>{student ? 'Student sign-in' : 'Sign in to CertiFlow'}</h1>
          <p>
            {student
              ? 'Use your registered email to access your certificates.'
              : 'Access your staff workspace.'}
          </p>
        </div>
        {notice && (
          <p className="notice success" role="status">
            {notice}
          </p>
        )}
        <label>
          Email
          <input name="email" type="email" autoComplete="username" required />
        </label>
        <div className="auth-field">
          <label htmlFor="signin-password">Password</label>
          <div className="password-field">
            <input
              id="signin-password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              className="icon-button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? (
                <EyeOff size={18} aria-hidden="true" />
              ) : (
                <Eye size={18} aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
        <button className="button primary" disabled={pending}>
          {pending ? 'Signing in…' : 'Sign in'}
        </button>
        {student ? (
          <>
            <Link className="auth-link" to="/student/activate">
              Activate account
            </Link>
            <Link to="/">Staff sign-in</Link>
          </>
        ) : (
          <Link className="auth-link" to="/student/login">
            Student Portal
          </Link>
        )}
        <Link className="auth-link" to="/verify">
          <BadgeCheck size={17} />
          Verify a certificate
        </Link>
      </form>
    </main>
  )
}

export function VerifyCertificate() {
  const [result, setResult] = useState(null)
  const [pending, setPending] = useState(false)
  async function verify(event) {
    event.preventDefault()
    const code = new FormData(event.currentTarget).get('code').trim()
    setPending(true)
    setResult(null)
    try {
      const certificate = await api('/certificates/' + encodeURIComponent(code))
      setResult({
        message:
          'Certificate verified. Issued ' +
          new Date(certificate.issuedAt).toLocaleDateString('en-IN') +
          '.'
      })
    } catch (error) {
      setResult({ message: error.message, error: true })
    } finally {
      setPending(false)
    }
  }
  return (
    <main className="signed-out">
      <form className="card auth-card" onSubmit={verify}>
        <span className="brand-mark">
          <BadgeCheck />
        </span>
        <div className="auth-heading">
          <h1>Verify a certificate</h1>
          <p>Enter the verification code printed on the certificate.</p>
        </div>
        <label>
          Certificate code
          <input name="code" required maxLength={128} />
        </label>
        <button className="button primary" disabled={pending}>
          Verify
        </button>
        {result && (
          <p className={'notice ' + (result.error ? 'error' : 'success')} role="status">
            {result.message}
          </p>
        )}
        <Link className="auth-link" to="/">
          <ArrowLeft size={17} />
          Return to CertiFlow
        </Link>
      </form>
    </main>
  )
}
