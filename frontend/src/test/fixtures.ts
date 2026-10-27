import type {
  SearchResponse,
  TokenResponse,
  UploadResponse,
} from "../api/contracts";

// Literal API fixtures, independent of client adapters and mock construction.
export const tokenFixture: TokenResponse = {
  access_token: "signed-token",
  token_type: "bearer",
  expires_in: 3600,
  user: {
    user_id: "user_abc123",
    username: "manager@enterprise.local",
    role: "Department Manager",
    department: "General",
    clearance: 2,
  },
};
export const searchFixture: SearchResponse = {
  query: "employee benefits",
  search_mode: "hybrid",
  total: 1,
  request_id: "req_abc123",
  results: [
    {
      document_id: "doc_001",
      chunk_id: "chunk_001",
      title: "Employee_Handbook.pdf",
      score: 0.92,
      content: "Employees receive 20 days of annual leave.",
      content_type: "application/pdf",
      department_id: "HR",
      clearance_level: 1,
      citation: { page: 12, line_start: 45, line_end: 49 },
    },
  ],
};
export const uploadFixture: UploadResponse = {
  document_id: "doc_new",
  filename: "policy.md",
  content_type: "text/markdown",
  size_bytes: 6,
  status: "queued",
  message: "Document queued for General with clearance 2",
};
