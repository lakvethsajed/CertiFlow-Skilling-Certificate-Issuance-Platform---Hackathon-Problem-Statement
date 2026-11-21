import React, { useState } from 'react'
import { Download } from 'lucide-react'

import { centreApi } from '../services/api'

export function ActivationCodeExport({ batchId }) {
  const [studentId, setStudentId] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState(null)

  async function download(id) {
    setBusy(true)
    setFeedback(null)
    try {
      await centreApi.downloadActivationCodes(batchId, id)
      setFeedback({ message: 'Download started. Share each code privately with its student.' })
      if (id) setStudentId('')
    } catch (error) {
      setFeedback({ message: error.message, error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card section stack">
      <h2>Student Activation Codes</h2>
      <p>
        New codes appear only in this download. Students can use them after final batch approval.
      </p>
      <div>
        <button type="button" className="button primary" disabled={busy} onClick={() => download()}>
          <Download size={16} /> Download Activation Codes
        </button>
      </div>
      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault()
          void download(studentId.trim())
        }}
      >
        <label>
          Student ID for a lost or expired code
          <input
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
            maxLength={250}
            required
          />
        </label>
        <div>
          <button className="button secondary" disabled={busy || !studentId.trim()}>
            Regenerate and Download
          </button>
        </div>
      </form>
      {feedback && (
        <p
          className={'notice ' + (feedback.error ? 'error' : 'success')}
          role={feedback.error ? 'alert' : 'status'}
        >
          {feedback.message}
        </p>
      )}
    </section>
  )
}
