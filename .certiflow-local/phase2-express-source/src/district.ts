import { Prisma, type BatchStatus, type Decision, type PrismaClient } from '@prisma/client'
import { Router } from 'express'
import { z } from 'zod'

import { userOf, type Actor } from './auth.js'
import {
  advancedStatuses,
  audit,
  findScoped,
  formatBatch,
  lockBatch,
  openStatuses,
  requiredApprovals,
  scope,
  statusLabels
} from './batches.js'
import { HttpError } from './http.js'

const decisionInput = z
  .object({
    revision: z.number().int().positive(),
    comment: z.string().trim().max(2000).default('')
  })
  .strict()

async function decide(
  db: PrismaClient,
  actor: Actor,
  id: string,
  decision: Decision,
  body: unknown
) {
  const input = decisionInput.parse(body)
  if (decision !== 'APPROVE' && !input.comment)
    throw new HttpError(400, 'Enter a reason for this decision.')
  return db.$transaction(
    async (transaction) => {
      await lockBatch(transaction, id, actor)
      const batch = await findScoped(transaction, id, actor)
      if (batch.revision !== input.revision || !openStatuses.includes(batch.status))
        throw new HttpError(409, 'This revision is no longer open for review.')
      const revision = batch.revisions.find((item) => item.number === input.revision)!
      if (revision.approvals.some((item) => item.officerId === actor.id))
        throw new HttpError(409, 'You already recorded a decision for this revision.')
      const validation = formatBatch(batch, actor).validation
      if (
        decision === 'APPROVE' &&
        (validation.technical.length || validation.batchFindings.length)
      ) {
        throw new HttpError(422, 'This batch has blocking validation errors.', validation)
      }
      await transaction.approval.create({
        data: { revisionId: revision.id, officerId: actor.id, decision, comment: input.comment }
      })
      await audit(transaction, revision.id, actor, decision, input.comment || undefined)
      const approvals = await transaction.approval.count({
        where: { revisionId: revision.id, decision: 'APPROVE' }
      })
      const advanced = decision === 'APPROVE' && approvals >= requiredApprovals
      const status =
        decision === 'RETURN'
          ? 'RETURNED_FOR_CORRECTION'
          : decision === 'REJECT'
            ? 'REJECTED'
            : !advanced
              ? 'UNDER_REVIEW'
              : batch.qualityRequired
                ? 'PENDING_QUALITY_REVIEW'
                : 'PENDING_STATE_APPROVAL'
      await transaction.batch.update({ where: { id }, data: { status, version: { increment: 1 } } })
      if (advanced) await audit(transaction, revision.id, actor, 'ADVANCED')
      return formatBatch(await findScoped(transaction, id, actor), actor)
    },
    { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted }
  )
}

const reviewViews = {
  pending: openStatuses,
  approved: advancedStatuses,
  returned: ['RETURNED_FOR_CORRECTION'],
  rejected: ['REJECTED']
} satisfies Record<string, BatchStatus[]>

export function districtRoutes(db: PrismaClient) {
  const router = Router()
  router.get('/dashboard', async (request, response) => {
    const actor = userOf(request)
    const counts = await db.batch.groupBy({ by: ['status'], where: scope(actor), _count: true })
    const count = (statuses: BatchStatus[]) =>
      counts
        .filter((item) => statuses.includes(item.status))
        .reduce((sum, item) => sum + item._count, 0)
    const reviewed = await db.batch.count({
      where: { ...scope(actor), revisions: { some: { approvals: { some: {} } } } }
    })
    response.json({
      pending: count(openStatuses),
      reviewed,
      approved: count(advancedStatuses),
      returned: count(reviewViews.returned),
      rejected: count(reviewViews.rejected)
    })
  })
  router.get('/batches', async (request, response) => {
    const actor = userOf(request)
    const view = z
      .enum(['pending', 'approved', 'returned', 'rejected', 'history'])
      .parse(request.query.view ?? 'pending')
    const where: Prisma.BatchWhereInput = {
      AND: [
        scope(actor),
        view === 'history'
          ? { revisions: { some: { approvals: { some: {} } } } }
          : { status: { in: reviewViews[view] } }
      ]
    }
    const batches = await db.batch.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      include: {
        centre: { include: { district: true } },
        revisions: {
          select: {
            number: true,
            form: true,
            submittedAt: true,
            _count: { select: { candidates: true, approvals: { where: { decision: 'APPROVE' } } } }
          }
        }
      }
    })
    response.json(
      batches.map((batch) => {
        const revision = batch.revisions.find((item) => item.number === batch.revision)!
        const form = revision.form as Record<string, string>
        return {
          id: batch.id,
          name: form.name,
          course: form.course,
          centre: batch.centre.name,
          district: batch.centre.district.name,
          submittedAt: revision.submittedAt,
          status: statusLabels[batch.status],
          count: revision._count.candidates,
          approvalsReceived: revision._count.approvals,
          approvalsRequired: requiredApprovals
        }
      })
    )
  })
  router.get('/batches/:id', async (request, response) => {
    const actor = userOf(request)
    const batch = await findScoped(db, z.string().uuid().parse(request.params.id), actor)
    const revision = batch.revisions.find((item) => item.number === batch.revision)!
    await audit(db, revision.id, actor, 'OPENED')
    response.json(formatBatch(batch, actor))
  })
  router.post('/batches/:id/:action', async (request, response) => {
    const { id, action } = z
      .object({ id: z.string().uuid(), action: z.enum(['approve', 'return', 'reject']) })
      .parse(request.params)
    response.json(
      await decide(db, userOf(request), id, action.toUpperCase() as Decision, request.body)
    )
  })
  return router
}
