import 'dotenv/config'

import { PrismaClient } from '@prisma/client'

import { createApp } from './app.js'

const databaseUrl = process.env.DATABASE_URL
const secret = process.env.JWT_SECRET
if (!databaseUrl || !secret || Buffer.byteLength(secret) < 32) {
  throw new Error('Configure DATABASE_URL and a JWT_SECRET of at least 32 bytes in backend/.env.')
}
const production = process.env.NODE_ENV === 'production'
const origin = process.env.APP_ORIGIN
if (production && !origin) throw new Error('Set APP_ORIGIN to the public HTTPS origin.')
const origins = production
  ? [origin!]
  : [origin ?? 'http://localhost:5173', 'http://localhost:5173', 'http://127.0.0.1:5173']
const db = new PrismaClient({ datasourceUrl: databaseUrl })
const port = Number(process.env.PORT ?? 3001)
const app = createApp(db, secret, origins)
await db.$connect()
const server = app.listen(port, process.env.HOST ?? '127.0.0.1', () =>
  console.log(`CertiFlow API listening on port ${port}`)
)
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.once(signal, () =>
    server.close(() => {
      void db.$disconnect()
    })
  )
}
