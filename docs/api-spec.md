# API Specification

## Base URL
- Local development: `http://localhost:8000`

## Health
### GET /health
Returns backend health status.

Response:
```json
{
  "status": "healthy",
  "database": "Qdrant Ready"
}
```

## Search Demo
### POST /api/v1/search
Search for relevant enterprise knowledge snippets.

Query Parameters:
- `query` (string, required): user search text
- `user_role` (string, optional): role used for access filtering

Example request:
```http
POST /api/v1/search?query=employee%20benefits&user_role=Manager
```

Example response:
```json
{
  "query": "employee benefits",
  "user_role": "Manager",
  "results": [
    {
      "doc_id": "doc_001",
      "title": "Employee_Handbook.pdf",
      "score": 0.92,
      "content": "Sample retrieved chunk text...",
      "citation": {
        "page": 12,
        "line": 45
      }
    }
  ]
}
```

## Notes
- This scaffold is intentionally lightweight and designed for Sprint 1/2 demonstration.
- Actual authentication, retrieval, and RBAC enforcement will be implemented in future iterations.
