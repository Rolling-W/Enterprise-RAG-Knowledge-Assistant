# Layout-Aware Document Parsing Evaluation

## Enterprise RAG Knowledge Assistant

**Sprint 1 – Parsing Evaluation and Prototype**  
**Owner:** Yen-Jui (Ray) Liang  
**Role:** Backend & RAG AI Engineer

---

## 1. Objective

The purpose of this evaluation was to identify a suitable layout-aware document parsing approach for the Enterprise RAG Knowledge Assistant.

The ingestion pipeline needs to support downstream retrieval and citation requirements by preserving document structure and source metadata such as:

- Page numbers
- Section and paragraph structure
- Element types
- Layout coordinates
- Table structure where possible
- Source references required for future page-level and line-level citations

The primary tools evaluated during this sprint were:

1. Unstructured
2. Marker

The initial prototype focused primarily on PDF parsing, with Markdown ingestion added using the same normalized document element model.

---

## 2. Test Document

The primary PDF used during development was the project charter for the Enterprise RAG Knowledge Assistant.

The document contains:

- 15 pages
- Headings and subsections
- Narrative paragraphs
- Tables
- Project timeline information
- Budget information
- Mixed document-control and structured content

This made it useful for evaluating both ordinary text extraction and layout-sensitive content.

---

## 3. Unstructured Evaluation

### 3.1 `fast` Strategy

Unstructured's `fast` strategy was tested first as the lightweight baseline.

Observed results:

- Parsing time: approximately 1.18 seconds
- Extracted elements: 291
- Element types included:
  - Title
  - NarrativeText
  - Text
  - ListItem
  - Footer
- Page numbers were preserved.
- Layout coordinates were available through element metadata.
- Polygon coordinates were normalized into bounding boxes in the application model.

Example normalized metadata:

```text
page_number = 4
bbox = (xmin, ymin, xmax, ymax)
element_type = NarrativeText
```

#### Advantages

- Fast execution
- Simple integration with the existing Python backend
- Element-oriented output maps naturally to the RAG ingestion pipeline
- Page metadata and coordinates are directly available
- Suitable for standard text-heavy enterprise documents

#### Limitations

- Tables are often decomposed into separate text elements.
- Row and column relationships may be lost.
- Some table cells or labels may be incorrectly classified as titles.
- Headers and footers can appear as ordinary extracted elements.
- Complex layouts require additional processing.

---

### 3.2 `hi_res` Strategy

The `hi_res` strategy was also evaluated to determine whether additional layout processing improves structured document extraction.

Observed results:

- Parsing time: approximately 29.5 seconds
- Extracted elements: 179
- Detected element types included:
  - Title
  - NarrativeText
  - Text
  - ListItem
  - Table
  - FigureCaption
- Table recognition was significantly better than the `fast` strategy.
- Page and coordinate metadata remained available.

#### Advantages

- Better awareness of tables and page layout
- More suitable for complex enterprise documents
- Produces explicit `Table` elements
- Preserves spatial metadata useful for source attribution

#### Limitations

- Significantly slower than the `fast` strategy
- Requires additional OCR and layout dependencies such as Tesseract
- Table extraction is improved but not always perfect
- Some text may still be separated from the detected table structure

#### Example Observation

The Project Budget section was detected as a structured table with `hi_res`, while the `fast` strategy largely returned separate title and text elements.

However, some values were still positioned outside the main table element, showing that layout-aware parsing does not completely eliminate reconstruction errors.

---

## 4. Marker Evaluation

Marker was evaluated as an alternative PDF-to-structured-document pipeline.

Marker successfully produced:

- Markdown output
- Structured headings
- Tables
- Page-level JSON structure
- Polygon coordinates for document blocks

The JSON representation also provided page and polygon information that could potentially be mapped into the same normalized ingestion model used by Unstructured.

### Advantages

- Strong Markdown reconstruction
- Good preservation of table structure
- Useful for documents where table reconstruction is especially important
- Structured page/block representation is available

### Limitations

- Considerably heavier setup
- Requires a separate dependency environment for the current project configuration
- Requires additional system dependencies and model downloads
- Local model assets require gigabyte-scale downloads
- More operational complexity than Unstructured for the baseline pipeline

### Table Observation

Marker produced a Markdown representation of the Project Budget table and preserved more row/column structure than Unstructured `fast`.

However, the reconstruction was still not perfect. Some budget rows or values were misplaced or omitted, so Marker should not be treated as error-free.

---

## 5. Prototype Decision

For the current prototype, **Unstructured is used as the primary PDF parsing library**.

The parser supports configurable strategies:

```python
UnstructuredPDFParser(strategy="fast")
UnstructuredPDFParser(strategy="hi_res")
```

The current baseline can therefore use `fast` during normal development while allowing `hi_res` to be selected for documents requiring additional layout analysis.

Marker remains a useful candidate for future evaluation or as a fallback for document types where table reconstruction quality is more important than parsing speed and deployment simplicity.

This decision is not intended to permanently exclude Marker. The parser architecture is designed so that alternative parsers can be incorporated later without changing the downstream chunk and retrieval models.

---

## 6. Normalized Document Model

Parsed content is converted into a normalized `DocumentElement` representation.

Each element currently preserves:

- `element_id`
- `text`
- `element_type`
- `source_file`
- `page_number`
- `sequence`
- `bbox`

This separates downstream RAG processing from the specific parsing library.

Conceptually:

```text
PDF / Markdown
      ↓
    Parser
      ↓
DocumentElement[]
      ↓
   Chunker
      ↓
DocumentChunk[]
```

---

## 7. Chunking Prototype

A section-aware chunking prototype was implemented.

The initial fixed-size approach produced chunks that could cross multiple unrelated sections. It was therefore improved to recognize numbered document headings such as:

```text
1 Project Background
1.1 Problem/Opportunity Description
2 Project Scope
2.10 Options Analysis
```

The final prototype:

- Preserves semantic section boundaries where possible
- Allows sections to span PDF pages
- Uses a configurable maximum word limit as a fallback
- Merges very short top-level heading chunks with their following subsection
- Produces deterministic chunk IDs

For the 15-page project charter:

```text
291 parsed elements
→ 18 semantic chunks
```

---

## 8. Stable Chunk IDs

Chunk IDs were changed from randomly generated UUIDs to deterministic UUID5 identifiers.

The stable identifier is derived from document and chunk characteristics such as:

- Document ID
- Source file
- Page range
- Chunk content

Repeated parsing of the same unchanged document therefore produces the same chunk identifiers.

A validation test generated the project charter chunks twice:

```text
First run chunks: 18
Second run chunks: 18
IDs identical: True
```

This is important for future indexing, retrieval fusion, document updates, and source tracking.

---

## 9. Citation Metadata Foundation

The ingestion pipeline preserves metadata required to support future citation functionality.

Each `DocumentChunk` retains the IDs of its source `DocumentElement` objects.

This provides the following traceability chain:

```text
DocumentChunk
    ↓
element_ids
    ↓
DocumentElement
    ↓
page_number
bbox
source text
```

A source-traceability test confirmed that a chunk could be mapped back to its original PDF elements and spatial coordinates.

The current sprint does **not** implement the final line-level citation UI. Instead, it establishes the metadata foundation required for future page-level and line-level citation functionality.

---

## 10. Markdown Parsing

Markdown ingestion was implemented using Unstructured.

Markdown headings and paragraphs are normalized into the same `DocumentElement` model used by the PDF pipeline.

Example:

```text
Title | Hybrid Retrieval
NarrativeText | The system combines BM25 sparse retrieval with dense vector search in Qdrant.
```

Because Markdown documents do not have native PDF-style pages or coordinates, the current prototype uses a logical page value while preserving structural elements.

More precise source-line metadata can be added in a later citation-focused sprint.

---

## 11. BM25 Baseline

A Rank-BM25 keyword retrieval baseline was implemented using `BM25Okapi`.

The baseline includes:

- Document chunk indexing
- Query tokenization
- Keyword-based ranking
- Top-K retrieval
- RBAC-compatible filtering support

Example test query:

```text
hybrid retrieval BM25 Qdrant
```

The retriever returned relevant sections including:

- Options Analysis
- Project Scope / Objectives
- Project Timeline
- Technical Features
- Deliverables

This completes the sparse retrieval baseline required as the foundation for later hybrid BM25 + dense-vector retrieval.

---

## 12. Additional Early Prototype Work

Some work for the next retrieval phase was also explored ahead of schedule.

This included proof-of-concept implementations for:

- SentenceTransformer dense embeddings
- Qdrant vector indexing
- Dense semantic retrieval
- Qdrant server-side RBAC filtering
- Reciprocal Rank Fusion (RRF)
- BM25 + dense hybrid retrieval
- Hybrid retrieval RBAC validation

These components were intentionally kept separate from the Sprint 1 deliverable and can be integrated during the appropriate future sprint.

---

## 13. Current Limitations and Future Work

The current prototype intentionally leaves several areas for future iterations:

- Improved table reconstruction
- Header/footer removal
- More general heading detection
- Markdown-specific heading hierarchy
- DOCX parsing
- Exact source-line tracking
- Parser fallback selection
- OCR handling for scanned documents
- Retrieval evaluation using Recall@K and MRR
- Cross-encoder reranking
- Production hybrid retrieval integration

These items can be addressed in later Jira tasks and sprints.

---

## 14. Sprint 1 Outcome

Sprint 1 successfully established the document ingestion and sparse retrieval foundation for the Enterprise RAG Knowledge Assistant.

Completed capabilities include:

- Layout-aware parsing technology evaluation
- PDF parsing
- Markdown parsing
- Page and layout metadata preservation
- Section-aware chunking
- Stable chunk identifiers
- Citation source traceability
- Rank-BM25 keyword retrieval baseline

The resulting architecture provides a stable foundation for the next phase of hybrid sparse + dense retrieval development.