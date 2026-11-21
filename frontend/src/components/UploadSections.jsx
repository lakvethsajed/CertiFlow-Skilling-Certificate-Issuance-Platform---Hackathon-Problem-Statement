import React, { useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, CloudUpload, Download, FileSpreadsheet, X } from 'lucide-react'

import { courses } from '../data/batchOptions'
import { columns, downloadCsv } from '../services/studentCsv'
import { formatDate } from './BatchUI'

export const batchFields = [
  ['name', 'Batch Name', 'text'],
  ['course', 'Course Name', 'select'],
  ['centre', 'Training Centre', 'readonly', 'Enter training centre name'],
  ['district', 'District', 'readonly', 'Enter district'],
  ['startDate', 'Training Start Date', 'date'],
  ['endDate', 'Training End Date', 'date'],
  ['assessmentDate', 'Assessment Date', 'date'],
  ['trainer', 'Trainer Name', 'text'],
  ['description', 'Batch Description', 'textarea', 'Add any relevant notes about this batch']
]

export function BatchInformation({ form, baseline, errors, onChange }) {
  const [touched, setTouched] = useState({})

  return (
    <section className="card section">
      <h2>Batch information</h2>

      <p className="section-note">Enter the training and assessment details for this batch.</p>

      <div className="form-grid">
        {batchFields.map(([key, label, type, placeholder]) => {
          const changed = baseline && key in baseline && (baseline[key] ?? '') !== form[key]

          const message = touched[key] ? errors[key] : ''

          const props = {
            id: key,
            value: form[key] ?? '',
            onChange: (event) => onChange(key, event.target.value),
            onBlur: () =>
              setTouched((current) => ({
                ...current,
                [key]: true
              })),
            'aria-invalid': Boolean(message),
            'aria-describedby': message ? key + '-error' : undefined
          }

          return (
            <div
              key={key}
              className={(type === 'textarea' ? 'full ' : '') + (changed ? 'changed' : '')}
            >
              <label htmlFor={key}>
                {label}{' '}
                {type === 'textarea' ? (
                  <small>(optional)</small>
                ) : (
                  type !== 'readonly' && <span className="required">*</span>
                )}
              </label>

              {type === 'select' ? (
                <select {...props} required>
                  <option value="">Select a course</option>

                  {courses.map((course) => (
                    <option key={course}>{course}</option>
                  ))}
                </select>
              ) : type === 'textarea' ? (
                <textarea {...props} placeholder={placeholder} rows={3} />
              ) : type === 'readonly' ? (
                <input id={key} value={props.value} readOnly />
              ) : (
                <input
                  {...props}
                  required
                  type={type}
                  placeholder={placeholder}
                  min={
                    key === 'endDate'
                      ? form.startDate || undefined
                      : key === 'assessmentDate'
                        ? form.endDate || undefined
                        : undefined
                  }
                />
              )}

              {message && (
                <small className="field-error" id={key + '-error'}>
                  {message}
                </small>
              )}

              {changed && (
                <small className="changed-note">Previously {baseline[key] || 'blank'}</small>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

export function CSVUploader({ upload, loading, error, onFile, onRemove }) {
  const input = useRef(null)
  const [dragging, setDragging] = useState(false)

  return (
    <section className="card section">
      <div className="section-header">
        <div>
          <h2>Upload Student Spreadsheet</h2>
          <p>
            Upload a CSV file containing the details of candidates who successfully completed the
            training.
          </p>
        </div>

        <button
          className="button secondary"
          onClick={() => downloadCsv('certiflow-template.csv', [columns])}
        >
          <Download size={16} />
          Download CSV Template
        </button>
      </div>

      <input
        className="visually-hidden"
        type="file"
        accept=".csv,text/csv"
        ref={input}
        tabIndex={-1}
        aria-label="Student CSV file"
        onChange={(event) => {
          onFile(event.target.files[0])
          event.target.value = ''
        }}
      />

      <div
        className={'dropzone' + (dragging ? ' dragging' : '')}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          onFile(event.dataTransfer.files[0])
        }}
      >
        <span className="stat-icon blue">
          <CloudUpload size={22} />
        </span>

        <div>
          <strong>Drag and drop your CSV here</strong>
          <p>CSV files only</p>
        </div>

        <button className="button secondary" onClick={() => input.current.click()}>
          {upload || error ? 'Replace file' : 'Browse files'}
        </button>
      </div>

      {loading && (
        <p className="inline" role="status">
          <span className="spinner" />
          Reading spreadsheet…
        </p>
      )}

      {error && (
        <div className="notice error inline" role="alert">
          <AlertCircle size={18} />
          {error}

          <button className="icon-button" aria-label="Clear file error" onClick={onRemove}>
            <X size={18} />
          </button>
        </div>
      )}

      {upload && (
        <div className="file-row">
          <FileSpreadsheet size={22} />

          <div>
            <strong>{upload.name}</strong>
            <small>
              {upload.size < 1024 ? upload.size + ' B' : (upload.size / 1024).toFixed(1) + ' KB'}
              {' · File read successfully'}
            </small>
          </div>

          <button
            className="icon-button"
            onClick={onRemove}
            aria-label="Remove spreadsheet"
            title="Remove spreadsheet"
          >
            <X size={19} />
          </button>
        </div>
      )}
    </section>
  )
}

// 3. Validation Results Component
export function ValidationResults({ students, upload, fileError }) {
  const invalid = students.filter((student) => student.errors.length)

  const hasError = invalid.length > 0 || Boolean(fileError)

  return (
    <section className="card section">
      <div className="section-header">
        <div>
          <h2>Validation results</h2>
          <p>Review candidate records before submission.</p>
        </div>

        {hasError && (
          <button
            className="button secondary"
            onClick={() =>
              downloadCsv('certiflow-validation-errors.csv', [
                ['row_number', 'student_id', 'error'],
                ...(fileError
                  ? [[fileError.match(/^Row (\d+)/)?.[1] ?? '', '', fileError]]
                  : invalid.flatMap((student) =>
                      student.errors.map((error) => [student.rowNumber, student.student_id, error])
                    ))
              ])
            }
          >
            <Download size={16} />
            Download error report
          </button>
        )}
      </div>

      {upload ? (
        <div className="validation-counts">
          <div>
            <strong>{students.length}</strong>
            <span>Total records</span>
          </div>

          <div>
            <strong className="valid-text">{students.length - invalid.length}</strong>
            <span>Valid records</span>
          </div>

          <div>
            <strong className="field-error">{invalid.length}</strong>
            <span>Invalid records</span>
          </div>
        </div>
      ) : null}

      {hasError ? (
        <div className="notice error" role="alert">
          <strong>
            Your batch contains errors. Please correct the invalid records and upload the file
            again.
          </strong>

          {fileError ? (
            <p>{fileError}</p>
          ) : (
            <ul>
              {invalid.map((student) => (
                <li key={student.rowNumber}>
                  <strong>Row {student.rowNumber}</strong>
                  {' · '}
                  {student.errors.join(' ')}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : upload ? (
        <div className="notice success inline" role="status">
          <CheckCircle2 size={18} />
          All student records passed validation.
        </div>
      ) : (
        <p className="muted">Upload a spreadsheet to validate your records.</p>
      )}
    </section>
  )
}

// 4. Submission Summary Component
export function SubmissionSummary({
  form,
  upload,
  ready,
  confirmed,
  onConfirm,
  canSubmit,
  canSave,
  onSave,
  onSubmit,
  correcting,
  error
}) {
  const fields = [
    ['Batch name', form.name],
    ['Course', form.course],
    ['Training centre', form.centre],
    ['Total students', upload?.students.length],
    ['Assessment date', formatDate(form.assessmentDate)],
    ['Validation status', upload ? (ready ? 'Passed' : 'Errors found') : 'Awaiting CSV']
  ]

  return (
    <section className="card section submission">
      <h2>Submission summary</h2>

      <dl className="details-grid">
        {fields.map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{(value ?? '') === '' ? '—' : value}</dd>
          </div>
        ))}
      </dl>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => onConfirm(event.target.checked)}
        />

        <span>
          I confirm that the uploaded student information is accurate and that all listed candidates
          have successfully completed the training and assessment.
        </span>
      </label>

      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}

      <div className="submission-actions">
        <small>Changes are saved to your training centre workspace.</small>

        <div className="inline">
          <button className="button secondary" disabled={!canSave} onClick={onSave}>
            Save as Draft
          </button>

          <button className="button primary" disabled={!canSubmit} onClick={onSubmit}>
            {correcting ? 'Resubmit Batch for Approval' : 'Submit Batch for Approval'}
          </button>
        </div>
      </div>
    </section>
  )
}
