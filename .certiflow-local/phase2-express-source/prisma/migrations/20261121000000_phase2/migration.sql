CREATE TYPE "Role" AS ENUM ('TRAINING_CENTRE', 'DISTRICT_OFFICER', 'QUALITY_TEAM', 'STATE_OFFICE', 'CANDIDATE');

CREATE TYPE "BatchStatus" AS ENUM ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'RETURNED_FOR_CORRECTION', 'REJECTED', 'PENDING_QUALITY_REVIEW', 'PENDING_STATE_APPROVAL', 'CERTIFICATES_GENERATED');

CREATE TYPE "Decision" AS ENUM ('APPROVE', 'RETURN', 'REJECT');

CREATE TABLE "District" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,

    CONSTRAINT "District_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "TrainingCentre" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "districtId" TEXT NOT NULL,

    CONSTRAINT "TrainingCentre_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "role" "Role" NOT NULL,
    "districtId" TEXT,
    "centreId" TEXT,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "Session" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Batch" (
    "id" TEXT NOT NULL,
    "centreId" TEXT NOT NULL,
    "status" "BatchStatus" NOT NULL DEFAULT 'DRAFT',
    "revision" INTEGER NOT NULL DEFAULT 1,
    "version" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "qualityRequired" BOOLEAN NOT NULL DEFAULT true,
    "correctionDraft" JSONB,

    CONSTRAINT "Batch_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "BatchRevision" (
    "id" TEXT NOT NULL,
    "batchId" TEXT NOT NULL,
    "number" INTEGER NOT NULL,
    "form" JSONB NOT NULL,
    "upload" JSONB,
    "submittedAt" TIMESTAMP(3),

    CONSTRAINT "BatchRevision_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Candidate" (
    "id" TEXT NOT NULL,
    "revisionId" TEXT NOT NULL,
    "rowNumber" INTEGER NOT NULL,
    "data" JSONB NOT NULL,

    CONSTRAINT "Candidate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Approval" (
    "id" TEXT NOT NULL,
    "revisionId" TEXT NOT NULL,
    "officerId" TEXT NOT NULL,
    "decision" "Decision" NOT NULL,
    "comment" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Approval_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" TEXT NOT NULL,
    "revisionId" TEXT NOT NULL,
    "actorId" TEXT NOT NULL,
    "actorRole" "Role" NOT NULL,
    "action" TEXT NOT NULL,
    "comment" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuditLog_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Certificate" (
    "code" TEXT NOT NULL,
    "batchId" TEXT NOT NULL,
    "issuedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Certificate_pkey" PRIMARY KEY ("code")
);

-- CreateIndex
CREATE INDEX "TrainingCentre_districtId_idx" ON "TrainingCentre"("districtId");

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "Session_userId_idx" ON "Session"("userId");

-- CreateIndex
CREATE INDEX "Batch_centreId_status_idx" ON "Batch"("centreId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "BatchRevision_batchId_number_key" ON "BatchRevision"("batchId", "number");

-- CreateIndex
CREATE UNIQUE INDEX "Candidate_revisionId_rowNumber_key" ON "Candidate"("revisionId", "rowNumber");

-- CreateIndex
CREATE INDEX "Approval_officerId_createdAt_idx" ON "Approval"("officerId", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "Approval_revisionId_officerId_key" ON "Approval"("revisionId", "officerId");

-- CreateIndex
CREATE INDEX "AuditLog_revisionId_createdAt_idx" ON "AuditLog"("revisionId", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "Certificate_batchId_key" ON "Certificate"("batchId");

-- AddForeignKey
ALTER TABLE "TrainingCentre" ADD CONSTRAINT "TrainingCentre_districtId_fkey" FOREIGN KEY ("districtId") REFERENCES "District"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "User" ADD CONSTRAINT "User_districtId_fkey" FOREIGN KEY ("districtId") REFERENCES "District"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "User" ADD CONSTRAINT "User_centreId_fkey" FOREIGN KEY ("centreId") REFERENCES "TrainingCentre"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Session" ADD CONSTRAINT "Session_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Batch" ADD CONSTRAINT "Batch_centreId_fkey" FOREIGN KEY ("centreId") REFERENCES "TrainingCentre"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "BatchRevision" ADD CONSTRAINT "BatchRevision_batchId_fkey" FOREIGN KEY ("batchId") REFERENCES "Batch"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Candidate" ADD CONSTRAINT "Candidate_revisionId_fkey" FOREIGN KEY ("revisionId") REFERENCES "BatchRevision"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Approval" ADD CONSTRAINT "Approval_revisionId_fkey" FOREIGN KEY ("revisionId") REFERENCES "BatchRevision"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Approval" ADD CONSTRAINT "Approval_officerId_fkey" FOREIGN KEY ("officerId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_revisionId_fkey" FOREIGN KEY ("revisionId") REFERENCES "BatchRevision"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_actorId_fkey" FOREIGN KEY ("actorId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Certificate" ADD CONSTRAINT "Certificate_batchId_fkey" FOREIGN KEY ("batchId") REFERENCES "Batch"("id") ON DELETE RESTRICT ON UPDATE CASCADE;


-- Require a stored scope for both active workflow roles.
ALTER TABLE "User" ADD CONSTRAINT "User_required_scope"
  CHECK (("role" <> 'DISTRICT_OFFICER' OR "districtId" IS NOT NULL)
     AND ("role" <> 'TRAINING_CENTRE' OR "centreId" IS NOT NULL));
