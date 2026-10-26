import type { KnowledgeDocument } from "../types";

export const seedDocuments: KnowledgeDocument[] = [
  {
    document_id: "doc-handbook",
    filename: "Employee_Handbook.pdf",
    format: "PDF",
    size_bytes: 1248000,
    department: "Global",
    min_clearance: 1,
    uploaded_at: "2026-09-29T14:00:00Z",
    status: "ready",
    page_count: 24,
    description: "Time off, employee benefits, and workplace policies.",
    preview:
      "Employee Handbook\n\nTime off and benefits\n\nFull-time employees receive 20 days of paid annual leave per calendar year. Leave requests should be submitted through the HR portal at least five business days in advance.\n\nEmployees are eligible for health coverage from their first day of employment. The company also provides a professional development allowance of $1,000 per year.",
  },
  {
    document_id: "doc-remote",
    filename: "Remote_Work_Policy.md",
    format: "Markdown",
    size_bytes: 8400,
    department: "Global",
    min_clearance: 1,
    uploaded_at: "2026-09-28T10:30:00Z",
    status: "ready",
    description: "Hybrid schedules, collaboration, and remote access.",
    preview:
      "Remote Work Policy\n\nHybrid schedule\n\nEmployees may work remotely up to three days per week, subject to their manager’s approval. Teams agree on shared office days to support collaboration.\n\nWorking securely\n\nUse the company VPN and a managed device to access internal systems. Keep confidential documents in approved company storage.",
  },
  {
    document_id: "doc-onboarding",
    filename: "Onboarding_Guide.pdf",
    format: "PDF",
    size_bytes: 682000,
    department: "General",
    min_clearance: 1,
    uploaded_at: "2026-09-27T16:00:00Z",
    status: "ready",
    page_count: 12,
    description: "A practical guide to your first week at the company.",
    preview:
      "Onboarding Guide\n\nYour first week\n\nOn day one, activate your company account and enroll in multi-factor authentication. Complete your HR profile and review the employee handbook.\n\nDuring the first week, finish security awareness training, meet your team, and agree on initial goals with your manager.",
  },
  {
    document_id: "doc-manager",
    filename: "Manager_Playbook.pdf",
    format: "PDF",
    size_bytes: 945000,
    department: "General",
    min_clearance: 2,
    uploaded_at: "2026-09-26T12:00:00Z",
    status: "ready",
    page_count: 18,
    description: "Team planning, approvals, and performance reviews.",
    preview:
      "Manager Playbook\n\nTeam management\n\nManagers hold monthly one-to-one meetings with each team member. Quarterly reviews should document agreed goals and development needs.\n\nReview leave requests against team coverage before approving them. Escalate unresolved staffing constraints to the department head.",
  },
  {
    document_id: "doc-strategy",
    filename: "Leadership_Strategy.pdf",
    format: "PDF",
    size_bytes: 1720000,
    department: "Executive",
    min_clearance: 3,
    uploaded_at: "2026-09-25T09:00:00Z",
    status: "ready",
    page_count: 16,
    description: "Leadership priorities and quarterly planning.",
    preview:
      "Leadership Strategy\n\nQuarterly priorities\n\nThe leadership team reviews strategic priorities at the beginning of each quarter. Department proposals should include a measurable outcome, a delivery owner, and a resource estimate.",
  },
];
