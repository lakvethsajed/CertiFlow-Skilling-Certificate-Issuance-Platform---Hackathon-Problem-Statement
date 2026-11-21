import { Prisma, type PrismaClient } from '@prisma/client'
import { Router } from 'express'
import { z } from 'zod'

import { userOf, type Actor } from './auth.js'
import { audit, batchInclude, findScoped, formatBatch, lockBatch, scope } from './batches.js'
import { HttpError } from './http.js'
import { batchInput, validateUpload } from './validation.js'

export function centreRoutes(db: PrismaClient) {
  const router = Router()
  router.get('/batches', async (request, response) => {
    const actor = userOf(request)
    const batches = await db.batch.findMany({
      where: scope(actor),
      include: batchInclude,
      orderBy: { createdAt: 'desc' }
    })
    response.json(batches.map((batch) => formatBatch(batch, actor)))
  })
  async function save(actor: Actor, body: unknown, id?: string) {
    const input = batchInput.parse(body)
    const students = validateUpload(input)
    return db.$transaction(async (transaction) => {
      if (id) await lockBatch(transaction, id, actor)
      const existing = id ? await findScoped(transaction, id, actor) : null
      if (
        existing &&
        (existing.version !== input.version ||
          !['DRAFT', 'RETURNED_FOR_CORRECTION'].includes(existing.status))
      ) {
        throw new HttpError(409, 'This batch changed. Reload it before editing.')
      }
      const { centre: _centre, district: _district, ...form } = input.form
      const upload = input.upload
        ? { name: input.upload.name, size: input.upload.size }
        : Prisma.DbNull
      const returned = existing?.status === 'RETURNED_FOR_CORRECTION'
      if (existing && returned && !input.submit) {
        await transaction.batch.update({
          where: { id: existing.id },
          data: {
            correctionDraft: {
              ...form,
              centre: existing.centre.name,
              district: existing.centre.district.name,
              students,
              upload: input.upload ? { name: input.upload.name, size: input.upload.size } : null
            },
            version: { increment: 1 }
          }
        })
        return formatBatch(await findScoped(transaction, existing.id, actor), actor)
      }
      const number = existing ? existing.revision + Number(returned) : 1
      const status = input.submit ? 'SUBMITTED' : 'DRAFT'
      const batch = existing
        ? await transaction.batch.update({
            where: { id: existing.id },
            data: {
              revision: number,
              status,
              correctionDraft: Prisma.DbNull,
              version: { increment: 1 }
            }
          })
        : await transaction.batch.create({ data: { centreId: actor.centreId!, status } })
      const revision = await transaction.batchRevision.upsert({
        where: { batchId_number: { batchId: batch.id, number } },
        create: {
          batchId: batch.id,
          number,
          form,
          upload,
          submittedAt: input.submit ? new Date() : null
        },
        update: { form, upload, submittedAt: input.submit ? new Date() : null }
      })
      await transaction.candidate.deleteMany({ where: { revisionId: revision.id } })
      await transaction.candidate.createMany({
        data: students.map((student) => ({
          revisionId: revision.id,
          rowNumber: student.rowNumber,
          data: student
        }))
      })
      if (input.submit)
        await audit(transaction, revision.id, actor, returned ? 'RESUBMITTED' : 'SUBMITTED')
      return formatBatch(await findScoped(transaction, batch.id, actor), actor)
    })
  }
  router.post('/batches', async (request, response) =>
    response.status(201).json(await save(userOf(request), request.body))
  )
  router.put('/batches/:id', async (request, response) =>
    response.json(
      await save(userOf(request), request.body, z.string().uuid().parse(request.params.id))
    )
  )
  return router
}
