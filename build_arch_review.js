'use strict';
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat, ExternalHyperlink
} = require('/sessions/upbeat-cool-albattani/mnt/outputs/docx_env/lib/node_modules/docx');

// ── Colour palette ──────────────────────────────────────────────────────────
const C = {
  red:    'C0392B', redLight:  'FDEDEC',
  amber:  'E67E22', amberLight:'FEF9E7',
  green:  '27AE60', greenLight:'EAFAF1',
  blue:   '2471A3', blueLight: 'EBF5FB',
  navy:   '1B2631',
  grey:   '5D6D7E', greyLight: 'F2F3F4',
  white:  'FFFFFF',
  black:  '000000',
};

const B = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: B, bottom: B, left: B, right: B };
const noBorder = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

// ── Typography helpers ───────────────────────────────────────────────────────
const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  pageBreakBefore: true,
  spacing: { before: 0, after: 200 },
  children: [new TextRun({ text, font: 'Arial', size: 36, bold: true, color: C.navy })]
});

const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 300, after: 120 },
  children: [new TextRun({ text, font: 'Arial', size: 28, bold: true, color: C.blue })]
});

const h3 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_3,
  spacing: { before: 200, after: 100 },
  children: [new TextRun({ text, font: 'Arial', size: 24, bold: true, color: C.grey })]
});

const p = (text, opts = {}) => new Paragraph({
  spacing: { before: 80, after: 120 },
  children: [new TextRun({ text, font: 'Arial', size: 22, color: C.black, ...opts })]
});

const pBold = (text, color = C.black) => p(text, { bold: true, color });

const bullet = (text, ref = 'bullets') => new Paragraph({
  numbering: { reference: ref, level: 0 },
  spacing: { before: 40, after: 40 },
  children: [new TextRun({ text, font: 'Arial', size: 22 })]
});

const gap = () => new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun('')] });

const divider = () => new Paragraph({
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC', space: 1 } },
  spacing: { before: 160, after: 160 },
  children: [new TextRun('')]
});

// ── Cell helper ──────────────────────────────────────────────────────────────
const cell = (content, width, fill = C.white, bold = false, color = C.black, align = AlignmentType.LEFT) => {
  const runs = Array.isArray(content) ? content : [new TextRun({ text: String(content), font: 'Arial', size: 20, bold, color })];
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 140, right: 140 },
    children: [new Paragraph({ alignment: align, children: runs })]
  });
};

const hCell = (text, width, fill = C.navy) =>
  cell(text, width, fill, true, C.white, AlignmentType.LEFT);

// ── Badge cell (colour-coded severity) ──────────────────────────────────────
const badgeCell = (text, width) => {
  const map = {
    CRITICAL: { fill: C.redLight, color: C.red },
    HIGH:     { fill: C.amberLight, color: C.amber },
    MEDIUM:   { fill: C.blueLight, color: C.blue },
    LOW:      { fill: C.greyLight, color: C.grey },
    GOOD:     { fill: C.greenLight, color: C.green },
  };
  const s = map[text] || { fill: C.greyLight, color: C.grey };
  return cell([new TextRun({ text, font: 'Arial', size: 18, bold: true, color: s.color })], width, s.fill);
};

// ── Callout box ──────────────────────────────────────────────────────────────
const callout = (label, text, fill, labelColor) => new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [1200, 8160],
  rows: [new TableRow({ children: [
    new TableCell({
      borders: noBorders,
      width: { size: 1200, type: WidthType.DXA },
      shading: { fill, type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: label, font: 'Arial', size: 20, bold: true, color: labelColor })] })]
    }),
    new TableCell({
      borders: noBorders,
      width: { size: 8160, type: WidthType.DXA },
      shading: { fill, type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 120, right: 140 },
      children: [new Paragraph({ children: [new TextRun({ text, font: 'Arial', size: 20, color: C.black })] })]
    })
  ]})]
});

// ────────────────────────────────────────────────────────────────────────────
//  DOCUMENT BUILD
// ────────────────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: 'numbers', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Arial', color: C.navy },
        paragraph: { spacing: { before: 0, after: 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: C.blue },
        paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: C.grey },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ]
  },
  sections: [
    // ── COVER PAGE ────────────────────────────────────────────────────────────
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      children: [
        new Paragraph({ spacing: { before: 2400, after: 0 }, children: [] }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 200 },
          children: [new TextRun({ text: 'ORDER ASSURANCE', font: 'Arial', size: 72, bold: true, color: C.navy })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 600 },
          children: [new TextRun({ text: 'Architecture Review Report', font: 'Arial', size: 48, color: C.blue })]
        }),
        new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: C.blue, space: 1 } },
          spacing: { before: 0, after: 400 },
          children: [new TextRun('')]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 400, after: 80 },
          children: [new TextRun({ text: 'Unfiltered. Evidence-Based. No Sugarcoating.', font: 'Arial', size: 28, italics: true, color: C.grey })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 80, after: 80 },
          children: [new TextRun({ text: 'Three-Agent Review Team | June 2026', font: 'Arial', size: 24, color: C.grey })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 80, after: 80 },
          children: [new TextRun({ text: 'Full codebase read: 15 files, ~5,000 lines of production code', font: 'Arial', size: 22, color: C.grey })]
        }),
        new Paragraph({ spacing: { before: 1200, after: 0 }, children: [] }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 80 },
          children: [new TextRun({ text: 'Scope', font: 'Arial', size: 22, bold: true, color: C.navy })]
        }),
        new Table({
          width: { size: 7200, type: WidthType.DXA },
          columnWidths: [3600, 3600],
          rows: [
            new TableRow({ children: [
              cell('Backend (FastAPI + SQLite)', 3600, C.blueLight),
              cell('Frontend (React 18 + Vite)', 3600, C.blueLight),
            ]}),
            new TableRow({ children: [
              cell('Extraction Pipeline (OCR + Parser)', 3600, C.greyLight),
              cell('Verification Engine', 3600, C.greyLight),
            ]}),
            new TableRow({ children: [
              cell('Migration Runner', 3600, C.blueLight),
              cell('Export Service (XLSX)', 3600, C.blueLight),
            ]}),
          ]
        }),
      ]
    },

    // ── MAIN BODY ─────────────────────────────────────────────────────────────
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
        }
      },
      headers: {
        default: new Header({ children: [new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.blue, space: 1 } },
          children: [
            new TextRun({ text: 'ORDER ASSURANCE — Architecture Review  ', font: 'Arial', size: 18, color: C.grey }),
            new TextRun({ text: 'June 2026', font: 'Arial', size: 18, color: C.blue }),
          ]
        })] })
      },
      footers: {
        default: new Footer({ children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC', space: 1 } },
          children: [
            new TextRun({ text: 'Page ', font: 'Arial', size: 18, color: C.grey }),
            new TextRun({ font: 'Arial', size: 18, color: C.grey, children: [PageNumber.CURRENT] }),
          ]
        })] })
      },
      children: [

        // ── §1 EXECUTIVE SUMMARY ────────────────────────────────────────────
        h1('1. Executive Summary'),
        p('Order Assurance is a self-hosted Intelligent Document Processing (IDP) platform targeting Indian logistics procurement. Its core value proposition is automated five-document bundle verification — Customer PO → Company PO → Vendor Invoice → Delivery Challan → Company Invoice — with extraction, cross-matching, and XLSX audit export.'),
        gap(),
        p('The platform is functionally working. Real-document validation results show 24/24 fields extracted from Panimalar, 27/28 from AMC. That is a legitimate achievement for a bespoke, single-team build.'),
        gap(),
        p('However, the architecture has accumulated a set of structural decisions that will become blocking constraints before the platform processes more than 50 concurrent bundles, is deployed beyond a single developer machine, or needs to be maintained by anyone other than its original author. This report names those decisions clearly, without softening.'),
        gap(),
        // summary table
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [4000, 2000, 3360],
          rows: [
            new TableRow({ children: [hCell('Dimension', 4000), hCell('Rating', 2000), hCell('Short Verdict', 3360)] }),
            new TableRow({ children: [cell('Extraction accuracy (current docs)', 4000), badgeCell('GOOD', 2000), cell('24–27/28 fields extracted. Solid.', 3360)] }),
            new TableRow({ children: [cell('Extraction pipeline architecture', 4000), badgeCell('HIGH', 2000), cell('1,585-line God object. Untestable in parts.', 3360)] }),
            new TableRow({ children: [cell('Async & concurrency model', 4000), badgeCell('CRITICAL', 2000), cell('Threading queue blocks async event loop.', 3360)] }),
            new TableRow({ children: [cell('Database choice & schema', 4000), badgeCell('CRITICAL', 2000), cell('SQLite + JSON blobs. Not production-safe.', 3360)] }),
            new TableRow({ children: [cell('Verification engine', 4000), badgeCell('HIGH', 2000), cell('Header-only. Tolerance hard-coded. Single DC.', 3360)] }),
            new TableRow({ children: [cell('Security & access control', 4000), badgeCell('CRITICAL', 2000), cell('Zero authentication. Zero.', 3360)] }),
            new TableRow({ children: [cell('Multi-tenancy', 4000), badgeCell('CRITICAL', 2000), cell('No tenant_id on any model. Schema rewrite needed.', 3360)] }),
            new TableRow({ children: [cell('Code maintainability', 4000), badgeCell('HIGH', 2000), cell('Three ~1,200-line files. High cognitive load.', 3360)] }),
            new TableRow({ children: [cell('Frontend quality', 4000), badgeCell('GOOD', 2000), cell('ExtractionActivityContext well-designed.', 3360)] }),
            new TableRow({ children: [cell('Test coverage', 4000), badgeCell('MEDIUM', 2000), cell('Backend tests exist. Frontend minimal.', 3360)] }),
            new TableRow({ children: [cell('Deployment readiness', 4000), badgeCell('HIGH', 2000), cell('CORS hardcoded. Dev router always on. No migrations in prod.', 3360)] }),
          ]
        }),

        // ── §2 CODEBASE ANATOMY ─────────────────────────────────────────────
        h1('2. Codebase Anatomy'),
        h2('2.1 File Size Distribution'),
        p('The complexity is concentrated in three files. Everything else is reasonably sized.'),
        gap(),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [4200, 1800, 3360],
          rows: [
            new TableRow({ children: [hCell('File', 4200), hCell('Lines', 1800), hCell('Concern', 3360)] }),
            new TableRow({ children: [cell('services/extraction_service.py', 4200), cell('1,585', 1800, C.redLight), cell('God object — all OCR logic in one file', 3360, C.red)] }),
            new TableRow({ children: [cell('services/extraction/structured_text_parser.py', 4200), cell('1,215', 1800, C.redLight), cell('Pure regex for 5 doc types, no ML layer', 3360, C.red)] }),
            new TableRow({ children: [cell('services/order_bundle_verifier.py', 4200), cell('467', 1800, C.amberLight), cell('Acceptable but hard-coded tolerances', 3360)] }),
            new TableRow({ children: [cell('services/export_service.py', 4200), cell('~400', 1800, C.greyLight), cell('9 XLSX sheets, manageable', 3360)] }),
            new TableRow({ children: [cell('api/routes/bundles.py', 4200), cell('218', 1800, C.greyLight), cell('O(N) verification bug lives here', 3360)] }),
            new TableRow({ children: [cell('services/document_normalizer.py', 4200), cell('179', 1800, C.greyLight), cell('Clean alias resolution layer', 3360)] }),
            new TableRow({ children: [cell('migrations/runner.py', 4200), cell('147', 1800, C.greyLight), cell('Works but splits SQL on ";" — dangerous for triggers', 3360)] }),
            new TableRow({ children: [cell('api/routes/documents.py', 4200), cell('233', 1800, C.greyLight), cell('PDF preview, extract, patch — well structured', 3360)] }),
            new TableRow({ children: [cell('config.py', 4200), cell('81', 1800, C.greyLight), cell('50+ settings, frozen dataclass — good pattern', 3360)] }),
          ]
        }),

        h2('2.2 Data Flow (as built)'),
        p('PDF Upload → save_upload_file() → DocumentRecord(status=UPLOADED) → POST /extract → extraction_service.extract_document() [1,585 lines] → {digital_text_extractor | paddleocr_gpu | glm_ocr} → structured_text_parser.parse_structured_text() [1,215 lines] → document_normalizer.normalize_document() → DocumentMetadataRecord.extracted_data JSON blob → verification_summary_service.build_verification_summary() → order_bundle_verifier.verify_order_bundle() → BundleStatus → XLSX export.'),
        gap(),
        callout('Note', 'Every step from OCR call to DB write happens synchronously inside a single FastAPI route handler, inside a threading.Condition lock. The FastAPI async event loop is completely blocked during GPU inference.', C.redLight, C.red),

        // ── §3 WHAT IS GENUINELY GOOD ───────────────────────────────────────
        h1('3. What Is Genuinely Good'),
        p('This section is not padding. These are real architectural decisions done right.'),

        h2('3.1 The Verification Engine Is Isolated'),
        p('order_bundle_verifier.py (467 lines) contains zero database calls, zero I/O, zero side effects. It takes a dict of normalized documents and returns a result dict. This is the correct design for a domain rule engine. It is fully unit-testable in isolation. The status priority ordering (PASS < PARTIAL_PASS < REVIEW_REQUIRED < MISSING_DOCUMENTS < BLOCKED < MISMATCH) is explicit and deterministic.'),

        h2('3.2 Repository Pattern Is Clean'),
        p('BundleRepository, DocumentRepository, AuditRepository, ReferenceIndexRepository each wrap their ORM model with typed methods. list(), get(), create(), delete() are correctly separated from the route layer. selectinload() is used correctly for eager loading. This is the right pattern.'),

        h2('3.3 Settings as Frozen Dataclass'),
        p('config.py uses @dataclass(frozen=True) with a global singleton, plus replace_settings() for test monkey-patching. 50+ settings with sensible env-var defaults. This is a pragmatic, testable configuration pattern that avoids both tight coupling and the fragility of mutable globals.'),

        h2('3.4 Audit Trail on Every Operation'),
        p('AuditService records bundle_created, document_uploaded, extraction_completed, extraction_failed, manual_metadata_patch, document_deleted, export_generated. Every mutation is audited. The XLSX export includes an Audit Trail sheet. For a compliance-sensitive logistics document platform, this is the right default.'),

        h2('3.5 Document Normalizer Handles Alias Ambiguity'),
        p('document_normalizer.py defines FIELD_ALIASES per document type with candidate lists. When a vendor calls a field "supplier_name" instead of "vendor_name", normalization resolves it transparently. The NormalizedDocument dataclass carries raw_document_type alongside normalized_type, preserving provenance. This is a deliberate and correct design choice.'),

        h2('3.6 Frontend ExtractionActivityContext'),
        p('The React ExtractionActivityContext is well-designed: it combines local optimistic state (immediate UI feedback) with 3-second backend polling (ground truth), provides a unified isExtracting() predicate, and cleans up correctly on unmount. The banner renders elapsed time. This pattern is production-quality.'),

        h2('3.7 Feature Flags for Incomplete Features'),
        p('MODEL_LAYER2_ENABLED=false and EVIDENCE_CAPTURE_ENABLED=false are shipped as explicit flags. Disabled paths do not run. This is correct — shipping disabled code with a flag is safer than deleting and re-adding later. The flag names are self-describing.'),

        h2('3.8 OCR Retry With Rotation'),
        p('_retry_sideways_vendor_invoice_ocr() retries extraction at 0°, 90°, and 270° when key fields are missing. This handles physically rotated invoice scans — a real-world problem in Indian logistics documents — without user intervention. Pragmatic and correct.'),

        // ── §4 WHAT IS BROKEN OR DANGEROUS ─────────────────────────────────
        h1('4. What Is Broken or Dangerous'),
        callout('CRITICAL', 'The following problems are not theoretical. They will cause failures in production conditions. They are listed in order of blast radius.', C.redLight, C.red),

        h2('4.1 [CRITICAL] Zero Authentication'),
        p('There is no authentication middleware, no JWT, no session, no API key, no OAuth. Any process that can reach port 8100 has full read/write/delete access to every bundle, every document, every extraction result, and every audit log. The CORS restriction (localhost:5180 only) is not a security boundary — it is a browser-side hint that any non-browser HTTP client ignores entirely.'),
        gap(),
        callout('Impact', 'One curl command from any machine with network access to the server deletes all data permanently. In a logistics procurement context, this is a regulatory risk, not just a security gap.', C.redLight, C.red),

        h2('4.2 [CRITICAL] SQLite in Production'),
        p('SQLite is configured with check_same_thread=False and a 60-second timeout. check_same_thread=False does not make SQLite thread-safe — it disables the guard that tells you when you are using it unsafely. SQLite has a single writer lock. When OCR runs (which can take 30-90 seconds per document), any other write — bundle creation, document upload, audit event — blocks until the lock is released or the 60-second timeout fires, returning a "database is locked" 503 to the user. There is explicit handling for this case in documents.py line 143-147. The workaround acknowledges the problem but does not solve it.'),

        h2('4.3 [CRITICAL] In-Process Threading Queue Blocks the Event Loop'),
        p('extraction_queue.py uses threading.Condition + collections.deque to serialize OCR jobs. The OCR call (PaddleOCR GPU or GLM via Ollama) is synchronous and can run for 30-90 seconds. This call is made inside a FastAPI route handler. FastAPI is an async framework built on asyncio. A synchronous 90-second call inside a route handler blocks the entire event loop — no other requests can be processed during that window. The threading queue prevents two OCR jobs from running simultaneously, but it does not prevent the event loop from stalling. Every other API call — bundle list, document preview, health check — is frozen while OCR runs.'),
        gap(),
        callout('Fix Required', 'OCR must be moved to an external worker process (Celery + Redis). The route handler should enqueue the job and return 202 Accepted immediately. The event loop must never block.', C.amberLight, C.amber),

        h2('4.4 [CRITICAL] O(N) Verification on Bundle List'),
        p('list_bundles() in api/routes/bundles.py calls build_verification_summary(db, bundle.id) for every bundle in the result set. build_verification_summary() fetches all documents for the bundle, calls normalize_document() on each, calls verify_order_bundle(), and builds a full verification result dict. At 10 bundles: 10 full verification computations per page load. At 100 bundles: 100. At 500 bundles: the request will time out. There is no pagination, no caching, no incremental update. The bundle record already has status, customer_delivery_status, vendor_procurement_status columns — but they are not used as the authoritative source for list rendering. Instead, live computation overwrites them on every request.'),

        h2('4.5 [HIGH] Extraction Service Is a 1,585-Line God Object'),
        p('extraction_service.py contains: route selection logic, OCR provider dispatch, PaddleOCR invocation, GLM invocation, fallback logic, header OCR crop logic, rotation retry logic, evidence capture, field merging, diagnostics building, and error handling for each path. These are at least six distinct responsibilities in one file. The diagnostics dict is mutated throughout — tracking its state at any point in the function requires reading 500+ lines of context. Adding a new OCR provider or document type requires modifying this file in multiple places, risking regressions in existing paths.'),

        h2('4.6 [HIGH] structured_text_parser.py Is 1,215 Lines of Pure Regex'),
        p('The parser handles five document types (CUSTOMER_PO, VENDOR_INVOICE, COMPANY_INVOICE, COMPANY_DC, COMPANY_PO) with regex patterns per field per document type. There is no statistical model, no learned weights, no confidence calibration from training data. When a vendor uses a non-standard field label — "Our Ref" instead of "PO Reference", or "Net Payable" instead of "Invoice Total" — the regex fails silently and the field is missing. The fallback is GLM OCR, which adds 60-90 seconds per document. The parser and the normalizer maintain separate alias maps with different semantics, creating two places to update when adding a new field variant.'),

        h2('4.7 [HIGH] Header-Level Matching Only'),
        p('order_bundle_verifier.py performs matching at the document header level only: total amounts, PO numbers, names. Line items are not extracted, not stored, and not compared. Industry-standard IDP platforms (HighRadius, Rillion, Stampli) achieve 90%+ autonomous match rates through line-item matching — price per unit, quantity per line, HSN codes per line, GST treatment per line. Header-level matching misses all partial delivery scenarios, line-level pricing errors, and HSN mismatches that are the primary source of disputed invoices in Indian logistics.'),
        gap(),
        callout('Industry context', 'HighRadius consistently delivers 90% autonomous match rates via line-item matching. Order Assurance header matching will flag bundles as PASS when line items are wrong, giving false confidence.', C.amberLight, C.amber),

        h2('4.8 [HIGH] Hard-Coded Absolute Tolerance'),
        p('The verifier uses abs(left_value - right_value) <= 2 for amount comparisons. This means: a Rs 1,000 bundle tolerates Rs 2 variance (0.2%) but a Rs 10,00,000 bundle also tolerates Rs 2 (0.0002%). At large invoice values — which are the high-value, high-risk transactions this platform is designed to protect — the tolerance is effectively zero and will generate false MISMATCH flags for legitimate rounding differences. Tolerance must be percentage-based and configurable per document type.'),

        h2('4.9 [HIGH] No Tenant Isolation'),
        p('No model — OrderBundleRecord, DocumentRecord, DocumentMetadataRecord, AuditEventRecord, ReferenceIndexRecord — has a tenant_id, org_id, or user_id column. Adding multi-tenancy now requires: schema migration on every table, index additions, query changes in every repository, row-level filtering in every route. The longer this waits, the more expensive it becomes. This is a structural constraint on the platform\'s commercial viability.'),

        h2('4.10 [MEDIUM] JSON Blob for All Extracted Data'),
        p('DocumentMetadataRecord.extracted_data is a single JSON column containing all extracted fields. This means: no SQL query can filter by vendor_invoice_no, no index can accelerate "find all bundles where invoice_total > 100000", no schema enforcement prevents storing garbage in a typed field. The diagnostics column is also JSON and can grow to hundreds of KB per document. There is no field-level queryability on the most important data the platform holds.'),

        h2('4.11 [MEDIUM] Migration Runner Has Dangerous SQL Splitting'),
        p('migrations/runner.py splits SQL files on semicolons: sql.split(";"). This is incorrect for any SQL that contains a semicolon inside a string literal, trigger body, or stored procedure. It also applies backward-compat column additions via runtime ALTER TABLE inside _ensure_reference_provenance_columns(), which is a code-based schema migration that bypasses the migration file tracking system entirely. If a column is added this way and also added in a later migration file, the ALTER TABLE will fail on a fresh database.'),

        h2('4.12 [MEDIUM] last_error Truncated at 500 Characters'),
        p('DocumentRecord.last_error is defined as String(500). PaddleOCR and GLM error messages — especially GPU OOM errors and Ollama timeout tracebacks — routinely exceed 500 characters. The truncated error is then the only diagnostic available when debugging extraction failures, because the full traceback is not stored anywhere else.'),

        h2('4.13 [MEDIUM] Dev Router Always Included'),
        p('main.py includes the dev_router unconditionally — it is not gated on APP_ENV. Only init_db() is gated. This means development endpoints (whatever dev_router exposes) are live in any deployment. If those endpoints expose reset functionality or bypass validation, they are live in production.'),

        h2('4.14 [LOW] Only dcs[0] Used in Multi-DC Bundles'),
        p('order_bundle_verifier.py assigns primary_dc = dcs[0] and uses only that delivery challan for all matching. If a bundle has two DCs (split delivery), only the first is verified. The second DC is silently ignored. No warning is emitted. The bundle may be marked PASS while the second delivery is unverified.'),

        h2('4.15 [LOW] SequenceMatcher for Name Matching'),
        p('Name matching uses difflib.SequenceMatcher with ratio >= 0.82. SequenceMatcher is character-level. It will fail on "ABC Electronics Private Limited" vs "ABC Electronics Pvt Ltd" (ratio ~0.75 — MISMATCH) while accepting "Acme Corp" vs "Acme Corp." (ratio 0.99). Indian company names with Pvt/Private/Ltd/Limited variants will generate false mismatches. A normalised token-set comparison would be more appropriate.'),

        // ── §5 WHAT NEEDS TO CHANGE ─────────────────────────────────────────
        h1('5. What Needs to Change — Prioritised Roadmap'),
        h2('Priority 1: Stop the Bleeding (Weeks 1–4)'),
        p('These are pre-condition fixes before any new feature work.'),

        h3('P1-A: Add Authentication'),
        bullet('Add fastapi-users or a simple JWT middleware (python-jose + passlib)'),
        bullet('Every route behind auth. Health endpoint exempt.'),
        bullet('One admin user to start. Role expansion later.'),
        bullet('This is a single afternoon of work. There is no excuse for its absence.'),

        gap(),
        h3('P1-B: Fix the O(N) List Query'),
        bullet('Remove build_verification_summary() from list_bundles().'),
        bullet('The bundle record already has status, customer_delivery_status, vendor_procurement_status. Use them.'),
        bullet('Call sync_bundle_status_from_verification() on every write (extract, patch, delete) — which is already done in most places.'),
        bullet('The list endpoint becomes a simple DB read: zero verification computation.'),

        gap(),
        h3('P1-C: Gate the Dev Router'),
        bullet('Wrap app.include_router(dev_router, ...) with: if settings.enable_dev_tools and settings.app_env == "development"'),
        bullet('One line change. Do it now.'),

        gap(),
        h3('P1-D: Fix last_error Truncation'),
        bullet('Change DocumentRecord.last_error to Text (unlimited) in SQLAlchemy model.'),
        bullet('Add a migration to ALTER COLUMN or recreate the column.'),

        h2('Priority 2: Architecture Fixes (Months 1–3)'),
        p('These are structural changes that affect every subsequent feature.'),

        h3('P2-A: Replace SQLite with PostgreSQL'),
        bullet('PostgreSQL supports concurrent writers, row-level locking, JSONB with indexing, and full-text search on extracted data.'),
        bullet('The SQLAlchemy ORM layer is already database-agnostic. Connection string change + migration rewrite.'),
        bullet('This eliminates the "database is locked" 503 errors entirely.'),
        bullet('JSONB replaces JSON: extracted_data becomes queryable with GIN indexes.'),

        gap(),
        h3('P2-B: Replace Threading Queue with Celery + Redis'),
        bullet('extraction_queue.py → Celery task: @celery.task def extract_document_task(document_id: str)'),
        bullet('Route handler: enqueue job, return 202 Accepted with job_id'),
        bullet('Frontend already polls /extractions/activity — wire it to Celery task status'),
        bullet('OCR workers run as separate processes. Event loop is never blocked.'),
        bullet('Redis provides durability: queue survives API server restart.'),
        bullet('Celery Flower provides monitoring out of the box.'),

        gap(),
        h3('P2-C: Break extraction_service.py Into Bounded Services'),
        p('Recommended split:'),
        bullet('ExtractionOrchestrator (200 lines) — routing logic, feature flag checks, result assembly'),
        bullet('OcrRouter (200 lines) — provider dispatch, fallback logic, rotation retry'),
        bullet('PaddleOcrEngine (150 lines) — PaddleOCR-specific invocation'),
        bullet('GlmOcrEngine (150 lines) — GLM/Ollama-specific invocation'),
        bullet('ExtractionDiagnosticsBuilder (100 lines) — diagnostics dict construction'),
        bullet('Each has a single responsibility and is independently testable.'),

        gap(),
        h3('P2-D: Add Typed Index Columns for Critical Fields'),
        bullet('Add indexed columns to DocumentMetadataRecord: vendor_invoice_no VARCHAR, invoice_total NUMERIC, po_reference VARCHAR, document_date DATE'),
        bullet('Populate these on extraction and on manual patch'),
        bullet('Keep extracted_data JSON for the full field set'),
        bullet('Enables: "find all bundles where invoice_total > 500000", "find duplicate invoice numbers"'),

        gap(),
        h3('P2-E: Add tenant_id to All Models'),
        bullet('Add tenant_id UUID (NOT NULL) to: order_bundle, document_metadata, audit_event, reference_index'),
        bullet('Add composite indexes: (tenant_id, created_at), (tenant_id, bundle_number)'),
        bullet('All repository queries filter by tenant_id from auth context'),
        bullet('Do this before any customer data enters the system — retroactive migration is painful'),

        h2('Priority 3: Verification Quality (Months 3–6)'),
        h3('P3-A: Percentage-Based Configurable Tolerance'),
        bullet('Replace: abs(left - right) <= 2'),
        bullet('With: abs(left - right) / max(abs(left), abs(right)) <= config.amount_tolerance_pct'),
        bullet('Default: 0.5% tolerance. Configurable per bundle or document type.'),
        bullet('Add a separate absolute_tolerance_floor for rounding (e.g., Rs 1).'),

        gap(),
        h3('P3-B: Token-Set Company Name Matching'),
        bullet('Replace SequenceMatcher with: normalise → tokenise → sort → compare token sets'),
        bullet('Normalise: lowercase, remove punctuation, expand: Pvt→Private, Ltd→Limited, Co→Company'),
        bullet('Token-set ratio handles word reordering and common abbreviations correctly.'),

        gap(),
        h3('P3-C: Multi-DC Bundle Support'),
        bullet('Change verifier to accept all_dcs: list[NormalizedDocument]'),
        bullet('Match each DC against the company invoice line items'),
        bullet('Aggregate DC quantities; flag if total DC quantity != invoice quantity'),

        gap(),
        h3('P3-D: Line-Item Extraction and Matching (Long Term)'),
        bullet('Extend structured_text_parser to extract line items: HSN code, description, quantity, unit price, GST rate, line total'),
        bullet('Add line_items: list[dict] to extracted_data'),
        bullet('Extend verifier with compare_line_items(): price tolerance per line, quantity tolerance per line'),
        bullet('This moves Order Assurance from header-level to industry-standard matching accuracy'),

        // ── §6 THREE-AGENT TEAM DESIGN ──────────────────────────────────────
        h1('6. Three-Agent Review Team Design'),
        p('The following agents were used for this review. The design is also a specification for ongoing AI-assisted development and QA on this codebase.'),

        h2('Agent 1: Extraction Analyst'),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2400, 6960],
          rows: [
            new TableRow({ children: [hCell('Attribute', 2400), hCell('Specification', 6960)] }),
            new TableRow({ children: [cell('Role', 2400, C.blueLight, true), cell('Deep reader of extraction pipeline code. Reads extraction_service.py, structured_text_parser.py, digital_text_extractor.py, OCR provider code in full. Identifies logic gaps, unreachable code paths, and missing field handlers.', 6960)] }),
            new TableRow({ children: [cell('Context', 2400, C.greyLight), cell('Full text of: extraction_service.py, structured_text_parser.py, document_normalizer.py, extraction_queue.py, config.py. Validation run results (field counts per document type). Known failure cases.', 6960)] }),
            new TableRow({ children: [cell('Tools', 2400, C.greyLight), cell('Read, Grep (field pattern search), Bash (run extraction on a specific document), WebSearch (OCR accuracy benchmarks, PaddleOCR known issues)', 6960)] }),
            new TableRow({ children: [cell('Output Format', 2400, C.greyLight), cell('Per-field extraction audit: field name | parser pattern | last known result | failure mode. Missing pattern list. Regex coverage gaps per document type.', 6960)] }),
            new TableRow({ children: [cell('Mandate', 2400, C.greyLight), cell('Do not suggest fixes to files outside the extraction pipeline. Do not comment on verification logic. Report what you find, not what you think should be built.', 6960)] }),
          ]
        }),

        gap(),
        h2('Agent 2: Verification Auditor'),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2400, 6960],
          rows: [
            new TableRow({ children: [hCell('Attribute', 2400), hCell('Specification', 6960)] }),
            new TableRow({ children: [cell('Role', 2400, C.blueLight, true), cell('Reads and stress-tests the verification logic. Constructs synthetic bundle inputs representing edge cases: partial delivery, multi-DC, rounding differences, name abbreviation variants, missing documents. Runs verify_order_bundle() against each and records the result.', 6960)] }),
            new TableRow({ children: [cell('Context', 2400, C.greyLight), cell('Full text of: order_bundle_verifier.py, verification_summary_service.py, document_normalizer.py, domain/enums.py. Real validation run outputs (Panimalar, Trade, AMC baselines).', 6960)] }),
            new TableRow({ children: [cell('Tools', 2400, C.greyLight), cell('Read, Bash (run pytest on verifier unit tests, construct synthetic NormalizedDocument inputs), Grep (find all tolerance constants), WebSearch (three-way matching industry benchmarks)', 6960)] }),
            new TableRow({ children: [cell('Output Format', 2400, C.greyLight), cell('Scenario table: scenario | input | expected result | actual result | verdict (PASS/FAIL). List of hard-coded constants with recommended replacements.', 6960)] }),
            new TableRow({ children: [cell('Mandate', 2400, C.greyLight), cell('Do not read extraction code. Focus exclusively on the domain matching logic. Your job is to find cases where the verifier returns a wrong answer.', 6960)] }),
          ]
        }),

        gap(),
        h2('Agent 3: Systems Architect'),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2400, 6960],
          rows: [
            new TableRow({ children: [hCell('Attribute', 2400), hCell('Specification', 6960)] }),
            new TableRow({ children: [cell('Role', 2400, C.blueLight, true), cell('Reviews the overall system architecture: API layer, database schema, concurrency model, configuration, migration system, deployment posture. Does not read extraction or verification business logic in detail. Focuses on infrastructure concerns, cross-cutting risks, and scalability constraints.', 6960)] }),
            new TableRow({ children: [cell('Context', 2400, C.greyLight), cell('Full text of: main.py, database.py, config.py, migrations/runner.py, all models, all repositories, api/routes/bundles.py, api/routes/documents.py. Summary statistics: DB file size, bundle count, document count.', 6960)] }),
            new TableRow({ children: [cell('Tools', 2400, C.greyLight), cell('Read, Grep (find all db.execute(), all check_same_thread, all hardcoded URLs), Bash (run migration smoke test, check DB schema), WebSearch (SQLite production limits, FastAPI async blocking patterns, Celery architecture)', 6960)] }),
            new TableRow({ children: [cell('Output Format', 2400, C.greyLight), cell('Risk matrix: component | risk | severity | evidence | recommended fix. Deployment readiness checklist. Migration safety assessment.', 6960)] }),
            new TableRow({ children: [cell('Mandate', 2400, C.greyLight), cell('Do not suggest business logic changes. Infrastructure and architecture only. Your findings should be actionable by a backend engineer without domain knowledge.', 6960)] }),
          ]
        }),

        // ── §7 COMPARATIVE ANALYSIS ─────────────────────────────────────────
        h1('7. Comparative Analysis'),
        p('How does Order Assurance compare to commercial IDP platforms on the dimensions that matter?'),

        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2500, 1720, 1720, 1700, 1720],
          rows: [
            new TableRow({ children: [
              hCell('Dimension', 2500),
              hCell('Order Assurance', 1720),
              hCell('Rossum', 1720),
              hCell('Nanonets', 1700),
              hCell('Industry Std.', 1720),
            ]}),
            new TableRow({ children: [
              cell('Async processing', 2500),
              cell('Threading queue', 1720, C.redLight),
              cell('Cloud async', 1720, C.greenLight),
              cell('API-first async', 1700, C.greenLight),
              cell('Celery + Redis', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('Database', 2500),
              cell('SQLite', 1720, C.redLight),
              cell('PostgreSQL/Cloud', 1720, C.greenLight),
              cell('PostgreSQL/Cloud', 1700, C.greenLight),
              cell('PostgreSQL', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('Authentication', 2500),
              cell('None', 1720, C.redLight),
              cell('SSO + RBAC', 1720, C.greenLight),
              cell('JWT + API keys', 1700, C.greenLight),
              cell('JWT/OAuth2', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('Multi-tenancy', 2500),
              cell('None', 1720, C.redLight),
              cell('Full SaaS', 1720, C.greenLight),
              cell('Full SaaS', 1700, C.greenLight),
              cell('Org-scoped', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('Matching depth', 2500),
              cell('Header only', 1720, C.amberLight),
              cell('Line-item', 1720, C.greenLight),
              cell('Line-item', 1700, C.greenLight),
              cell('Line-item', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('OCR model type', 2500),
              cell('Rules regex + GPU OCR', 1720, C.amberLight),
              cell('Template-free AI (Aurora)', 1720, C.greenLight),
              cell('MoE VLM (OCR-3)', 1700, C.greenLight),
              cell('ML + rules hybrid', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('Languages supported', 2500),
              cell('English + partial Hindi', 1720, C.amberLight),
              cell('276 languages', 1720, C.greenLight),
              cell('Multi-language', 1700, C.greenLight),
              cell('Multi-language', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('Autonomous match rate', 2500),
              cell('Unknown (no benchmark)', 1720, C.greyLight),
              cell('>98% accuracy', 1720, C.greenLight),
              cell('High (MoE model)', 1700, C.greenLight),
              cell('90%+ (line-item)', 1720, C.greenLight),
            ]}),
            new TableRow({ children: [
              cell('India-specific docs', 2500),
              cell('Yes — built for it', 1720, C.greenLight),
              cell('Generic (Western bias)', 1720, C.amberLight),
              cell('Generic', 1700, C.amberLight),
              cell('Generic', 1720, C.amberLight),
            ]}),
            new TableRow({ children: [
              cell('Self-hosted / on-prem', 2500),
              cell('Yes — key advantage', 1720, C.greenLight),
              cell('Cloud only', 1720, C.amberLight),
              cell('Cloud + API', 1700, C.amberLight),
              cell('Varies', 1720, C.amberLight),
            ]}),
            new TableRow({ children: [
              cell('Data stays on-premise', 2500),
              cell('Yes — key advantage', 1720, C.greenLight),
              cell('No', 1720, C.redLight),
              cell('No', 1700, C.redLight),
              cell('No', 1720, C.redLight),
            ]}),
          ]
        }),

        gap(),
        h2('7.1 Where Order Assurance Is Differentiated'),
        p('Self-hosted, on-premise operation with GPU-accelerated OCR is the platform\'s genuine competitive moat. Indian logistics companies — particularly those handling Defence, Government, or sensitive supply chain procurement — cannot send documents to Rossum or Nanonets. Data residency requirements, document classification rules, and vendor agreement restrictions make cloud-based IDP non-viable for a significant segment of the market. Order Assurance serves that segment with a document model that is built for the specific five-document Indian procurement bundle, not retrofitted from a Western invoice-processing tool.'),

        h2('7.2 Where Order Assurance Is Behind'),
        p('On every infrastructure dimension — concurrency, persistence, security, matching depth — Order Assurance is 2-3 architectural generations behind commercial platforms. The gap is not in domain knowledge (that is actually strong) or OCR accuracy (that is competitive on the supported document types). The gap is in production engineering: the platform cannot safely handle multiple simultaneous users, cannot isolate tenant data, and will fail under concurrent write load.'),
        gap(),
        p('The good news: the domain model is correct, the extraction pipeline produces results, and the infrastructure gaps are addressable without rebuilding the core logic. The fixes in Section 5 do not require rewriting the verifier or the parser — they require fixing the plumbing around them.'),

        // ── §8 HONEST OPINION ───────────────────────────────────────────────
        h1('8. Honest Opinion'),
        p('Order Assurance is a technically ambitious project built by a small team on a tight scope. The document model is sophisticated — five interlinked document types with cross-references, Indian-specific field naming, OCR retry with rotation, bounding box evidence capture. The extraction accuracy results (24/24, 27/28) are real and non-trivial to achieve.'),
        gap(),
        p('But the architectural debt is not cosmetic. It is structural. The zero-authentication posture alone makes this undeployable as a business tool serving real clients. The SQLite single-writer lock makes it unusable under any concurrent load. The 1,585-line extraction service makes it unmaintainable as the document corpus grows. These are not "nice to have" improvements — they are the minimum viable conditions for the platform to be deployed to a paying customer.'),
        gap(),
        p('The right framing is: this is a proof-of-concept that has validated the domain model and achieved extraction accuracy. The next phase is production engineering — not new features, not UI polish, not more document types. PostgreSQL, Celery, authentication, and the O(N) list fix. In that order. Everything else waits.'),
        gap(),
        callout('Bottom Line', 'The core idea is right. The infrastructure is not ready. Fix the plumbing before selling the product.', C.blueLight, C.blue),

        // ── §9 APPENDIX ─────────────────────────────────────────────────────
        h1('9. Appendix — File-by-File Issue Index'),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [3800, 2000, 3560],
          rows: [
            new TableRow({ children: [hCell('File', 3800), hCell('Severity', 2000), hCell('Issue', 3560)] }),
            new TableRow({ children: [cell('main.py', 3800), badgeCell('HIGH', 2000), cell('dev_router included unconditionally; init_db only in dev', 3560)] }),
            new TableRow({ children: [cell('main.py', 3800), badgeCell('CRITICAL', 2000), cell('No auth middleware on any route', 3560)] }),
            new TableRow({ children: [cell('database.py', 3800), badgeCell('CRITICAL', 2000), cell('SQLite check_same_thread=False + 60s timeout', 3560)] }),
            new TableRow({ children: [cell('config.py', 3800), badgeCell('MEDIUM', 2000), cell('CORS origins not in config (hardcoded in main.py)', 3560)] }),
            new TableRow({ children: [cell('api/routes/bundles.py', 3800), badgeCell('CRITICAL', 2000), cell('O(N) verification on every list call, no pagination', 3560)] }),
            new TableRow({ children: [cell('api/routes/bundles.py', 3800), badgeCell('MEDIUM', 2000), cell('delete_bundle uses raw SQL delete, bypasses ORM cascade', 3560)] }),
            new TableRow({ children: [cell('services/extraction_service.py', 3800), badgeCell('CRITICAL', 2000), cell('Synchronous OCR blocks FastAPI event loop', 3560)] }),
            new TableRow({ children: [cell('services/extraction_service.py', 3800), badgeCell('HIGH', 2000), cell('1,585 lines, 6+ responsibilities, mutable diagnostics dict', 3560)] }),
            new TableRow({ children: [cell('services/extraction_queue.py', 3800), badgeCell('CRITICAL', 2000), cell('In-process queue, no persistence, no retry, no DLQ', 3560)] }),
            new TableRow({ children: [cell('services/order_bundle_verifier.py', 3800), badgeCell('HIGH', 2000), cell('abs tolerance <=2, SequenceMatcher for names, dcs[0] only', 3560)] }),
            new TableRow({ children: [cell('services/order_bundle_verifier.py', 3800), badgeCell('HIGH', 2000), cell('Header-level matching only, no line items', 3560)] }),
            new TableRow({ children: [cell('services/extraction/structured_text_parser.py', 3800), badgeCell('HIGH', 2000), cell('1,215 lines pure regex, no statistical fallback at parse layer', 3560)] }),
            new TableRow({ children: [cell('services/document_normalizer.py', 3800), badgeCell('LOW', 2000), cell('Second alias map (separate from parser aliases) — two places to update', 3560)] }),
            new TableRow({ children: [cell('migrations/runner.py', 3800), badgeCell('MEDIUM', 2000), cell('sql.split(";") incorrect for triggers; ALTER TABLE outside migration files', 3560)] }),
            new TableRow({ children: [cell('models/document.py', 3800), badgeCell('MEDIUM', 2000), cell('last_error String(500) — truncates OCR error traces', 3560)] }),
            new TableRow({ children: [cell('models/document_metadata.py', 3800), badgeCell('HIGH', 2000), cell('extracted_data as JSON blob — no queryability, no schema', 3560)] }),
            new TableRow({ children: [cell('models/ (all)', 3800), badgeCell('CRITICAL', 2000), cell('No tenant_id on any model', 3560)] }),
            new TableRow({ children: [cell('domain/enums.py', 3800), badgeCell('LOW', 2000), cell('BundleStatus, SectionStatus, CheckResult — three enums, same values', 3560)] }),
            new TableRow({ children: [cell('frontend/ExtractionActivityContext.tsx', 3800), badgeCell('LOW', 2000), cell('3s polling, no exponential backoff on failure', 3560)] }),
          ]
        }),

        gap(),
        divider(),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 200, after: 80 },
          children: [new TextRun({ text: 'Order Assurance Architecture Review — June 2026', font: 'Arial', size: 18, color: C.grey })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 0 },
          children: [new TextRun({ text: 'Full codebase read conducted by three-agent review team. All findings are evidence-based.', font: 'Arial', size: 18, italics: true, color: C.grey })]
        }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('/sessions/upbeat-cool-albattani/mnt/order-assurance/Order-Assurance-Architecture-Review.docx', buffer);
  console.log('Written: Order-Assurance-Architecture-Review.docx (' + buffer.length + ' bytes)');
}).catch(err => {
  console.error('ERROR:', err.message);
  process.exit(1);
});
