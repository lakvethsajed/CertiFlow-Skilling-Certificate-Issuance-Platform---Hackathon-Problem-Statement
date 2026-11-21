import React, { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Award, ChevronRight, ClipboardCheck, Clock3 } from 'lucide-react'

import { EmptyState, PageHeading, StatusBadge, formatDate } from '../components/BatchUI'
import { StudentPreview } from '../components/StudentPreview'
import { districtApi } from '../services/api'

const views = {
  pending: 'Pending Reviews',
  approved: 'Approved Batches',
  history: 'Review History',
  notifications: 'Notifications'
}

export function useReviewData(load, key) {
  const [state, setState] = useState({ key, loading: true })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setState({ key, loading: true })
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ key, data })
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState({ key, error: error.message })
      })
    return () => controller.abort()
  }, [key, attempt])
  return {
    ...(state.key === key ? state : { loading: true }),
    retry: () => setAttempt((current) => current + 1),
    update: (data) => setState({ key, data })
  }
}

export function LoadError({ state }) {
  if (state.loading) return <p role="status">Loading review records…</p>
  if (state.error)
    return (
      <div className="notice error" role="alert">
        <p>{state.error}</p>
        <button className="button secondary" onClick={state.retry}>
          Retry
        </button>
      </div>
    )
  return null
}

export function DistrictDashboard() {
  const state = useReviewData(districtApi.dashboard, 'dashboard')
  const stats = [
    ['pending', 'Awaiting Review', Clock3, 'amber'],
    ['history', 'Reviewed', ClipboardCheck, 'blue', 'reviewed'],
    ['approved', 'Approved', Award, 'green']
  ]
  return (
    <div className="district-dashboard">
      <PageHeading
        title="District Officer Dashboard"
        subtitle="Track and review training batches in your district."
      />
      <LoadError state={state} />
      {state.data && (
        <div className="stats district-stats">
          {stats.map(([route, label, Icon, theme, key = route]) => (
            <Link to={'/district/' + route} className="card stat" key={route}>
              <div className="stat-top">
                <span className={'stat-icon ' + theme}>
                  <Icon size={21} />
                </span>
                <ChevronRight size={18} className="stat-chevron" />
              </div>
              <div className="stat-label">{label}</div>
              <strong>{state.data[key]}</strong>
            </Link>
          ))}
        </div>
      )}
      {state.data && !state.data.pending && !state.data.reviewed && (
        <div className="card">
          <EmptyState title="No batches available for review." />
        </div>
      )}
    </div>
  )
}

const pageSize = 10

export function DistrictList() {
  const { view } = useParams()
  return views[view] && Object.hasOwn(views, view) ? (
    <ReviewTable key={view} view={view} />
  ) : (
    <EmptyState title="Page unavailable" />
  )
}

function ReviewTable({ view }) {
  const state = useReviewData(
    (signal) => districtApi.list(view === 'notifications' ? 'pending' : view, signal),
    view
  )
  const [params, setParams] = useSearchParams()
  const [course, setCourse] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('new')
  const [page, setPage] = useState(1)
  const batches = state.data ?? []
  const query = params.get('q') ?? ''
  const matching = batches
    .filter(
      (batch) =>
        (!course || course === batch.course) &&
        (!status || status === batch.status) &&
        [batch.name, batch.id, batch.centre].some((value) =>
          value.toLowerCase().includes(query.trim().toLowerCase())
        )
    )
    .sort(
      (a, b) => (sort === 'new' ? -1 : 1) * (a.submittedAt ?? '').localeCompare(b.submittedAt ?? '')
    )
  const current = Math.min(page, Math.max(1, Math.ceil(matching.length / pageSize)))

  return (
    <>
      <PageHeading
        title={views[view]}
        subtitle={
          view === 'notifications'
            ? 'Batches in your district awaiting review.'
            : 'Training centre submissions in your district.'
        }
      />
      <LoadError state={state} />
      {state.data && (
        <section className="card">
          <div className="filters">
            <label>
              Search batches
              <input
                value={query}
                onChange={(event) => {
                  setParams({ q: event.target.value }, { replace: true })
                  setPage(1)
                }}
              />
            </label>
            <label>
              Course
              <select
                value={course}
                onChange={(event) => {
                  setCourse(event.target.value)
                  setPage(1)
                }}
              >
                <option value="">All courses</option>
                {[...new Set(batches.map((batch) => batch.course))].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              Status
              <select
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value)
                  setPage(1)
                }}
              >
                <option value="">All statuses</option>
                {[...new Set(batches.map((batch) => batch.status))].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              Sort by
              <select
                value={sort}
                onChange={(event) => {
                  setSort(event.target.value)
                  setPage(1)
                }}
              >
                <option value="new">Newest first</option>
                <option value="old">Oldest first</option>
              </select>
            </label>
          </div>
          {matching.length ? (
            <>
              <div
                className="table-scroll"
                tabIndex={0}
                role="region"
                aria-label="District batches"
              >
                <table>
                  <thead>
                    <tr>
                      {[
                        'Batch ID',
                        'Batch Name',
                        'Training Centre',
                        'District',
                        'Course',
                        'Candidates',
                        'Submitted',
                        'Approvals',
                        'Status',
                        'Action'
                      ].map((label) => (
                        <th key={label}>{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {matching.slice((current - 1) * pageSize, current * pageSize).map((batch) => (
                      <tr key={batch.id}>
                        <td>
                          <code>{batch.id}</code>
                        </td>
                        <td>{batch.name}</td>
                        <td>{batch.centre}</td>
                        <td>{batch.district}</td>
                        <td>{batch.course}</td>
                        <td>{batch.count}</td>
                        <td>{formatDate(batch.submittedAt)}</td>
                        <td>
                          {batch.approvalsReceived} / {batch.approvalsRequired}
                        </td>
                        <td>
                          <StatusBadge status={batch.status} />
                        </td>
                        <td>
                          <Link to={'/district/batches/' + batch.id}>View Details</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="table-footer pagination">
                <span>{matching.length} batches</span>
                <div className="inline">
                  <button
                    className="button secondary"
                    disabled={current === 1}
                    onClick={() => setPage(current - 1)}
                  >
                    Previous
                  </button>
                  <span>
                    {current} / {Math.ceil(matching.length / pageSize)}
                  </span>
                  <button
                    className="button secondary"
                    disabled={current * pageSize >= matching.length}
                    onClick={() => setPage(current + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              title={
                view === 'notifications' && !batches.length
                  ? 'No notifications available.'
                  : 'No matching batches.'
              }
            />
          )}
        </section>
      )}
    </>
  )
}

export function DecisionDialog({
  batch,
  action,
  onClose,
  onRecorded,
  decide = districtApi.decide,
  approveLabel = 'Approve batch'
}) {
  const dialog = useRef(null)
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const labels = {
    approve: approveLabel,
    return: 'Return for corrections',
    reject: 'Reject batch'
  }
  useEffect(() => {
    dialog.current.showModal()
  }, [])
  async function record(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      onRecorded(await decide(batch.id, action, { revision: batch.revision, comment }))
    } catch (failure) {
      setError(failure.message)
      setSaving(false)
    }
  }
  return (
    <dialog
      className="modal card"
      ref={dialog}
      aria-labelledby="decision-title"
      onCancel={(event) => {
        event.preventDefault()
        if (!saving) onClose()
      }}
    >
      <form onSubmit={record} className="stack">
        <h2 id="decision-title">{labels[action]}</h2>
        <p>
          {batch.name} · Revision {batch.revision}
        </p>
        <label>
          {action === 'approve' ? 'Comment (optional)' : 'Reason'}
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            required={action !== 'approve'}
            maxLength={2000}
          />
        </label>
        {error && (
          <p role="alert" className="notice error">
            {error}
          </p>
        )}
        <div className="inline">
          <button className="button secondary" type="button" disabled={saving} onClick={onClose}>
            Cancel
          </button>
          <button
            className="button primary"
            disabled={saving || (action !== 'approve' && !comment.trim())}
          >
            {saving ? 'Saving…' : 'Confirm decision'}
          </button>
        </div>
      </form>
    </dialog>
  )
}

export function DistrictValidation({ validation }) {
  return (
    <section className="card section">
      <h2>Validation Summary</h2>
      <h3>Technical CSV validation</h3>
      {validation.technical.length ? (
        <ul>
          {validation.technical.map((item) => (
            <li key={item.rowNumber}>
              Row {item.rowNumber}: {item.errors.join(' ')}
            </li>
          ))}
        </ul>
      ) : (
        <p>No technical CSV errors.</p>
      )}
      <h3>District-level findings</h3>
      {validation.batchFindings.length + validation.districtFindings.length ? (
        <ul>
          {validation.batchFindings.map((message) => (
            <li key={message}>{message}</li>
          ))}
          {validation.districtFindings.map((item) => (
            <li key={item.rowNumber}>
              Row {item.rowNumber}: {item.message}
            </li>
          ))}
        </ul>
      ) : (
        <p>No district-level findings.</p>
      )}
    </section>
  )
}

export function ApprovalProgress({ batch }) {
  return (
    <section className="card section">
      <h2>Approval Progress</h2>
      <p>
        Revision {batch.revision} · {batch.approvalsReceived} of {batch.approvalsRequired} approvals
        received · {Math.max(0, batch.approvalsRequired - batch.approvalsReceived)} still required
      </p>
      {batch.decisions.length ? (
        <ol className="history">
          {batch.decisions.map((item) => (
            <li key={item.id}>
              <div>
                <strong>
                  {item.officer} · {item.role}
                </strong>
                <time dateTime={item.date}>{new Date(item.date).toLocaleString()}</time>
              </div>
              <p>
                Revision {item.revision} ·{' '}
                {{ APPROVE: 'Approved', RETURN: 'Returned', REJECT: 'Rejected' }[item.decision]}
              </p>
              {item.comment && <p>{item.comment}</p>}
            </li>
          ))}
        </ol>
      ) : (
        <p>No decisions have been recorded.</p>
      )}
    </section>
  )
}

export function DistrictReview() {
  const { id } = useParams()
  const state = useReviewData((signal) => districtApi.details(id, signal), id)
  const [action, setAction] = useState('')
  const [recorded, setRecorded] = useState(false)
  if (!state.data) return <LoadError state={state} />
  const batch = state.data
  const blocking = batch.validation.technical.length || batch.validation.batchFindings.length
  const fields = [
    ['Training Centre', batch.centre],
    ['District', batch.district],
    ['Course', batch.course],
    ['Trainer', batch.trainer],
    ['Training Start', formatDate(batch.startDate)],
    ['Training End', formatDate(batch.endDate)],
    ['Assessment Date', formatDate(batch.assessmentDate)],
    ['Submitted', formatDate(batch.submittedAt)],
    ['Candidates', batch.count]
  ]
  return (
    <>
      <PageHeading title={batch.name} subtitle={batch.id}>
        <StatusBadge status={batch.status} />
      </PageHeading>
      <div className="details-layout">
        <div className="stack">
          <section className="card section">
            <h2>Batch Information</h2>
            <dl className="details-grid">
              {fields.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            {batch.description && <p>{batch.description}</p>}
          </section>
          <StudentPreview students={batch.students} review />
          <DistrictValidation validation={batch.validation} />
        </div>
        <div className="stack">
          <ApprovalProgress batch={batch} />
          {recorded && (
            <p className="notice success" role="status">
              Decision recorded.
            </p>
          )}
          {batch.canReview && (
            <section className="card section stack">
              <h2>Record a decision</h2>
              <button
                className="button primary"
                disabled={Boolean(blocking)}
                onClick={() => setAction('approve')}
              >
                Approve
              </button>
              <button className="button secondary" onClick={() => setAction('return')}>
                Return for Corrections
              </button>
              <button className="button secondary" onClick={() => setAction('reject')}>
                Reject
              </button>
            </section>
          )}
        </div>
      </div>
      {action && (
        <DecisionDialog
          batch={batch}
          action={action}
          onClose={() => setAction('')}
          onRecorded={(updated) => {
            state.update(updated)
            setAction('')
            setRecorded(true)
          }}
        />
      )}
    </>
  )
}
