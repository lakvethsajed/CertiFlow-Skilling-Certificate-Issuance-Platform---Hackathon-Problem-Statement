import { dateIsValid } from './studentCsv.js'

export const emptyBatch = {
  name: '',
  course: '',
  centre: '',
  district: '',
  startDate: '',
  endDate: '',
  assessmentDate: '',
  trainer: '',
  description: ''
}

export function batchErrors(batch) {
  const errors = {}
  for (const key of [
    'name',
    'course',
    'centre',
    'district',
    'startDate',
    'endDate',
    'assessmentDate',
    'trainer'
  ]) {
    if (!batch[key]?.trim()) errors[key] = 'This field is required.'
  }
  for (const key of ['startDate', 'endDate', 'assessmentDate']) {
    if (batch[key] && !dateIsValid(batch[key])) errors[key] = 'Enter a valid date.'
  }
  if (!errors.startDate && !errors.endDate && batch.endDate < batch.startDate)
    errors.endDate = 'End date must be on or after the start date.'
  if (!errors.endDate && !errors.assessmentDate && batch.assessmentDate < batch.endDate)
    errors.assessmentDate = 'Assessment date must be on or after the end date.'
  return errors
}
