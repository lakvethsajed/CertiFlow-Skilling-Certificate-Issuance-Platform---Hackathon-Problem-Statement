import React, { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Award, Clock3 } from 'lucide-react'

import { EmptyState, PageHeading, StatusBadge, formatDate } from '../components/BatchUI'
import { StudentPreview } from '../components/StudentPreview'
import { qualityApi } from '../services/api'
import { ApprovalHistory } from './Batches'
import {
  ApprovalProgress,
  DecisionDialog,
  DistrictValidation,
  LoadError,
  useReviewData
} from './District'

const views = {
  pending: 'Quality Review Queue',
  approved: 'Quality-approved Batches',
  history: 'Quality Review History'
}
const decisions = { APPROVE: 'Approved', RETURN: 'Returned', REJECT: 'Rejected' }
const labels = {
  PENDING_QUALITY_REVIEW: 'Pending Quality Review',
  PENDING_STATE_APPROVAL: 'Pending State Approval',
  RETURNED_FOR_CORRECTION: 'Returned',
  REJECTED: 'Rejected'
}
const detailsPath = (id, revision) => '/quality/batches/' + id + '?revision=' + revision

export function QualityDashboard() {
  const state = useReviewData(qualityApi.dashboard, 'quality-dashboard')
  const cards = [
    ['pending', 'pending', 'Awaiting Quality Review', Clock3, 'amber'],
    ['approved', 'approved', 'Quality-approved', Award, 'green']
  ]
  return (
    <>
      <PageHeading
        title="Quality Team Dashboard"
        subtitle="Review batches that require quality scrutiny."
      />
      <LoadError state={state} />
      {state.data && (
        <div className="stack">
          <div className="stats">
            {cards.map(([key, path, label, Icon, theme]) => (
              <Link key={key} to={'/quality/' + path} className="card stat">
                <span className={'stat-icon ' + theme}>
                  <Icon size={21} />
                </span>
                <div className="stat-label">{label}</div>
                <strong>{state.data[key]}</strong>
              </Link>
            ))}
          </div>
          <section className="card section">
            <h2>Recent review activity</h2>
            {state.data.activity.length ? (
              <ul className="history">
                {state.data.activity.map((item) => (
                  <li key={item.batch_id + ':' + item.revision}>
                    <div>
                      <Link to={detailsPath(item.batch_id, item.revision)}>{item.batch_name}</Link>
                      <time dateTime={item.created_at}>
                        {new Date(item.created_at).toLocaleString()}
                      </time>
                    </div>
                    <p>
                      {decisions[item.decision]} by {item.reviewer} · Revision {item.revision}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No quality decisions yet." />
            )}
          </section>
        </div>
      )}
    </>
  )
}

function waitingTime(timestamp) {
  if (!timestamp) return '—'
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(timestamp).getTime()) / 60000))
  if (minutes < 60) return minutes + ' min'
  if (minutes < 1440) return Math.floor(minutes / 60) + ' hr'
  return Math.floor(minutes / 1440) + ' days'
}

function QualityQueueTable({ records, pending }) {
  if (!records.length) return <EmptyState title="No batches match this view." />
  const headings = [
    'Batch ID',
    'Batch name',
    'Training Centre',
    'District',
    'Course',
    'Candidates',
    'District approvals',
    'Submitted',
    pending ? 'Waiting time' : 'Revision',
    'Status',
    'Action'
  ]
  return (
    <div className="table-scroll" role="region" aria-label="Quality review batches" tabIndex={0}>
      <table>
        <thead>
          <tr>
            {headings.map((heading) => (
              <th key={heading}>{heading}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map((batch) => (
            <tr key={batch.batch_id + ':' + batch.revision}>
              <td>
                <code>{batch.batch_id}</code>
              </td>
              <td>{batch.name}</td>
              <td>{batch.centre}</td>
              <td>{batch.district}</td>
              <td>{batch.course}</td>
              <td>{batch.candidate_count}</td>
              <td>{batch.district_approval_count} / 2</td>
              <td>{formatDate(batch.submitted_at)}</td>
              <td>{pending ? waitingTime(batch.quality_queued_at) : batch.revision}</td>
              <td>
                <StatusBadge status={labels[batch.status] ?? batch.status} />
              </td>
              <td>
                <Link to={detailsPath(batch.batch_id, batch.revision)}>View Details</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function QualityQueue() {
  const { view } = useParams()
  return Object.hasOwn(views, view) ? (
    <Queue key={view} view={view} />
  ) : (
    <EmptyState title="Page unavailable" />
  )
}

function Queue({ view }) {
  const [params, setParams] = useSearchParams()
  const query = new URLSearchParams({ view })
  for (const key of ['search', 'course', 'district', 'sort', 'page']) {
    if (params.get(key)) query.set(key, params.get(key))
  }
  const serialized = query.toString()
  const state = useReviewData((signal) => qualityApi.list(serialized, signal), serialized)
  const update = (key, value) => {
    const next = new URLSearchParams(params)
    if (key !== 'page') next.delete('page')
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const current = state.data?.page ?? 1
  const total = state.data?.total ?? 0
  const size = state.data?.page_size ?? 20
  return (
    <>
      <PageHeading
        title={views[view]}
        subtitle={
          view === 'pending'
            ? 'Batches awaiting a quality decision.'
            : 'Recorded Quality Team decisions.'
        }
      />
      <section className="card">
        <div className="filters">
          {[
            ['search', 'Search batches'],
            ['course', 'Course'],
            ['district', 'District']
          ].map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                maxLength={250}
                value={params.get(key) ?? ''}
                onChange={(event) => update(key, event.target.value)}
              />
            </label>
          ))}
          <label>
            Sort by
            <select
              value={params.get('sort') ?? 'oldest'}
              onChange={(event) => update('sort', event.target.value)}
            >
              <option value="oldest">Oldest first</option>
              <option value="newest">Newest first</option>
            </select>
          </label>
        </div>
        <LoadError state={state} />
        {state.data && (
          <>
            <QualityQueueTable records={state.data.records} pending={view === 'pending'} />
            <div className="table-footer pagination">
              <span>{total} records</span>
              <div className="inline">
                <button
                  className="button secondary"
                  disabled={current <= 1}
                  onClick={() => update('page', current - 1)}
                >
                  Previous
                </button>
                <span>
                  {current} / {Math.max(1, Math.ceil(total / size))}
                </span>
                <button
                  className="button secondary"
                  disabled={current * size >= total}
                  onClick={() => update('page', current + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  )
}

export function QualityDetails() {
  const { id } = useParams()
  const [params] = useSearchParams()
  return (
    <QualityRevision
      key={id + ':' + params.get('revision')}
      id={id}
      revision={params.get('revision')}
    />
  )
}

function QualityRevision({ id, revision }) {
  const state = useReviewData(
    (signal) => qualityApi.details(id, revision, signal),
    id + ':' + revision
  )
  const [action, setAction] = useState('')
  const [recorded, setRecorded] = useState(false)
  if (!state.data) return <LoadError state={state} />
  const batch = state.data
  const blocking = batch.validation.technical.length + batch.validation.batchFindings.length
  const fields = [
    ['Training Centre', batch.centre],
    ['District', batch.district],
    ['Course', batch.course],
    ['Trainer', batch.trainer],
    ['Training start', formatDate(batch.startDate)],
    ['Training end', formatDate(batch.endDate)],
    ['Assessment date', formatDate(batch.assessmentDate)],
    ['Submitted', formatDate(batch.submittedAt)],
    ['Candidates', batch.count]
  ]
  return (
    <>
      <PageHeading title={batch.name} subtitle={batch.id + ' · Revision ' + batch.revision}>
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
          <StudentPreview students={batch.students} review quality />
          <DistrictValidation validation={batch.validation} />
        </div>
        <div className="stack">
          <ApprovalProgress batch={batch} />
          {recorded && (
            <p className="notice success" role="status">
              Quality decision recorded.
            </p>
          )}
          {batch.canReview && (
            <section className="card section stack">
              <h2>Record a quality decision</h2>
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
          <ApprovalHistory history={batch.history} />
        </div>
      </div>
      {action && (
        <DecisionDialog
          batch={batch}
          action={action}
          decide={qualityApi.decide}
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
