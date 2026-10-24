import { getCachedSession, restoreSession, type WorkspaceContext } from "./api";

export type IntelligenceDocumentType = "SUPPLIER_INVOICE" | "EXPENSE_RECEIPT" | "CUSTOMER_INVOICE" | "PURCHASE_ORDER" | "OTHER";
export type IntelligenceDocumentStatus = "NEEDS_REVIEW" | "CONFIRMED" | "REJECTED";
export type CandidateField = { value: string | null; confidence: number; evidence: string | null };
export type DocumentCandidate = {
  schema_version: string;
  document_type: IntelligenceDocumentType;
  fields: Record<string, CandidateField>;
  warnings: string[];
  text_character_count?: number;
};
export type IntelligenceDocument = {
  id: string;
  branch_id: string;
  document_type: IntelligenceDocumentType;
  status: IntelligenceDocumentStatus;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  content_sha256: string;
  extraction_status: "SUCCEEDED" | "PARTIAL" | "UNAVAILABLE";
  extraction_method: "PDF_TEXT_LAYER" | "PDF_RENDERED_OCR" | "TESSERACT_OCR" | "UNAVAILABLE";
  candidate_fields: DocumentCandidate;
  confirmed_fields: Record<string, string | null> | null;
  review_reason: string | null;
  created_at: string;
  updated_at: string;
  reviewed_at: string | null;
  can_review: boolean;
  original_file_available: boolean;
  extracted_text_preview?: string;
  duplicate?: boolean;
  transaction_created?: false;
  next_step?: string;
  message?: string;
};
type DocumentList = { items: IntelligenceDocument[]; count: number };

async function activeSession() {
  const session = getCachedSession() || await restoreSession();
  if (!session?.access_token) throw new Error("Your sign-in has expired. Sign in again to continue.");
  return session;
}

async function requestJson<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const session = await activeSession();
  const headers = new Headers(init.headers || {});
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Bearer ${session.access_token}`);
  const response = await fetch(`/api/lexa${path}`, { ...init, headers, cache: "no-store", credentials: "include" });
  if (response.status === 401 && retry) {
    await restoreSession();
    return requestJson<T>(path, init, false);
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let message = "LEXA could not complete that request. Please try again.";
    if (payload && typeof payload === "object" && "detail" in payload) {
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) message = detail;
      else if (detail && typeof detail === "object" && "message" in detail && typeof (detail as { message?: unknown }).message === "string") {
        message = String((detail as { message: string }).message);
      }
    }
    throw new Error(message);
  }
  return payload as T;
}

export async function getIntelligenceDocuments(options: { branchId?: string; status?: IntelligenceDocumentStatus; limit?: number } = {}) {
  const search = new URLSearchParams({ limit: String(Math.min(100, Math.max(1, options.limit || 30))) });
  if (options.branchId) search.set("branch_id", options.branchId);
  if (options.status) search.set("status", options.status);
  return requestJson<DocumentList>(`/api/v1/intelligence/documents?${search.toString()}`);
}

export async function getIntelligenceDocument(id: string) {
  return requestJson<IntelligenceDocument>(`/api/v1/intelligence/documents/${encodeURIComponent(id)}`);
}

export async function uploadIntelligenceDocument(file: File, documentType: IntelligenceDocumentType, branchId: string) {
  if (file.size <= 0) throw new Error("The selected file is empty.");
  if (file.size > 10 * 1024 * 1024) throw new Error("Choose a file no larger than 10 MB.");
  if (!new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]).has(file.type)) {
    throw new Error("Choose a PDF, JPG, PNG or WebP file.");
  }
  const session = await activeSession();
  const response = await fetch("/api/lexa/api/v1/intelligence/documents/intake", {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${session.access_token}`,
      "Content-Type": file.type,
      "X-Document-Type": documentType,
      "X-Branch-ID": branchId,
      "X-Document-Filename": encodeURIComponent(file.name),
    },
    body: file,
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? (payload as { detail?: unknown }).detail : null;
    const message = detail && typeof detail === "object" && "message" in detail ? String((detail as { message?: unknown }).message) : typeof detail === "string" ? detail : "LEXA couldn't receive this document. Check the file and try again.";
    throw new Error(message);
  }
  return payload as IntelligenceDocument;
}

export async function reviewIntelligenceDocument(id: string, payload: {
  action: "CONFIRM" | "REJECT";
  confirmed_fields?: Record<string, string | null>;
  reason?: string;
}) {
  return requestJson<IntelligenceDocument>(`/api/v1/intelligence/documents/${encodeURIComponent(id)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function downloadIntelligenceDocument(item: Pick<IntelligenceDocument, "id" | "original_filename">) {
  const session = await activeSession();
  const response = await fetch(`/api/lexa/api/v1/intelligence/documents/${encodeURIComponent(item.id)}/file`, {
    credentials: "include", cache: "no-store",
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  if (!response.ok) throw new Error("LEXA couldn't retrieve the original file.");
  const fileUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = fileUrl;
  anchor.download = item.original_filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(fileUrl);
}

export type { WorkspaceContext };
