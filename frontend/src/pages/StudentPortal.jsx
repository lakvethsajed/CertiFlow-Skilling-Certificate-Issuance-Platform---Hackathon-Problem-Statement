import React, { useState } from 'react'
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useParams,
  useSearchParams
} from 'react-router-dom'
import { Award, Download, LogOut, ShieldCheck, UserRound } from 'lucide-react'

import { EmptyState, formatDate, PageHeading, StatusBadge } from '../components/BatchUI'
import { studentApi } from '../services/api'
import { LoadError, useReviewData } from './District'
import { NewPasswordFields } from './StudentActivation'
import '../styles/student.css'

function StudentLayout({ onLogout }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function signOut() {
    setBusy(true)
    try {
      await onLogout()
    } catch (failure) {
      setError(failure.message)
      setBusy(false)
    }
  }

  return (
    <div className="student-shell">
      <header className="student-header">
        <Link className="student-brand" to="/student/dashboard">
          <span className="brand-mark">
            <ShieldCheck size={22} />
          </span>
          CertiFlow
        </Link>
        <nav aria-label="Student Portal">
          <NavLink to="/student/dashboard">
            <Award size={17} /> Certificates
          </NavLink>
          <NavLink to="/student/profile">
            <UserRound size={17} /> Profile
          </NavLink>
        </nav>
        <button className="button secondary" onClick={signOut} disabled={busy}>
          <LogOut size={16} /> Sign out
        </button>
      </header>
      <main className="content student-content">
        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
        <Outlet />
      </main>
    </div>
  )
}

export function StudentWorkspace({ onLogout, onPasswordChanged }) {
  return (
    <Routes>
      <Route element={<StudentLayout onLogout={onLogout} />}>
        <Route path="/student/dashboard" element={<StudentDashboard />} />
        <Route path="/student/certificates/:id" element={<CertificateDetails />} />
        <Route
          path="/student/profile"
          element={<StudentProfile onPasswordChanged={onPasswordChanged} />}
        />
        <Route path="*" element={<Navigate to="/student/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

function ProfileCard({ profile }) {
  const fields = [
    ['Name', profile.name],
    ['Student ID', profile.student_id],
    ['Registered email', profile.email],
    ['Phone', profile.phone_number],
    ['Course', profile.course],
    ['Certificates issued', profile.total_issued]
  ]
  return (
    <section className="card section">
      <h2>Student Profile</h2>
      <dl className="details-grid student-fields">
        {fields
          .filter(([, value]) => value !== null && value !== '')
          .map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
      </dl>
    </section>
  )
}

function CertificateDownload({ certificate }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (certificate.status !== 'ACTIVE')
    return <p>Downloads are unavailable for cancelled certificates.</p>

  async function download() {
    setBusy(true)
    setError('')
    try {
      await studentApi.download(certificate.id, certificate.number)
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="student-download">
      <button className="button primary" disabled={busy} onClick={download}>
        <Download size={16} /> {busy ? 'Downloading…' : 'Download PDF'}
      </button>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

function CertificateRecord({ certificate, detailed = false }) {
  return (
    <article className="card section stack">
      <div className="student-certificate-header">
        <span className="stat-icon blue">
          <Award size={21} />
        </span>
        <StatusBadge status={certificate.status === 'ACTIVE' ? 'Active' : 'Cancelled'} />
      </div>
      <h2>{certificate.course}</h2>
      <dl className="details-grid student-fields">
        <div className="student-certificate-number">
          <dt>Certificate Number</dt>
          <dd>{certificate.number}</dd>
        </div>
        <div>
          <dt>Assessment Date</dt>
          <dd>{formatDate(certificate.assessment_date)}</dd>
        </div>
        <div>
          <dt>Issue Date</dt>
          <dd>{formatDate(certificate.issued_at)}</dd>
        </div>
      </dl>
      <div className="inline student-certificate-actions">
        {!detailed && (
          <Link className="button secondary" to={'/student/certificates/' + certificate.id}>
            View Certificate
          </Link>
        )}
        <CertificateDownload certificate={certificate} />
      </div>
    </article>
  )
}

function CertificateList() {
  const [params, setParams] = useSearchParams()
  const value = Number(params.get('page'))
  const page = Number.isSafeInteger(value) && value > 0 ? value : 1
  const state = useReviewData(
    (signal) => studentApi.certificates(page, signal),
    'student-certificates-' + page
  )

  if (!state.data) return <LoadError state={state} />
  const { records, total, page_size: pageSize } = state.data
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <>
      {records.length ? (
        <div className="student-certificate-grid">
          {records.map((certificate) => (
            <CertificateRecord key={certificate.id} certificate={certificate} />
          ))}
        </div>
      ) : (
        <div className="card">
          <EmptyState
            title={total ? 'No certificates on this page.' : "You don't have any certificates yet."}
          >
            {!total &&
              'Once your training batch is approved and your certificate is issued, it will appear here.'}
          </EmptyState>
        </div>
      )}
      {(pages > 1 || page > 1) && (
        <nav className="pagination table-footer" aria-label="Certificate pages">
          <button
            className="button secondary"
            disabled={page <= 1}
            onClick={() => setParams({ page: page - 1 })}
          >
            Previous
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button
            className="button secondary"
            disabled={page >= pages}
            onClick={() => setParams({ page: page + 1 })}
          >
            Next
          </button>
        </nav>
      )}
    </>
  )
}

function StudentDashboard() {
  const state = useReviewData(studentApi.profile, 'student-dashboard')
  return (
    <>
      <PageHeading
        title={state.data ? 'Welcome, ' + state.data.name : 'Student Dashboard'}
        subtitle="View your training certificates."
      />
      <div className="stack">
        {state.data ? <ProfileCard profile={state.data} /> : <LoadError state={state} />}
        <section className="stack">
          <h2>My Certificates</h2>
          <CertificateList />
        </section>
      </div>
    </>
  )
}

function CertificateDetails() {
  const { id } = useParams()
  const state = useReviewData((signal) => studentApi.certificate(id, signal), id)
  return (
    <>
      <PageHeading title="Certificate Details">
        <Link className="button secondary" to="/student/dashboard">
          Back to Certificates
        </Link>
      </PageHeading>
      {state.data ? (
        <CertificateRecord key={id} certificate={state.data} detailed />
      ) : (
        <LoadError state={state} />
      )}
    </>
  )
}

function PasswordChange({ onPasswordChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function update(event) {
    event.preventDefault()
    const fields = Object.fromEntries(new FormData(event.currentTarget))
    setError('')
    setBusy(true)
    try {
      if (fields.password !== fields.confirm_password) throw new Error('Passwords do not match.')
      await studentApi.changePassword(fields)
      onPasswordChanged()
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card section stack student-password-form" onSubmit={update}>
      <h2>Change Password</h2>
      <p>Use at least 12 characters. Changing your password signs you out on all devices.</p>
      <label>
        Current password
        <input
          name="current_password"
          type="password"
          autoComplete="current-password"
          maxLength={72}
          required
        />
      </label>
      <NewPasswordFields />
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary" disabled={busy}>
        {busy ? 'Updating…' : 'Update password'}
      </button>
    </form>
  )
}

function StudentProfile({ onPasswordChanged }) {
  const state = useReviewData(studentApi.profile, 'student-profile')
  return (
    <>
      <PageHeading title="My Profile" subtitle="Your registration details and account security." />
      <div className="stack">
        {state.data ? <ProfileCard profile={state.data} /> : <LoadError state={state} />}
        <PasswordChange onPasswordChanged={onPasswordChanged} />
      </div>
    </>
  )
}
