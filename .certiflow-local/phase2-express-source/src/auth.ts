import type { PrismaClient, Role } from '@prisma/client'
import bcrypt from 'bcryptjs'
import { Router, type Request, type RequestHandler } from 'express'
import rateLimit from 'express-rate-limit'
import jwt from 'jsonwebtoken'
import { z } from 'zod'

import { HttpError } from './http.js'

const cookieName = 'certiflow_session'
const lifetime = 8 * 60 * 60
const cookieOptions = {
  httpOnly: true,
  sameSite: 'strict' as const,
  secure: process.env.NODE_ENV === 'production',
  path: '/api'
}
const credentials = z
  .object({ email: z.string().trim().email().max(254), password: z.string().min(1).max(72) })
  .strict()
const timingHash = bcrypt.hashSync('unused-login-fallback', 12)
const selectUser = {
  id: true,
  name: true,
  email: true,
  role: true,
  districtId: true,
  centreId: true,
  district: { select: { name: true } },
  centre: { select: { name: true, district: { select: { name: true } } } }
} as const

export type Actor = { id: string; role: Role; districtId: string | null; centreId: string | null }

export function userOf(request: Request): Actor {
  return request.auth!.user
}

declare module 'express-serve-static-core' {
  interface Request {
    auth?: { sessionId: string; user: Actor }
  }
}

export function authentication(db: PrismaClient, secret: string) {
  async function readSession(request: Request) {
    const token = request.headers.cookie
      ?.split(/;\s*/)
      .find((cookie) => cookie.startsWith(cookieName + '='))
      ?.slice(cookieName.length + 1)
    if (!token) return undefined
    try {
      const claims = jwt.verify(token, secret, {
        algorithms: ['HS256'],
        issuer: 'certiflow',
        audience: 'certiflow-web'
      })
      if (
        typeof claims === 'string' ||
        typeof claims.jti !== 'string' ||
        typeof claims.sub !== 'string'
      )
        return undefined
      const session = await db.session.findUnique({
        where: { id: claims.jti },
        include: { user: { select: selectUser } }
      })
      if (!session || session.userId !== claims.sub || session.expiresAt <= new Date())
        return undefined
      return { sessionId: session.id, user: session.user }
    } catch (error) {
      if (!(error instanceof jwt.JsonWebTokenError)) throw error
      return undefined
    }
  }

  const requireUser: RequestHandler = async (request, _response, next) => {
    const session = await readSession(request)
    if (!session) throw new HttpError(401, 'Please sign in.')
    request.auth = session
    next()
  }

  const router = Router()
  router.post(
    '/login',
    rateLimit({
      windowMs: 15 * 60_000,
      limit: 30,
      message: { message: 'Too many login attempts. Try again later.' }
    }),
    async (request, response) => {
      const input = credentials.parse(request.body)
      if (Buffer.byteLength(input.password) > 72)
        throw new HttpError(400, 'Invalid credentials format.')
      const account = await db.user.findUnique({
        where: { email: input.email.toLowerCase() },
        select: { ...selectUser, passwordHash: true }
      })
      const valid = await bcrypt.compare(input.password, account?.passwordHash ?? timingHash)
      if (!account || !valid) throw new HttpError(401, 'Email or password is incorrect.')
      const { passwordHash: _hash, ...user } = account
      const session = await db.session.create({
        data: { userId: user.id, expiresAt: new Date(Date.now() + lifetime * 1000) }
      })
      const token = jwt.sign({}, secret, {
        algorithm: 'HS256',
        issuer: 'certiflow',
        audience: 'certiflow-web',
        subject: user.id,
        jwtid: session.id,
        expiresIn: lifetime
      })
      response.cookie(cookieName, token, { ...cookieOptions, maxAge: lifetime * 1000 }).json(user)
    }
  )
  router.get('/session', async (request, response) => {
    const session = await readSession(request)
    response.json({ user: session?.user ?? null })
  })
  router.get('/me', requireUser, (request, response) => response.json(userOf(request)))
  router.post('/logout', requireUser, async (request, response) => {
    await db.session.deleteMany({ where: { id: request.auth!.sessionId } })
    response.clearCookie(cookieName, cookieOptions).sendStatus(204)
  })
  return { router, requireUser }
}

export function requireRole(role: Role): RequestHandler {
  return (request, _response, next) => {
    const user = userOf(request)
    if (
      user.role !== role ||
      (role === 'DISTRICT_OFFICER' && !user.districtId) ||
      (role === 'TRAINING_CENTRE' && !user.centreId)
    ) {
      throw new HttpError(403, 'This account does not have access.')
    }
    next()
  }
}
