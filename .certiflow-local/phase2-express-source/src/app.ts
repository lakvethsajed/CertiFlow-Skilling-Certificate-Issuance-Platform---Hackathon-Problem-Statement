import type { PrismaClient } from '@prisma/client'
import express from 'express'
import { z } from 'zod'

import { authentication, requireRole } from './auth.js'
import { centreRoutes } from './centre.js'
import { districtRoutes } from './district.js'
import { handleError, HttpError } from './http.js'

export function createApp(db: PrismaClient, secret: string, origin: string | readonly string[]) {
  if (Buffer.byteLength(secret) < 32) throw new Error('JWT_SECRET must contain at least 32 bytes.')
  const origins = new Set(typeof origin === 'string' ? [origin] : origin)
  const app = express()
  const auth = authentication(db, secret)
  app.disable('x-powered-by')
  app.use('/api', (request, response, next) => {
    response.set('Cache-Control', 'no-store')
    if (
      !['GET', 'HEAD', 'OPTIONS'].includes(request.method) &&
      request.headers.origin &&
      !origins.has(request.headers.origin)
    ) {
      return next(new HttpError(403, 'Request origin is not allowed.'))
    }
    next()
  })
  app.use(express.json({ limit: '4mb' }))
  app.use('/api/auth', auth.router)
  app.use('/api/centre', auth.requireUser, requireRole('TRAINING_CENTRE'), centreRoutes(db))
  app.use('/api/district', auth.requireUser, requireRole('DISTRICT_OFFICER'), districtRoutes(db))
  app.get('/api/certificates/:code', async (request, response) => {
    const code = z.string().min(1).max(128).parse(request.params.code)
    const certificate = await db.certificate.findFirst({
      where: { code, batch: { status: 'CERTIFICATES_GENERATED' } },
      select: { code: true, issuedAt: true }
    })
    if (!certificate) throw new HttpError(404, 'Certificate not found.')
    response.json(certificate)
  })
  app.use('/api', (_request, _response, next) => next(new HttpError(404, 'Endpoint not found.')))
  app.use(handleError)
  return app
}
