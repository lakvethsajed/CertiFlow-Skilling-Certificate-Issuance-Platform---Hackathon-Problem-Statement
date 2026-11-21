import React, { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { PageHeading, StatusBadge, formatDate } from '../components/BatchUI'
import { StudentPreview } from '../components/StudentPreview'
import { stateApi } from '../services/api'
import { ApprovalHistory } from './Batches'
import {
  ApprovalProgress,
  DecisionDialog,
  DistrictValidation,
  LoadError,
  useReviewData
} from './District'

export function StateBatchDetails() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const revision = params.get('revision')
  return <StateRevision key={id + ':' + revision} id={id} revision={revision} />
}

function RecordSection({ title, fields }) {
  return (
    <section className="card section">
      <h2>{title}</h2>
      <dl className="details-grid">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value ?? '—'}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function StateRevision({ id, revision }) {
  const state = useReviewData(
    (signal) => stateApi.details(id, revision, signal),
    id + ':' + revision
  )
  const [action, setAction] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const batch = state.data
  if (!batch)
    return (
      <>
        <PageHeading title="Final Review" />
        {confirmation && (
          <p className="notice success" role="status">
            {confirmation}
          </p>
        )}
        <LoadError state={state} />
        <Link to="/state/pending">Back to Final Approval Queue</Link>
      </>
    )

  const blocking = batch.validation.technical.length + batch.validation.batchFindings.length > 0
  const readiness = batch.certificateReadiness
  const quality = batch.decisions.find(
    (item) => item.role === 'Quality Team' && item.revision === batch.revision
  )
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
  const qualityFields = [
    ['Required', batch.qualityRequired ? 'Yes' : 'No'],
    ['Candidates counted', batch.count],
    ...(quality
      ? [
          [
            'Decision',
            { APPROVE: 'Approved', RETURN: 'Returned', REJECT: 'Rejected' }[quality.decision]
          ],
          ['Reviewer', quality.officer],
          ['Reviewed at', new Date(quality.date).toLocaleString()],
          ['Comment', quality.comment || '—']
        ]
      : [])
  ]

  function onRecorded(result) {
    setAction('')
    const messages = {
      FINAL_APPROVED: 'Final approval recorded. Certificate issuance has been requested.',
      RETURNED_FOR_CORRECTION:
        'Batch returned to the Training Centre. After resubmission, district review starts again.',
      REJECTED: 'Final rejection recorded.'
    }
    setConfirmation(messages[result.status])
    state.retry()
  }

  return (
    <>
      <Link to="/state/pending">Back to Final Approval Queue</Link>
      <PageHeading title={batch.name} subtitle={batch.id + ' · Revision ' + batch.revision}>
        <StatusBadge status={batch.status} />
      </PageHeading>
      {confirmation && (
        <p className="notice success" role="status">
          {confirmation}
        </p>
      )}
      <div className="details-layout">
        <div className="stack">
          <RecordSection title="Batch Information" fields={fields} />
          <StudentPreview students={batch.students} review quality />
          <DistrictValidation validation={batch.validation} />
        </div>
        <div className="stack">
          {batch.canReview && (
            <section className="card section stack">
              <h2>Final Decision</h2>
              {blocking && <p>Resolve blocking validation errors before approving.</p>}
              <button
                className="button primary"
                disabled={blocking}
                onClick={() => setAction('approve')}
              >
                Final Approve
              </button>
              <button className="button secondary" onClick={() => setAction('return')}>
                Return for Corrections
              </button>
              <button className="button secondary" onClick={() => setAction('reject')}>
                Reject
              </button>
            </section>
          )}
          <ApprovalProgress batch={batch} />
          <RecordSection title="Quality Review" fields={qualityFields} />
          <RecordSection
            title="Certificate Readiness"
            fields={[
              ['Final Approval', readiness.final_approved ? 'Granted' : 'Not granted'],
              ['Expected', readiness.expected],
              ['Generated', readiness.generated],
              ['Pending', readiness.pending],
              ['Failed', readiness.failed]
            ]}
          />
          <ApprovalHistory history={batch.history} />
        </div>
      </div>
      {action && (
        <DecisionDialog
          batch={batch}
          action={action}
          approveLabel="Final Approve"
          decide={stateApi.decide}
          onClose={() => setAction('')}
          onRecorded={onRecorded}
        />
      )}
    </>
  )
}
