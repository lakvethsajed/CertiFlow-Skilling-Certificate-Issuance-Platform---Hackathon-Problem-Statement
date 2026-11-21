import React from 'react'
import { Link } from 'react-router-dom'
import {
  Award,
  CalendarDays,
  ChevronRight,
  Clock3,
  Layers3,
  RotateCcw,
  Upload,
  ShieldCheck,
  FileCheck2
} from 'lucide-react'
import { BatchTable, PageHeading, formatDate } from '../components/BatchUI'

export function Dashboard({ batches }) {
  const pending = (item) =>
    ['Submitted', 'Under Review', 'Pending Quality Review', 'Pending State Approval'].includes(
      item.status
    )
  const returned = (item) => item.status === 'Returned'
  const stats = [
    ['Total Batches', batches.length, 'All training batches', Layers3, 'blue', '/batches'],
    [
      'Pending Approval',
      batches.filter(pending).length,
      'Awaiting officer review',
      Clock3,
      'amber',
      '/pending'
    ],
    [
      'Returned for Correction',
      batches.filter(returned).length,
      'Require your attention',
      RotateCcw,
      'rose',
      '/returned'
    ],
    [
      'Certificates Issued',
      batches
        .filter((item) => item.status === 'Certificates Generated')
        .reduce((total, item) => total + (item.certificatesIssued ?? 0), 0)
        .toLocaleString('en-IN'),
      'Across approved batches',
      Award,
      'green',
      '/certificates'
    ]
  ]
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Kolkata' }).format(new Date())
  const recent = [...batches]
    .filter((batch) => batch.submittedAt)
    .sort((a, b) => b.submittedAt.localeCompare(a.submittedAt))
    .slice(0, 5)
  return (
    <>
      <PageHeading
        title="Welcome to CertiFlow"
        subtitle="Manage your training batches and track certificate approvals."
      >
        <span className="today">
          <CalendarDays size={16} />
          {formatDate(today)}
        </span>
      </PageHeading>
      <div className="stats">
        {stats.map(([label, value, caption, Icon, theme, route]) => (
          <Link to={route} className="card stat" key={label}>
            <div className="stat-top">
              <span className={'stat-icon ' + theme}>
                <Icon size={21} />
              </span>
              <ChevronRight size={18} className="stat-chevron" />
            </div>
            <div className="stat-label">{label}</div>
            <strong>{value}</strong>
            <small>{caption}</small>
          </Link>
        ))}
      </div>
      <section className="upload-banner">
        <div className="banner-body">
          <span className="banner-icon">
            <Upload size={24} />
          </span>
          <div>
            <h2>Ready to submit a new batch?</h2>
            <p>Upload candidate records and send your batch for certificate approval.</p>
          </div>
        </div>
        <Link className="button banner-button" to="/upload">
          <Upload size={17} /> Upload New Batch
        </Link>
      </section>
      <section className="card recent">
        <div className="section-header">
          <div>
            <h2>Recent batches</h2>
            <p>Track your latest submissions and their approval status.</p>
          </div>
          <Link className="button secondary" to="/batches">
            View all batches
          </Link>
        </div>
        <BatchTable batches={recent} emptyTitle="No recent activity available." />
        <div className="table-footer">Showing {recent.length} recent submissions</div>
      </section>
      <div className="dashboard-links">
        <Link className="card dashboard-link" to="/pending">
          <span className="stat-icon blue">
            <ShieldCheck size={20} />
          </span>
          <span>
            <strong>Approval tracking</strong>
            <small>Check your submissions in review</small>
          </span>
          <ChevronRight size={18} />
        </Link>
        <Link className="card dashboard-link" to="/certificates">
          <span className="stat-icon green">
            <FileCheck2 size={20} />
          </span>
          <span>
            <strong>Certificate records</strong>
            <small>View batches with generated certificates</small>
          </span>
          <ChevronRight size={18} />
        </Link>
      </div>
    </>
  )
}
