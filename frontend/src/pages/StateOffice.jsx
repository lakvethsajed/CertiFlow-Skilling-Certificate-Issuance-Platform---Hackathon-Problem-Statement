import React from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Award, CheckCircle, Clock3, FileClock } from 'lucide-react'

import { EmptyState, PageHeading, StatusBadge, formatDate } from '../components/BatchUI'
import { stateApi } from '../services/api'
import { LoadError, useReviewData } from './District'

const views = {
  pending: 'Final Approval Queue',
  approved: 'Final-approved Batches',
  history: 'State Office Review History'
}
const decisions = { APPROVE: 'Approved', RETURN: 'Returned', REJECT: 'Rejected' }
const labels = {
  PENDING_STATE_APPROVAL: 'Pending State Approval',
  FINAL_APPROVED: 'Final Approved',
  RETURNED_FOR_CORRECTION: 'Returned',
  REJECTED: 'Rejected',
  CERTIFICATES_GENERATED: 'Certificates Generated'
}
const metrics = [
  ['pending', 'Awaiting Final Approval', Clock3, 'amber', 'pending'],
  ['approved', 'Final Approvals', CheckCircle, 'green', 'approved'],
  ['certificates_generated', 'Certificates Generated', Award, 'green'],
  ['certificates_pending', 'Certificates Pending', FileClock, 'blue']
]

function StateMetric({ Icon, label, value, theme, view }) {
  const content = (
    <>
      <span className={'stat-icon ' + theme}>
        <Icon size={21} />
      </span>
      <span className="stat-label">{label}</span>
      <strong>{value.toLocaleString()}</strong>
    </>
  )
  return view ? (
    <Link className="card stat" to={'/state/' + view}>
      {content}
    </Link>
  ) : (
    <article className="card stat">{content}</article>
  )
}

function RecentStateActivity({ activity }) {
  return (
    <section className="card section">
      <h2>Recent State Office activity</h2>
      {activity.length ? (
        <ul className="history">
          {activity.map((item) => (
            <li key={item.batch_id + ':' + item.revision}>
              <div>
                <Link to={'/state/history?search=' + encodeURIComponent(item.batch_id)}>
                  {item.batch_name}
                </Link>
                <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
              </div>
              <p>
                {decisions[item.decision]} by {item.reviewer} · Revision {item.revision}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="No State Office decisions yet." />
      )}
    </section>
  )
}

export function StateDashboard() {
  const state = useReviewData(stateApi.dashboard, 'state-dashboard')
  return (
    <>
      <PageHeading
        title="State Office Dashboard"
        subtitle="Track final reviews and certificate issuance across training centres."
      />
      {state.data ? (
        <div className="stack">
          <div className="stats district-stats">
            {metrics.map(([key, label, Icon, theme, view]) => (
              <StateMetric
                key={key}
                Icon={Icon}
                value={state.data[key]}
                label={label}
                theme={theme}
                view={view}
              />
            ))}
          </div>
          <RecentStateActivity activity={state.data.activity} />
        </div>
      ) : (
        <LoadError state={state} />
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

function StateQueueTable({ records }) {
  if (!records.length) return <EmptyState title="No batches match this view." />
  const headings = [
    'Batch ID',
    'Batch Name',
    'Training Centre',
    'District',
    'Course',
    'Candidates',
    'District Approval',
    'Quality Review',
    'Sent to State Office',
    'Waiting',
    'Status',
    'Action'
  ]
  return (
    <div className="table-scroll" role="region" aria-label="State Office batches" tabIndex={0}>
      <table>
        <thead>
          <tr>
            {headings.map((label) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map((row) => (
            <tr key={row.batch_id + ':' + row.revision}>
              <td>
                <code>{row.batch_id}</code>
              </td>
              <td>{row.name}</td>
              <td>{row.centre}</td>
              <td>{row.district}</td>
              <td>{row.course}</td>
              <td>{row.candidate_count}</td>
              <td>{row.district_approval_count} / 2 approved</td>
              <td>{row.quality_status === 'APPROVED' ? 'Approved' : 'Not required'}</td>
              <td>{formatDate(row.state_queued_at)}</td>
              <td>
                {row.status === 'PENDING_STATE_APPROVAL' ? waitingTime(row.state_queued_at) : '—'}
              </td>
              <td>
                <StatusBadge status={labels[row.status] ?? row.status} />
              </td>
              <td>
                <Link
                  className="button secondary"
                  to={'/state/batches/' + row.batch_id + '?revision=' + row.revision}
                >
                  View Details
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function StateQueue() {
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
  const state = useReviewData((signal) => stateApi.list(serialized, signal), serialized)

  function update(key, value) {
    const next = new URLSearchParams(params)
    if (key !== 'page') next.delete('page')
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const page = state.data?.page ?? 1
  const pages = Math.max(1, Math.ceil((state.data?.total ?? 0) / (state.data?.page_size ?? 20)))
  return (
    <>
      <PageHeading
        title={views[view]}
        subtitle={
          view === 'pending' ? 'Open an eligible batch to make a final decision.' : undefined
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
        {state.data ? (
          <>
            <StateQueueTable records={state.data.records} />
            <div className="table-footer pagination">
              <span>{state.data.total} records</span>
              <div className="inline">
                <button
                  className="button secondary"
                  disabled={page <= 1}
                  onClick={() => update('page', page - 1)}
                >
                  Previous
                </button>
                <span>
                  {page} / {pages}
                </span>
                <button
                  className="button secondary"
                  disabled={page >= pages}
                  onClick={() => update('page', page + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        ) : (
          <LoadError state={state} />
        )}
      </section>
    </>
  )
}
