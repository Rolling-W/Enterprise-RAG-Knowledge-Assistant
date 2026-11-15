# Enterprise RAG Knowledge Assistant

This context defines the project's identity, document-access, and retrieval language so API, backend, frontend, and acceptance work use the same concepts.

## Identity and access

**User**:
A person authenticated to the application with one product role and a user clearance level.
_Avoid_: account as a synonym for an authenticated person

**Product role**:
The user's operation class: `admin`, `staff`, or `user`.
_Avoid_: display title as authorization, client role

**User clearance**:
The maximum document sensitivity level the user may read, derived from the authenticated role.
_Avoid_: document clearance, user permission level

**Document permission level**:
The sensitivity classification assigned to one document, independent of its uploader and department.
_Avoid_: document clearance

**Department scope**:
The organizational audience assigned to a document and checked separately from its permission level.
_Avoid_: sensitivity level, clearance

**Operation permission**:
An action granted to a product role, such as `document:read` or `document:upload`.
_Avoid_: clearance, permission level

**Clearance token**:
The authenticated credential carrying server-issued identity and authorization claims.
_Avoid_: client-provided role or access claims

## Knowledge sources

**Document**:
An ingested source with its own permission level and department scope; indexed chunks inherit both access attributes.
_Avoid_: chunk as the access-control owner

**Citation**:
A reference from an answer to a chunk and its source location, subject to a fresh access check when displayed.
_Avoid_: proof of current access
