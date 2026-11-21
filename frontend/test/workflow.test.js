import { test } from 'node:test'
import assert from 'node:assert/strict'
import { batchErrors } from '../src/services/batchService.js'
import { columns, readCsv, validateStudents } from '../src/services/studentCsv.js'

const form = {
  name: 'Python Cohort',
  course: 'Python Programming',
  trainer: 'Demo Trainer',
  centre: 'Test Training Centre',
  district: 'Test District',
  startDate: '2026-10-01',
  endDate: '2026-11-09',
  assessmentDate: '2026-11-10',
  description: ''
}
test('CSV validation preserves source lines and flags every duplicate occurrence', () => {
  const csv = [
    columns.join(','),
    '"Demo, Student",ID,demo@example.com,9849001201,Python Programming,88,2026-11-10',
    '',
    ',id,demo@example.com,123,Python Programming,101,2026-02-30'
  ].join('\r\n')
  const rows = validateStudents(readCsv('\uFEFF' + csv), form)
  assert.deepEqual(
    rows.map((row) => row.rowNumber),
    [2, 4]
  )
  assert.equal(rows[0].student_name, 'Demo, Student')
  assert.deepEqual(rows[0].errors, ['Duplicate student ID.'])
  assert.equal(rows[1].errors.length, 5)
  assert.throws(() => readCsv(columns.join(',') + '\n"Open quote'), /Row 2/)
  assert.throws(() => readCsv(columns.join(',')), /at least one/)
})

test('date validation checks both ordering and calendar dates', () => {
  assert.deepEqual(batchErrors(form), {})
  assert.deepEqual(batchErrors({ ...form, centre: ' ', district: '' }), {
    centre: 'This field is required.',
    district: 'This field is required.'
  })
  assert.match(batchErrors({ ...form, endDate: '2026-09-30' }).endDate, /after the start date/)
  assert.match(batchErrors({ ...form, assessmentDate: '2026-02-30' }).assessmentDate, /valid date/)
})
