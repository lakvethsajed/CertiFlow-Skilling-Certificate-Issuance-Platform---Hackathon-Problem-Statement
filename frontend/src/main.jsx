import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate
} from 'react-router-dom'

import { EmptyState } from './components/BatchUI'
import { Layout } from './components/Layout'
import { Batches, BatchDetails, Profile, ReturnedBatches } from './pages/Batches'
import { Dashboard } from './pages/Dashboard'
import { DistrictDashboard, DistrictList, DistrictReview } from './pages/District'
import { Login, VerifyCertificate } from './pages/Login'
import { QualityDashboard, QualityDetails, QualityQueue } from './pages/Quality'
import { StateBatchDetails } from './pages/StateBatchDetails'
import { StateDashboard, StateQueue } from './pages/StateOffice'
import { StudentActivation } from './pages/StudentActivation'
import { StudentWorkspace } from './pages/StudentPortal'
import { UploadBatch } from './pages/UploadBatch'
import { authApi, centreApi, studentApi } from './services/api'
import './styles/global.css'

function Workspace({ user, onLogout }) {
  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(user.role === 'TRAINING_CENTRE')
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const officer = user.role === 'DISTRICT_OFFICER'
  const quality = user.role === 'QUALITY_TEAM'
  const stateOffice = user.role === 'STATE_OFFICE'
  const centre = user.role === 'TRAINING_CENTRE'
  const { pathname } = useLocation()

  useEffect(() => {
    if (!centre) return
    const controller = new AbortController()
    centreApi
      .list(controller.signal)
      .then((records) => {
        if (!controller.signal.aborted) setBatches(records)
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => {
      controller.abort()
    }
  }, [centre, attempt, pathname])

  if (loading || error)
    return (
      <main className="signed-out">
        <div className="card">
          <p role={error ? 'alert' : 'status'}>{error || 'Loading batches…'}</p>
          {error && (
            <button
              className="button secondary"
              onClick={() => {
                setError('')
                setLoading(true)
                setAttempt(attempt + 1)
              }}
            >
              Retry
            </button>
          )}
          <button
            className="button secondary"
            onClick={() => {
              void onLogout().catch((failure) => setError(failure.message))
            }}
          >
            Log out
          </button>
        </div>
      </main>
    )

  return (
    <Routes>
      <Route
        element={
          <Layout
            user={user}
            onLogout={onLogout}
            returnedCount={batches.filter((batch) => batch.status === 'Returned').length}
          />
        }
      >
        {centre && (
          <>
            <Route index element={<Dashboard batches={batches} />} />
            <Route
              path="upload"
              element={
                <UploadBatch batches={batches} setBatches={setBatches} organisation={user.centre} />
              }
            />
            <Route path="batches" element={<Batches key="all" batches={batches} />} />
            <Route path="batches/:id" element={<BatchDetails batches={batches} />} />
            <Route
              path="batches/:id/edit"
              element={
                <UploadBatch batches={batches} setBatches={setBatches} organisation={user.centre} />
              }
            />
            <Route
              path="pending"
              element={<Batches key="pending" mode="pending" batches={batches} />}
            />
            <Route path="returned" element={<ReturnedBatches batches={batches} />} />
            <Route
              path="certificates"
              element={<Batches key="certificates" mode="certificates" batches={batches} />}
            />
          </>
        )}
        {officer && (
          <>
            <Route index element={<DistrictDashboard />} />
            <Route path="district/batches/:id" element={<DistrictReview />} />
            <Route path="district/:view" element={<DistrictList />} />
            <Route path="district" element={<Navigate to="/district/pending" replace />} />
          </>
        )}
        {quality && (
          <>
            <Route index element={<QualityDashboard />} />
            <Route path="quality/batches/:id" element={<QualityDetails />} />
            <Route path="quality/:view" element={<QualityQueue />} />
            <Route path="quality" element={<Navigate to="/quality/pending" replace />} />
          </>
        )}
        {stateOffice && (
          <>
            <Route index element={<StateDashboard />} />
            <Route path="state/batches/:id" element={<StateBatchDetails />} />
            <Route path="state/:view" element={<StateQueue />} />
            <Route path="state" element={<Navigate to="/state/pending" replace />} />
          </>
        )}
        {!centre && !officer && !quality && !stateOffice && (
          <Route
            index
            element={
              <div className="card">
                <EmptyState title="Workspace unavailable for this role">
                  <Link to="/verify">Verify a certificate</Link>
                </EmptyState>
              </div>
            }
          />
        )}
        <Route path="profile" element={<Profile user={user} />} />
        <Route
          path="*"
          element={
            <div className="card">
              <EmptyState title="Page unavailable">
                <Link to="/">Back to Dashboard</Link>
              </EmptyState>
            </div>
          }
        />
      </Route>
    </Routes>
  )
}

function App() {
  const [user, setUser] = useState(undefined)
  const [error, setError] = useState('')
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const studentPath = pathname === '/student' || pathname.startsWith('/student/')
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  async function restore() {
    setError('')
    try {
      setUser(await authApi.session())
    } catch (failure) {
      setError(failure.message)
    }
  }
  useEffect(() => {
    function expireSession() {
      setUser(null)
    }
    window.addEventListener('certiflow-session-expired', expireSession)
    void restore()
    return () => window.removeEventListener('certiflow-session-expired', expireSession)
  }, [])

  async function logout() {
    try {
      await (user?.role === 'CANDIDATE' ? studentApi : authApi).logout()
      setUser(null)
      if (studentPath || user?.role === 'CANDIDATE') navigate('/student/login', { replace: true })
    } catch (failure) {
      if (failure.status === 401) setUser(null)
      else throw failure
    }
  }

  if (pathname === '/verify') return <VerifyCertificate />
  if (error)
    return (
      <main className="signed-out">
        <div className="card">
          <p role="alert">{error}</p>
          <button className="button secondary" onClick={restore}>
            Retry
          </button>
          <Link to="/verify">Verify a certificate</Link>
        </div>
      </main>
    )
  if (user === undefined)
    return (
      <main className="signed-out">
        <p role="status">Checking your session…</p>
      </main>
    )
  if (user?.role === 'CANDIDATE')
    return (
      <StudentWorkspace
        key={user.id}
        onLogout={logout}
        onPasswordChanged={() => {
          setUser(null)
          navigate('/student/login?notice=password', { replace: true })
        }}
      />
    )
  if (studentPath) {
    if (user)
      return (
        <main className="signed-out">
          <div className="card auth-card">
            <h1>Student Portal</h1>
            <p>Sign out of your staff workspace to switch to a student account.</p>
            <button
              className="button primary"
              onClick={() => {
                void logout().catch((failure) => setError(failure.message))
              }}
            >
              Sign out
            </button>
            <Link to="/">Back to staff dashboard</Link>
          </div>
        </main>
      )
    if (pathname === '/student/activate') return <StudentActivation />
    if (pathname !== '/student/login') return <Navigate to="/student/login" replace />
    return <Login student onLogin={setUser} />
  }
  return user ? (
    <Workspace key={user.id} user={user} onLogout={logout} />
  ) : (
    <Login onLogin={setUser} />
  )
}

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)
