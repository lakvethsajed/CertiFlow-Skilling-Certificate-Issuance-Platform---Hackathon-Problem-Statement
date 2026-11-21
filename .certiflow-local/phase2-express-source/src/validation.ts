import { z } from 'zod'
import { dateIsValid, validateStudents } from '../../frontend/src/services/studentCsv.js'

import { HttpError } from './http.js'

const line = z.string().trim().max(250)
const formSchema = z.object({
  name: line,
  course: line,
  trainer: line,
  startDate: z.string().max(10),
  endDate: z.string().max(10),
  assessmentDate: z.string().max(10),
  description: z.string().max(4000),
  centre: line.optional(),
  district: line.optional()
})
const studentSchema = z.object({
  rowNumber: z.number().int().min(2).max(1_000_000),
  malformed: z.boolean().optional(),
  student_name: line,
  student_id: line,
  email: line,
  phone_number: line,
  course_name: line,
  marks: line,
  assessment_date: line
})
export const batchInput = z
  .object({
    form: formSchema,
    upload: z
      .object({
        name: z
          .string()
          .max(255)
          .regex(/\.csv$/i),
        size: z.number().int().min(1).max(10_000_000),
        students: z.array(studentSchema).min(1).max(5000)
      })
      .nullable(),
    submit: z.boolean(),
    confirmed: z.boolean(),
    version: z.number().int().positive().optional()
  })
  .strict()

export function inspectBatch(
  form: z.infer<typeof formSchema>,
  students: z.infer<typeof studentSchema>[]
) {
  const batchFindings = []
  for (const [label, value] of [
    ['Batch name', form.name],
    ['Course', form.course],
    ['Trainer', form.trainer]
  ]) {
    if (!value.trim()) batchFindings.push(label + ' is required.')
  }
  for (const [label, value] of [
    ['Training start date', form.startDate],
    ['Training end date', form.endDate],
    ['Assessment date', form.assessmentDate]
  ]) {
    if (!dateIsValid(value)) batchFindings.push(label + ' is invalid.')
  }
  if (form.startDate > form.endDate)
    batchFindings.push('Training end date precedes the start date.')
  if (form.endDate > form.assessmentDate)
    batchFindings.push('Assessment precedes the training end date.')
  const validated: { rowNumber: number; errors: string[] }[] = validateStudents(
    students.map((student) => ({ ...student, malformed: student.malformed ?? false })),
    form
  )
  const technical = validated
    .filter((student) => student.errors.length)
    .map(({ rowNumber, errors }) => ({ rowNumber, errors }))
  if (!students.length) batchFindings.push('At least one candidate is required.')
  const districtFindings = students
    .filter(
      (student) =>
        dateIsValid(student.assessment_date) &&
        dateIsValid(form.assessmentDate) &&
        student.assessment_date !== form.assessmentDate
    )
    .map((student) => ({
      rowNumber: student.rowNumber,
      message: 'Candidate assessment date differs from the batch assessment date.'
    }))
  return { technical, batchFindings, districtFindings }
}

export function validateUpload(input: z.infer<typeof batchInput>) {
  const students = input.upload?.students ?? []
  const results = inspectBatch(input.form, students)
  if (new Set(students.map((student) => student.rowNumber)).size !== students.length) {
    throw new HttpError(422, 'Candidate row numbers must be unique.')
  }
  if (
    results.technical.length ||
    (input.submit && (!input.confirmed || results.batchFindings.length))
  ) {
    throw new HttpError(422, 'Correct the validation findings and confirm the submission.', results)
  }
  return students
}
