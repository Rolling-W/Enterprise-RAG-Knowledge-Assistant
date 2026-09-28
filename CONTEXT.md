# Domain Context

## Terms

### User

A person authenticated by the identity provider. A User receives a signed
clearance token and is assigned exactly one application role for a session.

### Role

The coarse-grained set of actions a User may perform. The initial roles are
Executive, Department Manager, and Standard Staff.

### Clearance

The numeric sensitivity level carried by a User's token: 3 for Executive, 2
for Department Manager, and 1 for Standard Staff. A document is returned only
when the User's clearance satisfies the document policy.

### Permission

An action granted by a Role, such as `document:read` or `document:upload`.
Permissions control operations; clearance controls the sensitivity of data
visible to a User.

### Document

An ingested enterprise file with an owning department and a minimum clearance
policy. The upload actor's role must come from the authenticated User, never
from an untrusted form field.

### Clearance token

A short-lived, signed JWT containing the User identity, Role, department,
clearance, permissions, issuer, timestamps, and a unique token identifier.
Clients present it as `Authorization: Bearer <token>`; clients do not edit
authorization claims.

## Invariants

- Every protected search or upload request has a valid, unexpired token.
- A Standard Staff User can read only documents permitted at clearance 1 and
  cannot upload or manage documents.
- A Department Manager can read and upload documents for the assigned
  department but cannot manage global access policy.
- An Executive can read, upload, and manage documents across departments.
- Role and clearance are server-issued claims and are not accepted from
  request bodies or multipart form fields.
