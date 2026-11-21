import assert from 'node:assert/strict'
import { randomBytes, randomUUID } from 'node:crypto'
import { once } from 'node:events'
import { test } from 'node:test'

import { PrismaClient, type Role } from '@prisma/client'
import bcrypt from 'bcryptjs'

import { createApp } from '../src/app.js'

const url = process.env.TEST_DATABASE_URL
test(
  'PostgreSQL review API enforces scopes, revisions and concurrent approval rules',
  { skip: !url && 'Set TEST_DATABASE_URL to a migrated test database.' },
  async (t) => {
    const db = new PrismaClient({ datasourceUrl: url })
    const server = createApp(db, randomBytes(48).toString('hex'), 'http://localhost:5173').listen(
      0,
      '127.0.0.1'
    )
    await once(server, 'listening')
    t.after(async () => {
      await new Promise<void>((resolve) => server.close(() => resolve()))
      await db.$disconnect()
    })
    const address = server.address()
    if (!address || typeof address === 'string') throw new Error('Expected TCP address.')
    const port = address.port
    const prefix = 'test-' + randomUUID()
    const password = randomBytes(24).toString('hex')
    const passwordHash = await bcrypt.hash(password, 4)
    const district = await db.district.create({ data: { id: prefix, name: 'Test district' } })
    const outside = await db.district.create({
      data: { id: prefix + '-outside', name: 'Outside district' }
    })
    const centre = await db.trainingCentre.create({
      data: { id: prefix, districtId: district.id, name: 'Test centre' }
    })
    async function account(name: string, role: Role, districtId?: string, centreId?: string) {
      const email = name + '@' + prefix + '.example'
      return db.user.create({ data: { name, email, passwordHash, role, districtId, centreId } })
    }
    const training = await account('training', 'TRAINING_CENTRE', undefined, centre.id)
    const first = await account('first', 'DISTRICT_OFFICER', district.id)
    const second = await account('second', 'DISTRICT_OFFICER', district.id)
    const third = await account('third', 'DISTRICT_OFFICER', district.id)
    const outsider = await account('outside', 'DISTRICT_OFFICER', outside.id)
    const quality = await account('quality', 'QUALITY_TEAM')

    async function request(path: string, cookie?: string, method = 'GET', data?: unknown) {
      const response = await fetch('http://127.0.0.1:' + port + '/api' + path, {
        method,
        headers: {
          ...(cookie ? { cookie } : {}),
          ...(data ? { 'Content-Type': 'application/json' } : {})
        },
        body: data ? JSON.stringify(data) : undefined
      })
      return {
        status: response.status,
        body: await response.json().catch(() => null),
        cookie: response.headers.get('set-cookie')?.split(';')[0]
      }
    }
    async function login(email: string) {
      const result = await request('/auth/login', undefined, 'POST', { email, password })
      assert.equal(result.status, 200)
      assert.equal(result.body.passwordHash, undefined)
      return result.cookie!
    }
    const [admin, one, two, three, crossDistrict, qualityUser] = await Promise.all(
      [training, first, second, third, outsider, quality].map((user) => login(user.email))
    )
    const form = {
      name: 'Uploaded batch',
      course: 'Python Programming',
      trainer: 'Test trainer',
      description: '',
      startDate: '2026-01-01',
      endDate: '2026-01-20',
      assessmentDate: '2026-01-21',
      centre: 'Spoofed centre',
      district: 'Spoofed district'
    }
    const upload = {
      name: 'test.csv',
      size: 200,
      students: [
        {
          rowNumber: 2,
          student_name: 'Test candidate',
          student_id: 'TEST-1',
          email: 'student@example.test',
          phone_number: '9990000001',
          course_name: form.course,
          marks: '87',
          assessment_date: form.assessmentDate
        }
      ]
    }
    const body = { form, upload, submit: true, confirmed: true }
    async function submit() {
      const result = await request('/centre/batches', admin, 'POST', body)
      assert.equal(result.status, 201)
      assert.equal(result.body.centre, centre.name)
      assert.equal(result.body.district, district.name)
      return result.body.id as string
    }
    const batchId = await submit()
    const detail = (id: string) => '/district/batches/' + id
    const decision = (
      id: string,
      cookie: string | undefined,
      action = 'approve',
      comment = '',
      revision = 1
    ) => request(detail(id) + '/' + action, cookie, 'POST', { revision, comment })

    await t.test('rejects unauthorized users and cross-district access', async () => {
      assert.equal((await decision(batchId, admin)).status, 403)
      assert.equal((await decision(batchId, qualityUser)).status, 403)
      assert.equal((await decision(batchId, undefined)).status, 401)
      assert.equal((await request(detail(batchId), crossDistrict)).status, 404)
      assert.equal((await decision(batchId, crossDistrict)).status, 404)
      assert.deepEqual((await request('/district/batches', crossDistrict)).body, [])
      assert.equal((await request('/auth/me', one)).body.role, 'DISTRICT_OFFICER')
      const anonymous = await request('/auth/session')
      assert.equal(anonymous.status, 200)
      assert.deepEqual(anonymous.body, { user: null })
      assert.equal((await request('/auth/session', one)).body.user.role, 'DISTRICT_OFFICER')
      assert.equal((await request('/auth/logout', qualityUser, 'POST')).status, 204)
      assert.equal((await request('/auth/me', qualityUser)).status, 401)
      assert.deepEqual((await request('/auth/session', qualityUser)).body, { user: null })
    })

    await t.test(
      'accepts one decision per officer and advances after two distinct approvals',
      async () => {
        const approval = await decision(batchId, one)
        assert.equal(approval.status, 200)
        assert.equal(approval.body.approvalsReceived, 1)
        assert.equal(approval.body.workflowStatus, 'UNDER_REVIEW')
        assert.equal((await decision(batchId, one)).status, 409)
        const final = await decision(batchId, two)
        assert.equal(final.status, 200)
        assert.equal(final.body.approvalsReceived, 2)
        assert.equal(final.body.workflowStatus, 'PENDING_QUALITY_REVIEW')
        assert.equal((await decision(batchId, three)).status, 409)
      }
    )

    await t.test(
      'serializes concurrent approvals and records exactly one advancement',
      async () => {
        const id = await submit()
        const results = await Promise.all([
          decision(id, one),
          decision(id, one),
          decision(id, two),
          decision(id, three)
        ])
        assert.deepEqual(results.map((result) => result.status).sort(), [200, 200, 409, 409])
        const records = await db.auditLog.findMany({ where: { revision: { batchId: id } } })
        assert.equal(records.filter((record) => record.action === 'ADVANCED').length, 1)
        assert.equal(records.filter((record) => record.action === 'APPROVE').length, 2)
        assert.ok(
          records.some((record) => record.action === 'SUBMITTED' && record.actorId === training.id)
        )
      }
    )

    await t.test(
      'requires reasons, preserves history and resets approvals after resubmission',
      async () => {
        const id = await submit()
        assert.equal((await decision(id, one)).status, 200)
        assert.equal((await decision(id, two, 'return', '   ')).status, 400)
        const returned = await decision(id, two, 'return', 'Verify candidate information.')
        assert.equal(returned.status, 200)
        assert.equal(returned.body.workflowStatus, 'RETURNED_FOR_CORRECTION')
        const corrected = await request('/centre/batches/' + id, admin, 'PUT', {
          ...body,
          version: returned.body.version
        })
        assert.equal(corrected.status, 200)
        assert.equal(corrected.body.revision, 2)
        assert.equal(corrected.body.approvalsReceived, 0)
        assert.equal(corrected.body.decisions.length, 2)
        assert.equal((await decision(id, one, 'approve', '', 1)).status, 409)
        assert.equal((await decision(id, one, 'approve', '', 2)).body.approvalsReceived, 1)
        assert.equal((await decision(id, two, 'approve', '', 2)).body.approvalsReceived, 2)
        const records = await db.auditLog.findMany({ where: { revision: { batchId: id } } })
        assert.ok(
          records.some(
            (record) => record.action === 'RETURN' && record.actorId === second.id && record.comment
          )
        )
        assert.ok(
          records.some(
            (record) => record.action === 'RESUBMITTED' && record.actorRole === 'TRAINING_CENTRE'
          )
        )
      }
    )

    await t.test('centre drafts stay private and invalid CSV uploads write no batch', async () => {
      const draft = await request('/centre/batches', admin, 'POST', {
        ...body,
        upload: null,
        submit: false,
        confirmed: false
      })
      assert.equal(draft.status, 201)
      assert.equal(draft.body.workflowStatus, 'DRAFT')
      assert.equal((await request(detail(draft.body.id), one)).status, 404)
      const before = await db.batch.count({ where: { centreId: centre.id } })
      const invalid = await request('/centre/batches', admin, 'POST', {
        ...body,
        upload: { ...upload, students: [{ ...upload.students[0], email: 'invalid' }] }
      })
      assert.equal(invalid.status, 422)
      assert.equal(invalid.body.details.technical[0].rowNumber, 2)
      assert.equal(await db.batch.count({ where: { centreId: centre.id } }), before)
    })

    await t.test(
      'certificate verification is public and returns only verification metadata',
      async () => {
        const id = await submit()
        const code = randomUUID()
        await db.batch.update({
          where: { id },
          data: {
            status: 'CERTIFICATES_GENERATED',
            certificate: { create: { code, issuedAt: new Date() } }
          }
        })
        const result = await request('/certificates/' + code)
        assert.equal(result.status, 200)
        assert.deepEqual(Object.keys(result.body).sort(), ['code', 'issuedAt'])
        assert.equal(result.body.code, code)
      }
    )

    await t.test('rejection blocks approval and centre edits, and is audited', async () => {
      const id = await submit()
      const rejected = await decision(id, one, 'reject', 'Eligibility requirements did not pass.')
      assert.equal(rejected.status, 200)
      assert.equal(rejected.body.workflowStatus, 'REJECTED')
      assert.equal((await decision(id, two)).status, 409)
      assert.equal(
        (
          await request('/centre/batches/' + id, admin, 'PUT', {
            ...body,
            version: rejected.body.version
          })
        ).status,
        409
      )
      assert.equal(
        await db.auditLog.count({
          where: { action: 'REJECT', actorId: first.id, revision: { batchId: id } }
        }),
        1
      )
      assert.equal((await request('/certificates/missing')).status, 404)
    })
  }
)
