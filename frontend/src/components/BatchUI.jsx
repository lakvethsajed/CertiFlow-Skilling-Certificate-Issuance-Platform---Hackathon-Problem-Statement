import React from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, FileSearch, Pencil, RotateCcw } from 'lucide-react'

export function formatDate(value) {
  const date = value ? new Date(value) : null
  return date && !Number.isNaN(date.valueOf())
    ? new Intl.DateTimeFormat('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC'
      }).format(date)
    : '—'
}

export function StatusBadge({ status }) {
  return (
    <span className={'badge ' + status.toLowerCase().replaceAll(' ', '-')}>
      <i />
      {status}
    </span>
  )
}

export function PageHeading({ title, subtitle, children }) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>

      {children}
    </div>
  )
}

export function EmptyState({ title, children }) {
  return (
    <div className="empty">
      <FileSearch size={29} />
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  )
}

export function BatchTable({ batches, emptyTitle = 'No batches found', emptyDescription }) {
  if (!batches.length) {
    return <EmptyState title={emptyTitle}>{emptyDescription}</EmptyState>
  }

  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Batch records">
      <table>
        <thead>
          <tr>
            <th>Batch ID</th>
            <th>Batch Name</th>
            <th>Course</th>
            <th>Students</th>
            <th>Submission Date</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>

        <tbody>
          {batches.map((batch) => (
            <tr key={batch.id}>
              <td>
                <Link className="batch-id" to={'/batches/' + batch.id}>
                  {batch.id}
                </Link>
              </td>

              <td className="batch-name">{batch.name || 'Untitled batch'}</td>

              <td>{batch.course || '—'}</td>

              <td className="number-cell">{batch.count}</td>

              <td className="nowrap">{formatDate(batch.submittedAt)}</td>

              <td>
                <StatusBadge status={batch.status} />
              </td>

              <td>
                <div className="row-actions">
                  <Link
                    className="icon-button"
                    to={'/batches/' + batch.id}
                    aria-label={'View details for ' + batch.id}
                    title="View Details"
                  >
                    <ChevronRight size={19} />
                  </Link>

                  {['Draft', 'Returned'].includes(batch.status) && (
                    <Link
                      className="icon-button"
                      to={'/batches/' + batch.id + '/edit'}
                      aria-label={batch.status === 'Draft' ? 'Edit Draft' : 'Correct and Resubmit'}
                      title={batch.status === 'Draft' ? 'Edit Draft' : 'Correct and Resubmit'}
                    >
                      {batch.status === 'Draft' ? <Pencil size={16} /> : <RotateCcw size={16} />}
                    </Link>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
