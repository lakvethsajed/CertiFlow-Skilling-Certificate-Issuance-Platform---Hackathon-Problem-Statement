export const columns = [
  'student_name',
  'student_id',
  'email',
  'phone_number',
  'course_name',
  'marks',
  'assessment_date'
]

export function dateIsValid(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(value + 'T00:00:00Z')
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value
}

export function readCsv(text) {
  const records = []
  let row = [],
    field = '',
    state = 'plain',
    line = 1,
    rowNumber = 1
  const source = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
  function finishRecord() {
    row.push(field.trim())
    if (row.some(Boolean) || row.length > 1) records.push({ rowNumber, cells: row })
    row = []
    field = ''
    state = 'plain'
  }
  for (let index = 0; index < source.length; index++) {
    const char = source[index]
    if (state === 'quoted') {
      if (char === '"') {
        if (source[index + 1] === '"') {
          field += '"'
          index++
        } else state = 'closed'
      } else {
        field += char
        if (char === '\n') line++
      }
    } else if (char === ',') {
      row.push(field.trim())
      field = ''
      state = 'plain'
    } else if (char === '\n') {
      finishRecord()
      rowNumber = ++line
    } else if (char === '"' && !field && state === 'plain') {
      state = 'quoted'
    } else if (char === '"' || state === 'closed') {
      throw new Error(`Row ${rowNumber}: Unexpected character after or inside a quoted field.`)
    } else {
      field += char
    }
  }
  if (state === 'quoted')
    throw new Error(`Row ${rowNumber}: Quoted field is missing its closing quote.`)
  finishRecord()
  const header = records.shift()?.cells.map((cell) => cell.toLowerCase()) ?? []
  const missing = columns.filter((column) => !header.includes(column))
  if (missing.length) throw new Error(`Missing CSV columns: ${missing.join(', ')}.`)
  if (new Set(header).size !== header.length)
    throw new Error('The CSV contains duplicate column headers.')
  if (!records.length) throw new Error('The CSV must contain at least one student record.')
  return records.map(({ rowNumber, cells }) => ({
    rowNumber,
    malformed: cells.length !== header.length,
    ...Object.fromEntries(columns.map((column) => [column, cells[header.indexOf(column)] ?? '']))
  }))
}

export function validateStudents(students, batch = {}) {
  const ids = new Map()
  for (const student of students) {
    const id = student.student_id.toLowerCase()
    if (id) ids.set(id, (ids.get(id) ?? 0) + 1)
  }
  return students.map((student) => {
    const errors = []
    if (student.malformed) errors.push('Column count does not match the header.')
    if (!student.student_name) errors.push('Student name is missing.')
    if (!student.student_id) errors.push('Student ID is missing.')
    else if (ids.get(student.student_id.toLowerCase()) > 1) errors.push('Duplicate student ID.')
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(student.email)) errors.push('Invalid email address.')
    if (!/^(?:\+91)?[6-9]\d{9}$/.test(student.phone_number.replace(/[\s()-]/g, '')))
      errors.push('Invalid phone number.')
    if (!student.course_name) errors.push('Course name is missing.')
    else if (batch.course && student.course_name.toLowerCase() !== batch.course.toLowerCase())
      errors.push('Course does not match the batch course.')
    if (!/^\d+(?:\.\d+)?$/.test(student.marks) || Number(student.marks) > 100)
      errors.push('Marks must be between 0 and 100.')
    if (!dateIsValid(student.assessment_date))
      errors.push('Assessment date must be a valid YYYY-MM-DD date.')
    return { ...student, errors }
  })
}

export function downloadCsv(filename, rows) {
  const csv = rows
    .map((row) =>
      row
        .map((value) => {
          const text = String(value ?? '')
          const safe = /^[\s]*[=+\-@]/.test(text) ? "'" + text : text
          return '"' + safe.replaceAll('"', '""') + '"'
        })
        .join(',')
    )
    .join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
