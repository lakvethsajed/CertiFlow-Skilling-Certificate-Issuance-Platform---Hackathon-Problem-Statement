import React, { useEffect, useRef } from 'react'
import { CheckCircle2, X } from 'lucide-react'

export function SuccessModal({ batch, onClose }) {
  const dialog = useRef(null)
  useEffect(() => {
    dialog.current.showModal()
  }, [])
  return (
    <dialog
      className="modal card"
      ref={dialog}
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      aria-labelledby="success-title"
    >
      <button
        className="icon-button modal-close"
        aria-label="Close success dialog"
        onClick={onClose}
      >
        <X size={20} />
      </button>
      <span className="stat-icon green">
        <CheckCircle2 size={25} />
      </span>
      <h2 id="success-title">Batch Submitted Successfully</h2>
      <p>Your batch has been submitted for district-level approval.</p>
      <div className="modal-id">
        <small>Batch ID</small>
        <strong>{batch.id}</strong>
      </div>
      <button className="button primary" onClick={onClose}>
        View Batch Details
      </button>
    </dialog>
  )
}
