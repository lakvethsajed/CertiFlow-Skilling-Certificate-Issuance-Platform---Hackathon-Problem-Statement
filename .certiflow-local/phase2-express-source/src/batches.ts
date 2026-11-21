import { Prisma, type BatchStatus, type PrismaClient } from '@prisma/client'
import { z } from 'zod'

import { type Actor } from './auth.js'
import { HttpError } from './http.js'
import { batchInput, inspectBatch } from './validation.js'

export const requiredApprovals = 2
export const openStatuses: BatchStatus[] = ['SUBMITTED', 'UNDER_REVIEW']
export const advancedStatuses: BatchStatus[] = [
  'PENDING_QUALITY_REVIEW',
  'PENDING_STATE_APPROVAL',
  'CERTIFICATES_GENERATED'
]
export const statusLabels: Record<BatchStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  RETURNED_FOR_CORRECTION: 'Returned',
  REJECTED: 'Rejected',
  PENDING_QUALITY_REVIEW: 'Pending Quality Review',
  PENDING_STATE_APPROVAL: 'Pending State Approval',
  CERTIFICATES_GENERATED: 'Certificates Generated'
}
export const scope = (actor: Actor): Prisma.BatchWhereInput =>
  actor.role === 'TRAINING_CENTRE'
    ? { centreId: actor.centreId! }
    : { centre: { districtId: actor.districtId! }, status: { not: 'DRAFT' } }
const revisionInclude = {
  candidates: { orderBy: { rowNumber: 'asc' } },
  approvals: { orderBy: { createdAt: 'asc' }, include: { officer: { select: { name: true } } } },
  audit: { orderBy: { createdAt: 'asc' } }
} satisfies Prisma.BatchRevisionInclude
export const batchInclude = {
  certificate: { select: { code: true } },
  centre: { include: { district: true } },
  revisions: { orderBy: { number: 'asc' }, include: revisionInclude }
} satisfies Prisma.BatchInclude
type FullBatch = Prisma.BatchGetPayload<{ include: typeof batchInclude }>

export function formatBatch(batch: FullBatch, actor: Actor) {
  const revision = batch.revisions.find((item) => item.number === batch.revision)!
  const form = revision.form as Record<string, string>
  const students = revision.candidates.map(
    (candidate) =>
      candidate.data as unknown as NonNullable<
        z.infer<typeof batchInput>['upload']
      >['students'][number]
  )
  const count = revision.approvals.filter((item) => item.decision === 'APPROVE').length
  const validation = inspectBatch(form as Parameters<typeof inspectBatch>[0], students)
  const errorsByRow = new Map(validation.technical.map((item) => [item.rowNumber, item.errors]))
  const lastDecision = revision.approvals.at(-1)
  const auditLabels: Record<string, string> = {
    SUBMITTED: 'Submitted by Training Centre',
    RESUBMITTED: 'Corrected batch resubmitted',
    ADVANCED: 'District review completed',
    APPROVE: 'District officer approved',
    RETURN: 'Returned for corrections',
    REJECT: 'Rejected by district officer'
  }
  return {
    ...form,
    id: batch.id,
    centre: batch.centre.name,
    district: batch.centre.district.name,
    status: statusLabels[batch.status],
    workflowStatus: batch.status,
    version: batch.version,
    revision: batch.revision,
    stage:
      batch.status === 'DRAFT'
        ? 0
        : batch.status === 'CERTIFICATES_GENERATED'
          ? 6
          : advancedStatuses.includes(batch.status)
            ? 3
            : batch.status === 'SUBMITTED'
              ? 1
              : count
                ? 3
                : 2,
    qualityRequired: batch.qualityRequired,
    createdAt: batch.createdAt,
    submittedAt: revision.submittedAt,
    upload: revision.upload,
    count: students.length,
    students: students.map((student) => ({
      ...student,
      errors: errorsByRow.get(student.rowNumber) ?? []
    })),
    certificatesIssued: Number(Boolean(batch.certificate)),
    correctionDraft: actor.role === 'TRAINING_CENTRE' ? batch.correctionDraft : null,
    reason:
      lastDecision?.decision === 'RETURN'
        ? 'Returned for corrections'
        : lastDecision?.decision === 'REJECT'
          ? 'Rejected'
          : null,
    comment: lastDecision?.decision !== 'APPROVE' ? lastDecision?.comment : null,
    returnedAt: lastDecision?.decision === 'RETURN' ? lastDecision.createdAt : null,
    approvalsReceived: count,
    approvalsRequired: requiredApprovals,
    canReview:
      actor.role === 'DISTRICT_OFFICER' &&
      openStatuses.includes(batch.status) &&
      !revision.approvals.some((item) => item.officerId === actor.id),
    decisions: batch.revisions.flatMap((item) =>
      item.approvals.map((decision) => ({
        id: decision.id,
        officer: decision.officer.name,
        role: 'District Officer',
        decision: decision.decision,
        date: decision.createdAt,
        comment: decision.comment,
        revision: item.number
      }))
    ),
    history: [
      { label: 'Batch created', date: batch.createdAt },
      ...batch.revisions.flatMap((item) =>
        item.audit
          .filter((event) => auditLabels[event.action])
          .map((event) => ({
            label: auditLabels[event.action],
            date: event.createdAt,
            note: event.comment,
            revision: item.number
          }))
      )
    ],
    validation
  }
}

export async function findScoped(
  db: PrismaClient | Prisma.TransactionClient,
  id: string,
  actor: Actor
) {
  const batch = await db.batch.findFirst({ where: { id, ...scope(actor) }, include: batchInclude })
  if (!batch) throw new HttpError(404, 'Batch not found.')
  return batch
}

export async function lockBatch(db: Prisma.TransactionClient, id: string, actor: Actor) {
  const allowed =
    actor.role === 'TRAINING_CENTRE'
      ? Prisma.sql`batch."centreId" = ${actor.centreId}`
      : Prisma.sql`centre."districtId" = ${actor.districtId} AND batch."status" <> 'DRAFT'`
  const rows = await db.$queryRaw<Array<{ id: string }>>`
    SELECT batch."id" FROM "Batch" AS batch
    JOIN "TrainingCentre" AS centre ON centre."id" = batch."centreId"
    WHERE batch."id" = ${id} AND ${allowed}
    FOR UPDATE OF batch
  `
  if (!rows.length) throw new HttpError(404, 'Batch not found.')
}

export function audit(
  db: Prisma.TransactionClient,
  revisionId: string,
  actor: Actor,
  action: string,
  comment?: string
) {
  return db.auditLog.create({
    data: { revisionId, actorId: actor.id, actorRole: actor.role, action, comment }
  })
}
