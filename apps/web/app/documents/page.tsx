"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { getWorkspaceContext, type WorkspaceContext } from "../../lib/api";
import {
  downloadIntelligenceDocument,
  getIntelligenceDocument,
  getIntelligenceDocuments,
  reviewIntelligenceDocument,
  uploadIntelligenceDocument,
  type CandidateField,
  type IntelligenceDocument,
  type IntelligenceDocumentStatus,
  type IntelligenceDocumentType,
} from "../../lib/document-intelligence-api";
import styles from "./page.module.css";

type FieldName = "supplier_name" | "customer_name" | "invoice_number" | "receipt_number" | "purchase_order_number" | "invoice_date" | "due_date" | "subtotal" | "tax_amount" | "total" | "tax_id" | "currency_code";
type ReviewValues = Record<FieldName, string>;
const MAX_BYTES = 10 * 1024 * 1024;
const TYPES: { value: IntelligenceDocumentType; label: string }[] = [
  { value: "SUPPLIER_INVOICE", label: "Supplier invoice" },
  { value: "EXPENSE_RECEIPT", label: "Expense receipt" },
  { value: "CUSTOMER_INVOICE", label: "Customer invoice" },
  { value: "PURCHASE_ORDER", label: "Purchase order" },
  { value: "OTHER", label: "Other business document" },
];
const FIELDS: { key: FieldName; label: string; kind?: "date" | "number" }[] = [
  { key: "supplier_name", label: "Supplier name" },
  { key: "customer_name", label: "Customer name" },
  { key: "invoice_number", label: "Invoice number" },
  { key: "receipt_number", label: "Receipt number" },
  { key: "purchase_order_number", label: "Purchase order number" },
  { key: "invoice_date", label: "Document date", kind: "date" },
  { key: "due_date", label: "Due date", kind: "date" },
  { key: "subtotal", label: "Subtotal", kind: "number" },
  { key: "tax_amount", label: "Tax / VAT", kind: "number" },
  { key: "total", label: "Total amount", kind: "number" },
  { key: "currency_code", label: "Currency code" },
  { key: "tax_id", label: "Tax identification number" },
];
const EMPTY_REVIEW: ReviewValues = {
  supplier_name: "", customer_name: "", invoice_number: "", receipt_number: "", purchase_order_number: "",
  invoice_date: "", due_date: "", subtotal: "", tax_amount: "", total: "", currency_code: "", tax_id: "",
};

function friendlyStatus(status: IntelligenceDocumentStatus) {
  if (status === "NEEDS_REVIEW") return "Needs review";
  if (status === "CONFIRMED") return "Details confirmed";
  return "Rejected";
}
function statusClass(status: IntelligenceDocumentStatus) {
  return status === "CONFIRMED" ? "good" : status === "REJECTED" ? "neutral" : "warn";
}
function fileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
function fromCandidate(field?: CandidateField, fallback?: string | null) {
  return fallback ?? field?.value ?? "";
}
function fieldEvidence(field?: CandidateField) {
  if (!field?.value) return "No value was extracted. Enter it after checking the original document.";
  if (field.evidence) return `Read from: “${field.evidence}”`;
  return "No supporting text was detected. Check the original document.";
}
function isRequired(type: IntelligenceDocumentType, key: FieldName) {
  const required: Partial<Record<IntelligenceDocumentType, FieldName[]>> = {
    SUPPLIER_INVOICE: ["supplier_name", "invoice_number", "invoice_date", "currency_code", "total"],
    EXPENSE_RECEIPT: ["invoice_date", "currency_code", "total"],
    CUSTOMER_INVOICE: ["customer_name", "invoice_number", "invoice_date", "currency_code", "total"],
    PURCHASE_ORDER: ["supplier_name", "purchase_order_number", "currency_code", "total"],
  };
  return required[type]?.includes(key) ?? false;
}

export default function DocumentsPage() {
  const [workspace, setWorkspace] = useState<WorkspaceContext | null>(null);
  const [branchId, setBranchId] = useState("");
  const [documentType, setDocumentType] = useState<IntelligenceDocumentType>("SUPPLIER_INVOICE");
  const [file, setFile] = useState<File | null>(null);
  const [items, setItems] = useState<IntelligenceDocument[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<IntelligenceDocument | null>(null);
  const [reviewValues, setReviewValues] = useState<ReviewValues>(EMPTY_REVIEW);
  const [reviewReason, setReviewReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const assignedBranches = useMemo(() => (workspace?.branches ?? []).filter(branch => branch.assigned), [workspace]);

  const loadDocuments = useCallback(async (selectedBranch?: string) => {
    try {
      const result = await getIntelligenceDocuments({ branchId: selectedBranch || undefined, limit: 50 });
      setItems(result.items);
      const currentId = selectedId && result.items.some(item => item.id === selectedId) ? selectedId : result.items[0]?.id || "";
      setSelectedId(currentId);
      if (currentId) {
        const detail = await getIntelligenceDocument(currentId);
        setSelected(detail);
      } else {
        setSelected(null);
      }
    } catch (cause) {
      setItems([]);
      setSelected(null);
      setError(cause instanceof Error ? cause.message : "Documents couldn't be loaded. Try again.");
    }
  }, [selectedId]);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const data = await getWorkspaceContext();
      setWorkspace(data);
      const allowed = (data.branches ?? []).filter(branch => branch.assigned);
      const nextBranch = branchId && allowed.some(branch => branch.id === branchId) ? branchId : allowed[0]?.id || "";
      setBranchId(nextBranch);
      await loadDocuments(nextBranch);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "LEXA couldn't load your workspace. Try again.");
    } finally {
      setLoading(false);
    }
  }, [branchId, loadDocuments]);

  useEffect(() => { void load(); }, []); // Revalidation is user-triggered after the initial workspace check.
  useEffect(() => {
    if (!selected) { setReviewValues(EMPTY_REVIEW); return; }
    const candidate = selected.candidate_fields?.fields ?? {};
    const confirmed = selected.confirmed_fields;
    setReviewValues(Object.fromEntries(FIELDS.map(({ key }) => [key, fromCandidate(candidate[key], confirmed?.[key])])) as ReviewValues);
    setReviewReason(selected.review_reason || "");
  }, [selected?.id, selected?.status, selected?.confirmed_fields, selected?.candidate_fields]);

  async function refreshSelected(documentId: string) {
    setSelectedId(documentId);
    try { setSelected(await getIntelligenceDocument(documentId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "This document couldn't be opened."); }
  }

  async function upload() {
    if (!file) { setError("Choose a file first."); return; }
    if (!branchId) { setError("Choose an assigned business branch before uploading."); return; }
    if (file.size > MAX_BYTES) { setError("Choose a file no larger than 10 MB."); return; }
    setUploading(true); setError(""); setMessage("");
    try {
      const result = await uploadIntelligenceDocument(file, documentType, branchId);
      setMessage(result.duplicate ? "This file is already saved in this branch. The existing review was opened." : "Document saved. Check each extracted field against the original before confirming.");
      setFile(null);
      await loadDocuments(branchId);
      await refreshSelected(result.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "LEXA couldn't receive this document. Try again.");
    } finally { setUploading(false); }
  }

  async function review(action: "CONFIRM" | "REJECT") {
    if (!selected) return;
    setReviewing(true); setError(""); setMessage("");
    try {
      const result = await reviewIntelligenceDocument(selected.id, {
        action,
        ...(action === "CONFIRM" ? { confirmed_fields: Object.fromEntries(FIELDS.map(({ key }) => [key, reviewValues[key].trim() || null])) } : {}),
        ...(reviewReason.trim() ? { reason: reviewReason.trim() } : action === "REJECT" ? { reason: "Rejected after human review." } : {}),
      });
      setSelected(result);
      setMessage(action === "CONFIRM" ? "Details confirmed. No invoice, expense, payment or journal entry was created." : "Document rejected. No business transaction was created.");
      await loadDocuments(branchId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "LEXA couldn't save this review.");
    } finally { setReviewing(false); }
  }

  async function download() {
    if (!selected) return;
    try { await downloadIntelligenceDocument(selected); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "The original file couldn't be downloaded."); }
  }

  const candidateFields = selected?.candidate_fields?.fields ?? {};
  const canReview = Boolean(selected?.can_review && !reviewing);

  return <AppShell title="Documents" eyebrow="LEXA intelligence">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1240 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · DOCUMENTS</span>
          <h1>Turn business documents into checked details.</h1>
          <p>Upload an invoice, receipt or purchase order. LEXA reads locally where possible, shows the evidence and lets your team confirm the details before using the normal business workflow.</p>
        </div>
        <div className="header-actions"><button className="button button-soft" onClick={() => void load()} disabled={loading || uploading || reviewing} type="button">{loading ? "Refreshing…" : "Refresh"}</button><Link href="/purchasing" className="button button-dark">Open purchasing</Link></div>
      </div>

      <div className="notice" role="note"><strong>Review before using.</strong> Text recognition can be wrong. Original files stay within LEXA's branch-scoped store; document text is not sent to an AI provider. Confirmed details are a review result only—LEXA does not create or post financial records from this page.</div>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {message && <div className="notice" role="status">{message}</div>}

      <section className={`workspace-section ${styles.section}`} aria-labelledby="document-upload-title">
        <div className="section-head"><div><span className="section-label">STEP 1 · ADD A DOCUMENT</span><h2 id="document-upload-title">Upload a document</h2><p>PDF, JPG, PNG or WebP · Maximum 10 MB per file.</p></div></div>
        <div className={styles.uploadGrid}>
          <label className={styles.field}><span>Document type</span><select value={documentType} onChange={event => setDocumentType(event.target.value as IntelligenceDocumentType)} disabled={uploading}>{TYPES.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label className={styles.field}><span>Business branch</span><select value={branchId} onChange={event => setBranchId(event.target.value)} disabled={uploading || assignedBranches.length === 0} required><option value="">Choose an assigned branch</option>{assignedBranches.map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>
          <label className={`${styles.field} ${styles.fileField}`}><span>Choose file</span><input type="file" accept="application/pdf,image/jpeg,image/png,image/webp" onChange={event => { setFile(event.target.files?.[0] || null); setError(""); }} disabled={uploading} /><small>{file ? `${file.name} · ${fileSize(file.size)}` : "Use a clear scan or photo with readable text."}</small></label>
          <div className={styles.uploadAction}><button className="button button-dark" type="button" onClick={() => void upload()} disabled={uploading || !file || !branchId}>{uploading ? "Reading document…" : "Upload and read"}</button><small>Files are size-limited and processed without an external model.</small></div>
        </div>
      </section>

      <section className={`workspace-section ${styles.section}`} aria-labelledby="document-review-title">
        <div className="section-head"><div><span className="section-label">STEP 2 · CHECK THE DETAILS</span><h2 id="document-review-title">Document review</h2><p>Open a saved file to view extracted fields and the text that supports them.</p></div><span className="status neutral">{items.length} saved {items.length === 1 ? "document" : "documents"}</span></div>
        <div className={styles.reviewLayout}>
          <div className={styles.documentList} aria-label="Saved documents">
            {loading && <p role="status">Loading saved documents…</p>}
            {!loading && items.length === 0 && <div className="empty-state compact"><strong>No documents saved yet</strong><span>Upload a supplier invoice, receipt or purchase order to begin.</span></div>}
            {items.map(item => <button key={item.id} type="button" className={`${styles.documentItem} ${selected?.id === item.id ? styles.documentItemActive : ""}`} onClick={() => void refreshSelected(item.id)}>
              <span className={styles.documentGlyph} aria-hidden="true">{item.content_type === "application/pdf" ? "PDF" : "IMG"}</span>
              <span className={styles.documentItemText}><strong>{item.original_filename}</strong><small>{TYPES.find(type => type.value === item.document_type)?.label || item.document_type} · {fileSize(item.size_bytes)}</small><span className={`status ${statusClass(item.status)}`}>{friendlyStatus(item.status)}</span></span>
            </button>)}
          </div>

          <div className={styles.documentDetail}>
            {!selected && <div className="empty-state compact"><strong>Select a document</strong><span>Its candidate fields and source evidence will appear here.</span></div>}
            {selected && <>
              <div className={styles.detailHead}><div><h3>{selected.original_filename}</h3><p>{TYPES.find(type => type.value === selected.document_type)?.label || selected.document_type} · {fileSize(selected.size_bytes)} · {new Date(selected.created_at).toLocaleString("en-UG")}</p></div><button className="button button-soft" type="button" onClick={() => void download()}>Download original</button></div>
              <div className={styles.extractionNotice}><strong>{selected.extraction_status === "SUCCEEDED" ? "Text extracted" : selected.extraction_status === "PARTIAL" ? "Some text was found" : "Manual entry needed"}</strong><span>{selected.extraction_method.replaceAll("_", " ").toLowerCase()} · {selected.candidate_fields?.text_character_count ?? 0} characters. Recognition is not verification.</span></div>
              {selected.candidate_fields?.warnings?.map(warning => <p className={styles.warningLine} key={warning}>{warning}</p>)}
              <div className={styles.fieldsGrid}>
                {FIELDS.map(({ key, label, kind }) => {
                  const candidate = candidateFields[key];
                  const value = reviewValues[key] || "";
                  return <label className={styles.field} key={key}><span>{label}{canReview && isRequired(selected.document_type, key) ? " · required" : ""}</span><input type={kind || "text"} min={kind === "number" ? "0" : undefined} step={kind === "number" ? "0.01" : undefined} value={value} disabled={!canReview} onChange={event => setReviewValues(current => ({ ...current, [key]: event.target.value }))} placeholder={canReview ? "Check the original and enter if missing" : "No confirmed value"} /><small>{candidate?.value ? `Extracted: ${candidate.value}${candidate.confidence ? ` · label match ${Math.round(candidate.confidence * 100)}%` : ""}` : "No value extracted"}</small><small>{fieldEvidence(candidate)}</small></label>;
                })}
              </div>
              {selected.extracted_text_preview && <details className={styles.sourceText}><summary>View extracted text for cross-checking</summary><pre>{selected.extracted_text_preview}</pre></details>}
              {selected.review_reason && <p className={styles.warningLine}>Review note: {selected.review_reason}</p>}
              {canReview && <div className={styles.reviewActions}><label className={styles.field}><span>Review note (optional)</span><input value={reviewReason} onChange={event => setReviewReason(event.target.value)} maxLength={500} placeholder="For example, matched against the supplier's original invoice." /></label><div className="header-actions"><button className="button button-dark" type="button" disabled={reviewing} onClick={() => void review("CONFIRM")}>{reviewing ? "Saving review…" : "Confirm checked details"}</button><button className="button button-soft" type="button" disabled={reviewing} onClick={() => void review("REJECT")}>Reject document</button></div></div>}
              {selected.status === "CONFIRMED" && <div className="notice" role="status"><strong>Details confirmed by a team member.</strong><p>No business transaction was created. Continue in the relevant module to create a draft record using these checked details.</p><div className="header-actions"><Link className="button button-soft" href={selected.document_type === "SUPPLIER_INVOICE" || selected.document_type === "PURCHASE_ORDER" ? "/purchasing" : "/accounting"}>{selected.document_type === "SUPPLIER_INVOICE" || selected.document_type === "PURCHASE_ORDER" ? "Continue to purchasing" : "Continue to finance"}</Link></div></div>}
              {selected.status === "REJECTED" && <div className="notice" role="status">This file was rejected during review. No business transaction was created.</div>}
            </>}
          </div>
        </div>
      </section>
    </main>
  </AppShell>;
}
