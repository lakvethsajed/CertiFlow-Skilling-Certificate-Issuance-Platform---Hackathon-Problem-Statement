import React, { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CircleCheck, ClipboardList, CloudUpload, ListChecks } from 'lucide-react'
import { ApprovalHistory } from './Batches'
import { EmptyState, PageHeading, formatDate } from '../components/BatchUI'
import { StudentPreview } from '../components/StudentPreview'
import {
  BatchInformation,
  CSVUploader,
  SubmissionSummary,
  ValidationResults,
  batchFields
} from '../components/UploadSections'
import { batchErrors, emptyBatch } from '../services/batchService'
import { centreApi } from '../services/api'
import { readCsv, validateStudents } from '../services/studentCsv'

function BatchEditor({ existing, setBatches, organisation }) {
  const correcting = existing?.status === 'Returned'
  const initial = existing?.correctionDraft ?? existing
  const [form, setForm] = useState(() =>
    Object.fromEntries(
      Object.entries(emptyBatch).map(([key, value]) => [
        key,
        key === 'centre'
          ? (organisation?.name ?? '')
          : key === 'district'
            ? (organisation?.district?.name ?? '')
            : (initial?.[key] ?? value)
      ])
    )
  )
  const [upload, setUpload] = useState(() =>
    initial?.upload ? { ...initial.upload, students: initial.students } : null
  )
  const [fileError, setFileError] = useState('')
  const [loading, setLoading] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const request = useRef(0)
  const version = useRef(existing?.version)
  const navigate = useNavigate()
  const students = validateStudents(upload?.students ?? [], form)
  const errors = batchErrors(form)
  const ready = Boolean(
    upload && students.length && students.every((student) => !student.errors.length)
  )
  const canSave = !saving && !loading && !fileError && (!upload || ready)
  const canSubmit = canSave && ready && confirmed && !Object.keys(errors).length
  const reset = () => {
    request.current++
    setUpload(null)
    setFileError('')
    setLoading(false)
    setConfirmed(false)
    setSaved(false)
  }
  async function selectFile(file) {
    if (!file) return
    reset()
    const token = request.current
    if (!/\.csv$/i.test(file.name)) {
      setFileError('Choose a file with a .csv extension.')
      return
    }
    setLoading(true)
    try {
      const records = readCsv(await file.text())
      if (token === request.current)
        setUpload({ name: file.name, size: file.size, students: records })
    } catch (error) {
      if (token === request.current) setFileError(error.message)
    } finally {
      if (token === request.current) setLoading(false)
    }
  }
  async function persist(submit) {
    setSaveError('')
    setSaving(true)
    try {
      const batch = await centreApi.save({
        id: existing?.id,
        version: version.current,
        form,
        upload,
        submit,
        confirmed
      })
      version.current = batch.version
      setBatches((current) =>
        existing
          ? current.map((item) => (item.id === batch.id ? batch : item))
          : [batch, ...current]
      )
      if (submit)
        navigate('/batches/' + batch.id, { state: { submitted: true }, replace: Boolean(existing) })
      else if (existing) setSaved(true)
      else navigate('/batches/' + batch.id, { state: { draftSaved: true } })
    } catch (error) {
      setSaveError(error.message)
    } finally {
      setSaving(false)
    }
  }
  const anchors = [
    ['batch-information', 'Batch information', ClipboardList],
    ['spreadsheet', 'Student spreadsheet', CloudUpload],
    ['validation', 'Validation results', ListChecks],
    ['submission', 'Submission summary', CircleCheck]
  ]
  return (
    <>
      <PageHeading
        title={
          correcting ? 'Correct and Resubmit Batch' : existing ? 'Edit Draft' : 'Upload New Batch'
        }
        subtitle={
          correcting
            ? existing.id + ' · Update the batch and upload a corrected spreadsheet.'
            : 'Upload your completed training batch and submit eligible candidates for certificate approval.'
        }
      />
      <div className="editor-layout">
        <div className="stack">
          {correcting && (
            <>
              <section className="card section">
                <h2>Previous submission</h2>
                <div className="notice warning">
                  <strong>{existing.reason}</strong>
                  <p>{existing.comment}</p>
                </div>
                <dl className="details-grid">
                  {batchFields
                    .filter(([key]) => key in existing)
                    .map(([key, label, type]) => (
                      <div key={key}>
                        <dt>{label}</dt>
                        <dd>
                          {(type === 'date' ? formatDate(existing[key]) : existing[key]) || '—'}
                        </dd>
                      </div>
                    ))}
                  <div>
                    <dt>Submitted</dt>
                    <dd>{formatDate(existing.submittedAt)}</dd>
                  </div>
                  <div>
                    <dt>Students</dt>
                    <dd>{existing.count}</dd>
                  </div>
                </dl>
                {upload && <p className="changed-note">Replacement spreadsheet · {upload.name}</p>}
              </section>
              <ApprovalHistory history={existing.history} />
            </>
          )}
          <div id="batch-information">
            <BatchInformation
              form={form}
              baseline={correcting ? existing : null}
              errors={errors}
              onChange={(key, value) => {
                setForm((current) => ({ ...current, [key]: value }))
                setConfirmed(false)
                setSaved(false)
              }}
            />
          </div>
          <div id="spreadsheet">
            <CSVUploader
              upload={upload}
              loading={loading}
              error={fileError}
              onFile={selectFile}
              onRemove={reset}
            />
          </div>
          <StudentPreview key={upload?.name} students={students} />
          <div id="validation">
            <ValidationResults students={students} upload={upload} fileError={fileError} />
          </div>
          <div id="submission">
            <SubmissionSummary
              form={form}
              upload={upload}
              ready={ready}
              confirmed={confirmed}
              onConfirm={setConfirmed}
              canSave={canSave}
              canSubmit={canSubmit}
              onSave={() => persist(false)}
              onSubmit={() => persist(true)}
              correcting={correcting}
              error={saveError}
            />
          </div>
          {saved && (
            <div className="notice success" role="status">
              Draft saved.
            </div>
          )}
        </div>
        <aside className="card section editor-index">
          <h2>On this page</h2>
          {anchors.map(([id, label, Icon]) => (
            <a key={id} href={'#' + id}>
              <Icon size={17} />
              {label}
            </a>
          ))}
        </aside>
      </div>
    </>
  )
}

export function UploadBatch({ batches, setBatches, organisation }) {
  const { id } = useParams()
  const existing = batches.find((item) => item.id === id)
  if (id && (!existing || !['Draft', 'Returned'].includes(existing.status)))
    return (
      <div className="card">
        <EmptyState title={existing ? 'This batch is locked' : 'Batch not found'}>
          <Link to={existing ? '/batches/' + id : '/batches'}>Back to batch records</Link>
        </EmptyState>
      </div>
    )
  return (
    <BatchEditor
      key={id ?? 'new'}
      existing={existing}
      setBatches={setBatches}
      organisation={organisation}
    />
  )
}
