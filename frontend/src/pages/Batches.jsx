import { ActivationCodeExport } from '../components/ActivationCodeExport'
import React, { useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Check, Circle, Clock3, RotateCcw, Search, Upload, UserRound } from 'lucide-react'
import { BatchTable, EmptyState, PageHeading, StatusBadge, formatDate } from '../components/BatchUI'
import { courses, stages, statuses } from '../data/batchOptions'
import { SuccessModal } from '../components/SuccessModal'
import { StudentPreview } from '../components/StudentPreview'

export function Batches({ batches, mode = 'all' }) {
  const [params, setParams] = useSearchParams()
  const [course, setCourse] = useState('')
  const [date, setDate] = useState('')
  const [status, setStatus] = useState('')
  const [order, setOrder] = useState('newest')
  const query = params.get('q') ?? ''
  const scope =
    mode === 'pending'
      ? ['Submitted', 'Under Review', 'Pending Quality Review', 'Pending State Approval']
      : mode === 'certificates'
        ? ['Certificates Generated']
        : statuses
  const titles = {
    all: ['My Batches', 'Search, filter and manage your training centre’s batches.'],
    pending: ['Pending Approvals', 'Track batches awaiting officer review.'],
    certificates: ['Certificates', 'View batches with generated certificates.']
  }
  const visible = batches
    .filter(
      (batch) =>
        scope.includes(batch.status) &&
        (!status || status === batch.status) &&
        (!course || course === batch.course) &&
        (!date || date === batch.submittedAt) &&
        (batch.id + ' ' + batch.name).toLowerCase().includes(query.trim().toLowerCase())
    )
    .sort(
      (a, b) =>
        (order === 'newest' ? -1 : 1) *
        (a.submittedAt || a.createdAt).localeCompare(b.submittedAt || b.createdAt)
    )
  const hasFilters = Boolean(query.trim() || course || date || status)
  const emptyTitle =
    mode === 'pending'
      ? 'No pending approvals'
      : mode === 'certificates'
        ? 'No certificates available'
        : 'No batches found.'
  const emptyDescription = hasFilters
    ? 'Try adjusting your filters.'
    : mode === 'all'
      ? 'Upload your first batch to get started.'
      : undefined
  return (
    <>
      <PageHeading title={titles[mode][0]} subtitle={titles[mode][1]}>
        <Link className="button primary" to="/upload">
          <Upload size={17} /> Upload New Batch
        </Link>
      </PageHeading>
      <section className="card">
        <div className="filters">
          <label>
            Search batches
            <div className="search-input">
              <Search size={17} />
              <input
                value={query}
                placeholder="Batch ID or name"
                onChange={(event) =>
                  setParams(event.target.value ? { q: event.target.value } : {}, { replace: true })
                }
              />
            </div>
          </label>
          <label>
            Course
            <select value={course} onChange={(event) => setCourse(event.target.value)}>
              <option value="">All courses</option>
              {courses.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Submission date
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
          {scope.length > 1 && (
            <label>
              Status
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">All statuses</option>
                {scope.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            Sort by
            <select value={order} onChange={(event) => setOrder(event.target.value)}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </label>
        </div>
        <BatchTable
          batches={visible}
          emptyTitle={hasFilters ? 'No matching batches' : emptyTitle}
          emptyDescription={emptyDescription}
        />
        <div className="table-footer">
          {visible.length} {visible.length === 1 ? 'batch' : 'batches'} found
        </div>
      </section>
    </>
  )
}

export function ReturnedBatches({ batches }) {
  const returned = batches.filter((batch) => batch.status === 'Returned')
  return (
    <>
      <PageHeading
        title="Returned for Corrections"
        subtitle="Review officer feedback and resubmit corrected batches."
      />
      <div className="stack">
        {returned.map((batch) => (
          <article className="card section returned-card" key={batch.id}>
            <div className="section-header">
              <div>
                <Link className="batch-id" to={'/batches/' + batch.id}>
                  {batch.id}
                </Link>
                <h2>{batch.name}</h2>
              </div>
              <StatusBadge status={batch.status} />
            </div>
            <dl className="details-grid">
              <div>
                <dt>Return date</dt>
                <dd>{formatDate(batch.returnedAt)}</dd>
              </div>
              <div>
                <dt>Reason for return</dt>
                <dd>{batch.reason}</dd>
              </div>
            </dl>
            <div className="notice warning">
              <strong>Officer comments</strong>
              <p>{batch.comment}</p>
            </div>
            <Link className="button primary" to={'/batches/' + batch.id + '/edit'}>
              <RotateCcw size={16} /> Correct and Resubmit
            </Link>
          </article>
        ))}
      </div>
      {!returned.length && (
        <div className="card">
          <EmptyState title="No returned batches">
            Batches that require corrections will appear here.
          </EmptyState>
        </div>
      )}
    </>
  )
}

export function ApprovalHistory({ history = [] }) {
  return (
    <section className="card section">
      <h2>Approval history</h2>
      {history.length ? (
        <ul className="history">
          {history.map((event, index) => (
            <li key={index}>
              <div>
                <strong>{event.label}</strong>
                <span>{formatDate(event.date)}</span>
              </div>
              {event.note && <p>{event.note}</p>}
              {event.previousSubmission && (
                <details>
                  <summary>Previous submission</summary>
                  <p>
                    {event.previousSubmission.name} · {event.previousSubmission.course} ·{' '}
                    {event.previousSubmission.count} students
                  </p>
                  <p>
                    Submitted {formatDate(event.previousSubmission.submittedAt)} · Assessment{' '}
                    {formatDate(event.previousSubmission.assessmentDate)}
                  </p>
                </details>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="section-note">No approval history available.</p>
      )}
    </section>
  )
}

export function BatchDetails({ batches }) {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const batch = batches.find((item) => item.id === id)
  if (!batch)
    return (
      <div className="card">
        <EmptyState title="Batch not found">
          <Link to="/batches">Back to My Batches</Link>
        </EmptyState>
      </div>
    )
  const fields = [
    ['Course', batch.course],
    ['Training centre', batch.centre],
    ['District', batch.district],
    ['Trainer', batch.trainer],
    ['Training start', formatDate(batch.startDate)],
    ['Training end', formatDate(batch.endDate)],
    ['Assessment date', formatDate(batch.assessmentDate)],
    ['Submission date', formatDate(batch.submittedAt)],
    ['Students', batch.count],
    [
      'Certificates',
      batch.status === 'Certificates Generated' ? 'Generated' : 'Awaiting generation'
    ]
  ]
  return (
    <>
      <PageHeading title={batch.name || 'Untitled batch'} subtitle={batch.id}>
        <StatusBadge status={batch.status} />
        {['Draft', 'Returned'].includes(batch.status) && (
          <Link className="button primary" to={'/batches/' + id + '/edit'}>
            {batch.status === 'Draft' ? 'Edit Draft' : 'Correct and Resubmit'}
          </Link>
        )}
      </PageHeading>
      {location.state?.draftSaved && (
        <p className="notice success draft-notice" role="status">
          Draft saved.
        </p>
      )}
      {location.state?.submitted && (
        <SuccessModal
          batch={batch}
          onClose={() => navigate(location.pathname, { replace: true, state: null })}
        />
      )}
      <div className="details-layout">
        <div className="stack">
          <section className="card section">
            <h2>Batch information</h2>
            <dl className="details-grid">
              {fields.map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{(value ?? '') === '' ? '—' : value}</dd>
                </div>
              ))}
            </dl>
            {batch.description && <p>{batch.description}</p>}
            {['Rejected', 'Returned'].includes(batch.status) && (
              <div className="notice warning">
                <strong>{batch.reason}</strong>
                <p>{batch.comment}</p>
              </div>
            )}
          </section>
          {batch.submittedAt && !['Returned', 'Rejected'].includes(batch.status) && (
            <ActivationCodeExport key={batch.id + ':' + batch.revision} batchId={batch.id} />
          )}
          <StudentPreview students={batch.students ?? []} />
        </div>
        <div className="stack">
          <section className="card section">
            <h2>Approval timeline</h2>
            <ol className="timeline">
              {stages.map((stage, index) => {
                const skipped =
                  index === 4 &&
                  batch.qualityRequired === false &&
                  ['PENDING_STATE_APPROVAL', 'FINAL_APPROVED', 'CERTIFICATES_GENERATED'].includes(
                    batch.workflowStatus
                  )
                const awaitingQuality =
                  index === 4 && batch.workflowStatus === 'PENDING_QUALITY_REVIEW'
                const state = skipped
                  ? 'Not required'
                  : awaitingQuality
                    ? 'Awaiting quality review'
                    : index === batch.stage &&
                        ['Returned', 'Rejected', 'Under Review'].includes(batch.status)
                      ? batch.status
                      : index <= batch.stage
                        ? 'Complete'
                        : 'Pending'
                const Icon =
                  state === 'Complete' ? Check : state === 'Under Review' ? Clock3 : Circle
                return (
                  <li key={stage}>
                    <span className={'timeline-icon ' + (state === 'Complete' ? 'complete' : '')}>
                      <Icon size={15} />
                    </span>
                    <div>
                      <strong>{stage}</strong>
                      <small>{state}</small>
                    </div>
                  </li>
                )
              })}
            </ol>
          </section>
          <ApprovalHistory history={batch.history} />
        </div>
      </div>
    </>
  )
}

export function Profile({ user }) {
  return (
    <>
      <PageHeading
        title="Profile & Settings"
        subtitle="View your training centre account and organisation details."
      />
      <section className="card section">
        <div className="inline">
          <span className="avatar large">
            <UserRound size={22} aria-hidden="true" />
          </span>
          <div>
            <h2>{user.name}</h2>
            <p>{user.email}</p>
          </div>
        </div>
        <dl className="details-grid">
          <div>
            <dt>Organisation</dt>
            <dd>{user.centre?.name || '—'}</dd>
          </div>
          <div>
            <dt>District</dt>
            <dd>{user.centre?.district?.name || user.district?.name || '—'}</dd>
          </div>
          <div>
            <dt>Workspace</dt>
            <dd>{user.role.replaceAll('_', ' ')}</dd>
          </div>
        </dl>
      </section>
    </>
  )
}
