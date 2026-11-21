import React, { useState } from 'react'
import { Search } from 'lucide-react'
import { EmptyState, StatusBadge, formatDate } from './BatchUI'

const pageSize = 8

export function StudentPreview({ students, review = false, quality = false }) {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('rowNumber')

  const matched = students
    .filter(
      (student) => filter === 'all' || (filter === 'invalid') === Boolean(student.errors?.length)
    )
    .filter((student) =>
      [
        student.student_id,
        student.student_name,
        student.email,
        student.phone_number,
        student.course_name
      ].some((value) => value.toLowerCase().includes(query.trim().toLowerCase()))
    )

  if (review)
    matched.sort((first, second) =>
      String(first[sort]).localeCompare(String(second[sort]), undefined, { numeric: true })
    )

  const pages = Math.max(1, Math.ceil(matched.length / pageSize))
  const current = Math.min(page, pages)

  const invalid = students.filter((student) => student.errors?.length).length

  return (
    <section className="card">
      <div className="section-header">
        <div>
          <h2>{review ? 'Candidate Information' : 'Student data preview'}</h2>
          <p>
            {students.length} total · {students.length - invalid} valid · {invalid} invalid
          </p>
        </div>

        {review && (
          <label>
            Sort candidates
            <select
              value={sort}
              onChange={(event) => {
                setSort(event.target.value)
                setPage(1)
              }}
            >
              <option value="rowNumber">CSV row</option>
              <option value="student_id">Student ID</option>
              <option value="student_name">Student name</option>
              <option value="marks">Marks</option>
              <option value="assessment_date">Assessment date</option>
            </select>
          </label>
        )}
        {quality && (
          <label>
            Validation status
            <select
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value)
                setPage(1)
              }}
            >
              <option value="all">All candidates</option>
              <option value="valid">Valid</option>
              <option value="invalid">With errors</option>
            </select>
          </label>
        )}
        <div className="search-input">
          <Search size={17} />

          <input
            aria-label="Search students"
            placeholder="Search students"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              setPage(1)
            }}
          />
        </div>
      </div>

      {matched.length ? (
        <div className="table-scroll" role="region" aria-label="Student records" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th>Row</th>
                <th>Student ID</th>
                <th>Student Name</th>
                <th>Email</th>
                <th>Phone Number</th>
                <th>Course</th>
                <th>Marks</th>
                {review && <th>Assessment Date</th>}
                <th>Validation Status</th>
              </tr>
            </thead>

            <tbody>
              {matched.slice((current - 1) * pageSize, current * pageSize).map((student) => (
                <tr key={student.rowNumber} className={student.errors?.length ? 'invalid-row' : ''}>
                  <td>{student.rowNumber}</td>

                  <td>{student.student_id || '—'}</td>

                  <td>{student.student_name || '—'}</td>

                  <td>{student.email || '—'}</td>

                  <td>{student.phone_number || '—'}</td>

                  <td>{student.course_name || '—'}</td>

                  <td>{student.marks || '—'}</td>
                  {review && <td>{formatDate(student.assessment_date)}</td>}

                  <td>
                    <StatusBadge status={student.errors?.length ? 'Invalid' : 'Valid'} />

                    {student.errors?.length > 0 && (
                      <small className="row-error">{student.errors.join(' ')}</small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title={students.length ? 'No matching students' : 'No student records available.'}
        >
          {!students.length && 'Upload a CSV file to preview student details.'}
        </EmptyState>
      )}

      {matched.length > 0 && (
        <div className="table-footer pagination">
          <span>
            Showing {(current - 1) * pageSize + 1}–{Math.min(current * pageSize, matched.length)} of{' '}
            {matched.length}
          </span>

          <div className="inline">
            <button
              className="button secondary"
              disabled={current === 1}
              onClick={() => setPage(current - 1)}
            >
              Previous
            </button>

            <span aria-live="polite">
              {current} / {pages}
            </span>

            <button
              className="button secondary"
              disabled={current === pages}
              onClick={() => setPage(current + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
