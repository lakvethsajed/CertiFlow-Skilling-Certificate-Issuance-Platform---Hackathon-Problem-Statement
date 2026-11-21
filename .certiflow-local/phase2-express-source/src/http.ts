import { Prisma } from '@prisma/client'
import type { ErrorRequestHandler } from 'express'
import { ZodError } from 'zod'

export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
  ) {
    super(message)
  }
}

export const handleError: ErrorRequestHandler = (error, _request, response, _next) => {
  if (error instanceof HttpError) {
    response.status(error.status).json({ message: error.message, details: error.details })
  } else if (error instanceof ZodError) {
    response
      .status(400)
      .json({ message: 'Check the submitted information.', details: error.flatten() })
  } else if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
    response.status(409).json({ message: 'This operation conflicts with an existing record.' })
  } else if (error.status === 413 || error.status === 400) {
    response
      .status(error.status)
      .json({ message: error.status === 413 ? 'Request is too large.' : 'Invalid request.' })
  } else {
    console.error('Request failed', error instanceof Error ? error.name : 'Unknown error')
    response.status(500).json({ message: 'The service could not complete your request.' })
  }
}
