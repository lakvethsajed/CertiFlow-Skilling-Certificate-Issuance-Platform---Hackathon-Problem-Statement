import 'dotenv/config'

import { PrismaClient, type Role } from '@prisma/client'
import bcrypt from 'bcryptjs'

const password = process.env.DEMO_PASSWORD
if (
  process.env.ENABLE_DEMO_SEED !== 'true' ||
  process.env.NODE_ENV === 'production' ||
  !password ||
  password.length < 12 ||
  Buffer.byteLength(password) > 72
) {
  throw new Error(
    'Set ENABLE_DEMO_SEED=true and a 12–72 byte DEMO_PASSWORD in a non-production environment.'
  )
}
const db = new PrismaClient()
try {
  const passwordHash = await bcrypt.hash(password, 12)
  await db.$transaction(async (transaction) => {
    await transaction.district.upsert({
      where: { id: 'demo-district' },
      create: { id: 'demo-district', name: 'Demo District' },
      update: {}
    })
    await transaction.trainingCentre.upsert({
      where: { id: 'demo-centre' },
      create: { id: 'demo-centre', name: 'Demo Training Centre', districtId: 'demo-district' },
      update: {}
    })
    const accounts: Array<[string, Role]> = [
      ['Anika', 'TRAINING_CENTRE'],
      ['Dev', 'DISTRICT_OFFICER'],
      ['Meera', 'DISTRICT_OFFICER'],
      ['Kabir', 'DISTRICT_OFFICER'],
      ['Neha', 'QUALITY_TEAM'],
      ['Farah', 'STATE_OFFICE']
    ]
    for (const [name, role] of accounts) {
      const email = name.toLowerCase() + '@certiflow.example'
      await transaction.user.upsert({
        where: { email },
        create: {
          name,
          email,
          role,
          passwordHash,
          centreId: role === 'TRAINING_CENTRE' ? 'demo-centre' : null,
          districtId: role === 'DISTRICT_OFFICER' ? 'demo-district' : null
        },
        update: {}
      })
    }
  })
  console.log('Demo accounts available. Existing accounts were preserved.')
} finally {
  await db.$disconnect()
}
