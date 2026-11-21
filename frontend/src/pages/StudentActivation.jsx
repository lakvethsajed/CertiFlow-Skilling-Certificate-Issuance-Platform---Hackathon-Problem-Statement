import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { KeyRound } from 'lucide-react'

import { studentApi } from '../services/api'

function RegistrationFields() {
  return (
    <>
      <label>
        Student ID
        <input name="student_id" maxLength={250} required />
      </label>
      <label>
        Secret activation code
        <input name="activation_code" type="password" autoComplete="off" maxLength={24} required />
      </label>
    </>
  )
}

export function NewPasswordFields() {
  return (
    <>
      <label>
        New password
        <input
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          maxLength={72}
          required
        />
      </label>
      <label>
        Confirm password
        <input
          name="confirm_password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          maxLength={72}
          required
        />
      </label>
    </>
  )
}

export function StudentActivation() {
  const [grant, setGrant] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(event) {
    event.preventDefault()
    const fields = Object.fromEntries(new FormData(event.currentTarget))
    setError('')
    setBusy(true)
    try {
      if (!grant) {
        const result = await studentApi.verifyCode(fields)
        setGrant(result.grant)
      } else {
        if (fields.password !== fields.confirm_password) throw new Error('Passwords do not match.')
        await studentApi.activate({ ...fields, grant })
        navigate('/student/login?notice=activated', { replace: true })
      }
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="signed-out">
      <form key={grant ? 'password' : 'code'} className="card auth-card" onSubmit={submit}>
        <span className="brand-mark">
          <KeyRound size={24} />
        </span>
        <div className="auth-heading">
          <h1>{grant ? 'Create your password' : 'Activate your account'}</h1>
          <p>
            {grant
              ? 'Use at least 12 characters.'
              : 'Enter your Student ID and the secret code provided by your Training Centre.'}
          </p>
        </div>
        {grant ? <NewPasswordFields /> : <RegistrationFields />}
        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
        <button className="button primary" disabled={busy}>
          {busy ? 'Please wait…' : grant ? 'Activate account' : 'Continue'}
        </button>
        {grant && (
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={() => {
              setGrant('')
              setError('')
            }}
          >
            Back to activation code
          </button>
        )}
        <Link className="auth-link" to="/student/login">
          Back to student sign-in
        </Link>
      </form>
    </main>
  )
}
