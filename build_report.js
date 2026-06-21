const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, HeadingLevel, AlignmentType, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat
} = require('/sessions/upbeat-cool-albattani/mnt/outputs/docx_env/lib/node_modules/docx');
const fs = require('fs');

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, font: "Arial" })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, font: "Arial" })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text, font: "Arial" })] });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 160 },
    children: [new TextRun({ text, font: "Arial", size: 22, ...opts })]
  });
}
function blank() { return new Paragraph({ children: [new TextRun("")] }); }
function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })]
  });
}
function numbered(text) {
  return new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })]
  });
}
function hr() {
  return new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2E75B6", space: 1 } },
    children: [new TextRun("")]
  });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function ratingTable(headers, rows, colWidths) {
  const total = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => new TableCell({
        borders,
        width: { size: colWidths[i], type: WidthType.DXA },
        shading: { fill: "1F3864", type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: h, font: "Arial", size: 20, bold: true, color: "FFFFFF" })] })]
      })) }),
      ...rows.map((row, ri) => new TableRow({ children: row.map((cell, i) => {
        const isStatus = typeof cell === 'object' && cell && cell.status;
        const text = isStatus ? cell.text : (cell || '');
        const fill = isStatus
          ? (cell.status === 'good' ? "C6EFCE" : cell.status === 'warn' ? "FFEB9C" : cell.status === 'bad' ? "FFC7CE" : "F2F2F2")
          : (ri % 2 === 0 ? "F8F8F8" : "FFFFFF");
        const textColor = isStatus
          ? (cell.status === 'good' ? "375623" : cell.status === 'warn' ? "9C5700" : cell.status === 'bad' ? "9C0006" : "000000")
          : "333333";
        return new TableCell({
          borders,
          width: { size: colWidths[i], type: WidthType.DXA },
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 20, color: textColor })] })]
        });
      }) }))
    ]
  });
}

const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
      ]},
      { reference: "numbers", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
    ]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2F5496" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "2F5496" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  sections: [
    {
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      children: [
        blank(), blank(), blank(), blank(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: "ORDER ASSURANCE PLATFORM", font: "Arial", size: 52, bold: true, color: "1F3864" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
          children: [new TextRun({ text: "Platform Intelligence Report", font: "Arial", size: 36, color: "2F5496" })] }),
        hr(),
        blank(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
          children: [new TextRun({ text: "Architecture · Gaps · Recommendations · Agent Team Design", font: "Arial", size: 24, italics: true, color: "595959" })] }),
        blank(), blank(), blank(), blank(),
        new Paragraph({ alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Prepared by: Claude (Anthropic Sonnet 4.6)", font: "Arial", size: 22, color: "595959" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Date: June 19, 2026    |    Classification: Confidential", font: "Arial", size: 22, color: "595959" })] }),
        pageBreak()
      ]
    },
    {
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      headers: {
        default: new Header({ children: [new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "2F5496", space: 1 } },
          children: [new TextRun({ text: "Order Assurance  —  Platform Intelligence Report  —  June 2026", font: "Arial", size: 18, color: "2F5496" })]
        })] })
      },
      footers: {
        default: new Footer({ children: [new Paragraph({
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: "2F5496", space: 1 } },
          children: [
            new TextRun({ text: "Confidential  |  amasQIS.ai     Page ", font: "Arial", size: 18, color: "595959" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "595959" }),
          ]
        })] })
      },
      children: [

        // 1. EXECUTIVE SUMMARY
        h1("1. Executive Summary"),
        p("Order Assurance is a well-engineered, single-user Intelligent Document Processing (IDP) platform purpose-built for Indian logistics and procurement workflows. It automates extraction, cross-verification, and export of a 5-document bundle that constitutes the complete evidence trail for a single order transaction."),
        p("The platform demonstrates production-quality thinking in its extraction pipeline: dual OCR providers (PaddleOCR GPU + GLM via Ollama), evidence capture with bounding-box field highlighting, a structured rules-based parser, a full audit trail, and a formatted multi-sheet Excel export. The test suite is thorough and the codebase is cleanly layered."),
        p("However, the platform has significant architectural gaps that limit it to single-user, single-tenant, local operation. There is no authentication, no multi-tenancy, no production database, no async task worker, and no ERP integration. The matching engine operates at header level only. The LLM-based extraction layer (Model Layer 2) is present but disabled."),
        p("This report details what exists, what is missing, what needs immediate attention, and proposes a concrete roadmap including an agent team context-engineering specification for accelerating those improvements."),
        blank(),

        // 2. PLATFORM OVERVIEW
        h1("2. Platform Overview"),
        p("Order Assurance solves a real and painful problem in Indian B2B logistics: verifying that a complete set of order documents is internally consistent before payment is released. The platform handles the five-stage procure-to-pay document flow:"),
        blank(),
        ratingTable(
          ["Step", "Document", "Party", "Key Fields"],
          [
            ["1", "Customer PO", "Customer to Company", "PO No, Date, Name, Address, Grand Total, Qty"],
            ["2", "Company PO (Vendor PO)", "Company to Vendor", "Vendor PO No, Date, Vendor Name, Amount"],
            ["3", "Vendor Invoice", "Vendor to Company", "Invoice No, Date, PO Ref, Taxable Amount, Total, GST"],
            ["4", "Delivery Challan (DC)", "Company to Customer", "DC No, Date, SO No, Customer Order No, DC Amount"],
            ["5", "Company Invoice", "Company to Customer", "Invoice No, Date, SO No, Order No, Net Amount, GST"],
          ],
          [600, 2200, 2400, 4160]
        ),
        blank(),
        p("The verification engine runs cross-document checks: PO number consistency, SO number alignment, name matching, and amount comparisons, producing a structured PASS / MISMATCH / REVIEW_REQUIRED / BLOCKED verdict with evidence pointers."),
        blank(),

        // 3. CURRENT ARCHITECTURE
        h1("3. Current Architecture"),
        h2("3.1 Technology Stack"),
        blank(),
        ratingTable(
          ["Layer", "Technology", "Notes"],
          [
            ["Backend", "FastAPI + Python", "Async-capable, clean routing"],
            ["Database", "SQLite via SQLAlchemy", "Single-file DB, development only"],
            ["Migrations", "Custom incremental SQL runner", "Not Alembic, hand-rolled"],
            ["Primary OCR", "PaddleOCR GPU (PP-OCRv4)", "GPU-accelerated, allowlisted doc types"],
            ["Fallback OCR", "GLM OCR via Ollama (local LLM)", "Vision model served by Ollama"],
            ["Structured Extraction", "Rules-based parser + regex", "700+ lines of aliased patterns"],
            ["LLM Extraction (L2)", "Ollama Gemma 4:31b-cloud", "Present but disabled"],
            ["Frontend", "React 18 + Vite + TypeScript", "SPA, well-structured pages"],
            ["Export", "openpyxl (XLSX)", "Multi-sheet formatted workbook"],
            ["Storage", "Local filesystem", "Plain files on disk"],
            ["Auth", "None", "Zero authentication"],
            ["Queue", "asyncio Semaphore (in-process)", "max_concurrent=1, no retry"],
          ],
          [2200, 2800, 4360]
        ),
        blank(),

        h2("3.2 Extraction Pipeline"),
        p("For each uploaded document the pipeline follows this chain:"),
        numbered("Digital text extraction (PyMuPDF) for born-digital PDFs"),
        numbered("If text < 25 chars, route to OCR"),
        numbered("OCR: PaddleOCR GPU (if allowed doc type) then GLM fallback"),
        numbered("Header-specific OCR pass for vendor invoices (top-30% crop, focused prompt)"),
        numbered("Structured text parser: regex + field aliases + normalization"),
        numbered("Optional Model Layer 2: LLM structured JSON extraction (currently off)"),
        numbered("Field evidence capture: bounding boxes, confidence, source attribution"),
        numbered("Reference index update and bundle status sync"),
        blank(),

        h2("3.3 Verification Engine"),
        p("The order_bundle_verifier.py (466 lines) produces two independent status verdicts:"),
        bullet("Customer Delivery Status: Invoice + DC + Customer PO cross-checks"),
        bullet("Vendor Procurement Status: Vendor PO + Vendor Invoice cross-checks"),
        p("These combine into a final bundle_status. Checks include: order number matches, SO number alignment, customer name similarity (SequenceMatcher), amount comparisons, and document presence checks. Issues carry severity: BLOCKER, WARNING, or INFO."),
        blank(),

        // 4. WHAT IS THERE
        h1("4. Strengths — What Is There"),
        blank(),
        ratingTable(
          ["Capability", "Quality", "Notes"],
          [
            ["Multi-provider OCR pipeline", { status: "good", text: "Strong" }, "Extensible registry, PaddleOCR + GLM"],
            ["Digital text fast-path", { status: "good", text: "Strong" }, "PyMuPDF before OCR, major speed gain"],
            ["Header-targeted OCR", { status: "good", text: "Strong" }, "Crop + focused prompt for vendor invoices"],
            ["Field evidence + BBox highlighting", { status: "good", text: "Strong" }, "PDF preview with field location overlay"],
            ["Structured rules parser", { status: "good", text: "Solid" }, "Handles label variants, normalization"],
            ["Three-section verification", { status: "good", text: "Solid" }, "Customer, Vendor, Bundle computed independently"],
            ["Manual correction with audit", { status: "good", text: "Solid" }, "PATCH endpoint, reason tracked, audit logged"],
            ["XLSX multi-sheet export", { status: "good", text: "Solid" }, "Executive Dashboard, Business Flow, Financials"],
            ["Real-document test fixtures", { status: "good", text: "Strong" }, "Panimalar, Trade, AMC pinned baselines"],
            ["OCR rotation support", { status: "warn", text: "Partial" }, "Manual + auto-rotate (disabled by default)"],
            ["Model Layer 2", { status: "warn", text: "Inactive" }, "LLM extraction code exists, env flag off"],
            ["Evidence capture", { status: "warn", text: "Feature-flagged" }, "EVIDENCE_CAPTURE_ENABLED=false in prod"],
          ],
          [3200, 1500, 4660]
        ),
        blank(),

        // 5. WHAT IS MISSING
        h1("5. Gaps — What Is Missing"),
        h2("5.1 Critical Production Blockers"),
        blank(),
        ratingTable(
          ["Gap", "Severity", "Impact"],
          [
            ["Authentication & Authorization", { status: "bad", text: "CRITICAL" }, "No login, no RBAC. Anyone with network access reads and deletes all financial data."],
            ["Production Database", { status: "bad", text: "CRITICAL" }, "SQLite cannot handle concurrent writes. Multi-user access will corrupt data."],
            ["Multi-tenancy", { status: "bad", text: "CRITICAL" }, "All bundles globally visible. No org isolation."],
            ["Async OCR Worker", { status: "bad", text: "HIGH" }, "In-process queue blocks API event loop during long OCR jobs."],
            ["CORS hardcoded to localhost", { status: "bad", text: "HIGH" }, "Will break in any deployment beyond developer machine."],
          ],
          [2800, 1400, 5160]
        ),
        blank(),

        h2("5.2 Feature Gaps"),
        blank(),
        ratingTable(
          ["Gap", "Priority", "Description"],
          [
            ["Line-item matching", { status: "warn", text: "HIGH" }, "Verifier explicitly skips line items. Only header totals compared. Standard in 3-way matching."],
            ["Tolerance thresholds", { status: "warn", text: "HIGH" }, "No configurable +/- % tolerance on amounts. Any rounding difference = MISMATCH."],
            ["Vendor master / GST registry", { status: "warn", text: "HIGH" }, "No vendor database. Cannot validate extracted GST/name against registered master."],
            ["ERP integration", { status: "warn", text: "MEDIUM" }, "ERP_ORDER_EXPORT type in enums but no extraction logic or ingestion endpoint."],
            ["Bulk upload", { status: "warn", text: "MEDIUM" }, "One document per upload. No batch / ZIP ingestion."],
            ["Search and filter", { status: "warn", text: "MEDIUM" }, "Bundle list has no status, date, or name filter. Unusable at scale."],
            ["Analytics dashboard", { status: "warn", text: "MEDIUM" }, "No aggregate metrics: match rates, accuracy trends, turnaround time."],
            ["Partial billing handling", { status: "warn", text: "MEDIUM" }, "Noted as open issue in CLAUDE.md. Vendor partial billing not resolved."],
            ["Webhook / notifications", { status: "warn", text: "MEDIUM" }, "No event hooks. No alerts on extraction completion or MISMATCH status."],
            ["Auto-approve high confidence", { status: "warn", text: "LOW" }, "All bundles require manual review regardless of extraction confidence."],
            ["Multi-DC reconciliation", { status: "warn", text: "LOW" }, "Only first DC used. Split-order multi-DC scenarios not reconciled."],
          ],
          [2600, 1400, 5360]
        ),
        blank(),

        h2("5.3 Technical Debt"),
        bullet("Custom migration runner instead of Alembic: cannot use standard tooling, increases migration risk as schema grows."),
        bullet("Regex-heavy structured parser: 700+ lines of hand-coded patterns. Each new document variant requires manual addition. Brittle under novel layouts."),
        bullet("Model Layer 2 disabled: LLM fallback that would catch what the regex parser misses is off. Parser failures produce EXTRACTION_FAILED with no recovery path."),
        bullet("Dev routes in production: /api/dev/* endpoints exist behind ENABLE_DEV_TOOLS guard. Accidental exposure surface area."),
        bullet("Global OCR queue: single asyncio.Semaphore serialises all OCR globally. One slow vendor invoice blocks all other extractions."),
        blank(),

        // 6. PRIORITY MATRIX
        h1("6. Priority Matrix"),
        blank(),
        ratingTable(
          ["#", "Item", "Impact", "Effort", "Recommendation"],
          [
            ["1", "Add JWT authentication + RBAC", { status: "bad", text: "CRITICAL" }, { status: "warn", text: "Medium" }, "Implement before any team use. FastAPI-Users or Auth0."],
            ["2", "Migrate to PostgreSQL + Alembic", { status: "bad", text: "CRITICAL" }, { status: "warn", text: "Medium" }, "Add docker-compose with postgres:16. Replace SQLite."],
            ["3", "Async OCR worker (Celery + Redis)", { status: "bad", text: "HIGH" }, { status: "bad", text: "High" }, "Decouple extraction from API request cycle."],
            ["4", "Enable Model Layer 2 with confidence fallback", { status: "warn", text: "HIGH" }, { status: "good", text: "Low" }, "Flip MODEL_LAYER2_ENABLED=true + set confidence threshold."],
            ["5", "Enable evidence capture in production", { status: "warn", text: "HIGH" }, { status: "good", text: "Low" }, "Flip EVIDENCE_CAPTURE_ENABLED=true. Already implemented."],
            ["6", "Add line-item matching", { status: "warn", text: "HIGH" }, { status: "bad", text: "High" }, "Extend verifier to compare line-item tables."],
            ["7", "Configurable tolerance thresholds", { status: "warn", text: "HIGH" }, { status: "good", text: "Low" }, "Add +/- % config to amount comparisons in verifier."],
            ["8", "Vendor master service", { status: "warn", text: "MEDIUM" }, { status: "warn", text: "Medium" }, "Build vendor registry with GST validation."],
            ["9", "Search / filter / pagination on bundles", { status: "warn", text: "MEDIUM" }, { status: "good", text: "Low" }, "Add query params to GET /bundles. Index status, date."],
            ["10", "Webhook / notification hooks", { status: "warn", text: "MEDIUM" }, { status: "warn", text: "Medium" }, "POST to configurable URL on status change events."],
            ["11", "Replace migration runner with Alembic", { status: "warn", text: "MEDIUM" }, { status: "warn", text: "Medium" }, "Long-term maintainability. Current runner works."],
            ["12", "Analytics page", { status: "warn", text: "MEDIUM" }, { status: "warn", text: "Medium" }, "Add /api/analytics endpoint + frontend chart page."],
          ],
          [400, 3000, 1200, 1000, 3760]
        ),
        blank(),

        // 7. COMPETITIVE POSITIONING
        h1("7. Competitive Positioning"),
        blank(),
        ratingTable(
          ["Capability", "Commercial IDP (Rossum/Nanonets)", "Order Assurance Today", "Gap?"],
          [
            ["OCR Accuracy", "96%+ (Aurora 1.5, cloud Vision)", "~91% on key fields", { status: "warn", text: "Close" }],
            ["Three-Way Matching", "Header + line-item + tolerance", "Header-level only, no tolerance", { status: "bad", text: "Gap" }],
            ["Authentication", "SSO, SAML, RBAC, audit log", "None", { status: "bad", text: "Gap" }],
            ["Multi-tenancy", "Tenant-isolated, per-org config", "None (global data)", { status: "bad", text: "Gap" }],
            ["ERP Integration", "SAP, NetSuite, MS Dynamics", "Not implemented", { status: "bad", text: "Gap" }],
            ["Workflow Automation", "Approval chains, escalation", "Status flags only", { status: "bad", text: "Gap" }],
            ["Analytics", "Extraction metrics, SLA dashboards", "None", { status: "bad", text: "Gap" }],
            ["India-specific documents", "Generic global formats", "Indian GST, DC, SO formats", { status: "good", text: "Advantage" }],
            ["Local / Offline operation", "Cloud-only", "Fully local, air-gap capable", { status: "good", text: "Advantage" }],
            ["Cost per page", "$0.01 - $0.10 per page", "Zero (local OCR)", { status: "good", text: "Advantage" }],
          ],
          [2400, 2600, 2400, 2160]
        ),
        blank(),
        p("Order Assurance has three genuine competitive advantages: India-specific domain logic, fully local operation, and zero per-page cost. These should be the platform's core differentiators as it evolves."),
        blank(),

        // 8. TARGET ARCHITECTURE
        h1("8. Target Architecture Changes"),
        h2("Database & Persistence"),
        bullet("Replace SQLite with PostgreSQL. Add docker-compose.yml with postgres:16 service."),
        bullet("Replace custom migration runner with Alembic. Existing SQL migration files become baseline revision."),
        bullet("Add tenant_id foreign key to OrderBundle and all child tables."),
        blank(),
        h2("Authentication & Authorization"),
        bullet("Add JWT auth using FastAPI-Users or lightweight custom implementation."),
        bullet("Three initial roles: Viewer (read-only), Reviewer (corrections), Admin (full)."),
        bullet("Scope all API endpoints with OAuth2 dependency injection."),
        blank(),
        h2("Extraction Pipeline"),
        bullet("Move OCR jobs to Celery workers with Redis as broker. API returns task_id, client polls status."),
        bullet("Enable MODEL_LAYER2_ENABLED=true with automatic fallback when parser confidence < 0.7."),
        bullet("Enable EVIDENCE_CAPTURE_ENABLED=true in production (code is already there)."),
        bullet("Add confidence-based auto-approve: all checks PASS + confidence > 0.95 = auto VERIFIED."),
        blank(),
        h2("Verification Engine"),
        bullet("Add line-item matching: compare SKU/description + quantity + unit price across PO and Invoice."),
        bullet("Add configurable tolerance thresholds per document type (e.g., +/- 2% on totals)."),
        bullet("Add vendor master service: persist known vendors with GST, canonical name, bank account."),
        bullet("Fix multi-DC handling: aggregate DC amounts when multiple DCs exist for one bundle."),
        blank(),
        h2("Frontend & UX"),
        bullet("Add login page and session management (JWT storage in memory, not localStorage)."),
        bullet("Add search/filter bar on bundle list (status, date range, customer name)."),
        bullet("Add analytics page: extraction accuracy trend, match rate, avg turnaround time."),
        bullet("Add real-time extraction progress via WebSocket or SSE polling."),
        blank(),

        // 9. AGENT TEAM
        h1("9. Agent Team Design"),
        p("To execute the improvements above, the following specialized agent team is recommended. Each agent is given a precise role, tools, token budget, and loop constraint."),
        blank(),

        h2("9.1 Team Overview"),
        ratingTable(
          ["Agent", "Role", "Primary Responsibility"],
          [
            ["Coordinator", "Orchestrator", "Routes work, enforces phase gates per CLAUDE.md 5-step test protocol"],
            ["Architect", "System Designer", "Writes ADRs, sets implementation contracts before code begins"],
            ["DB Migration", "Database Engineer", "PostgreSQL, Alembic, schema changes, multi-tenant model"],
            ["Auth", "Security Engineer", "JWT auth, RBAC, user model, endpoint protection"],
            ["OCR Pipeline", "ML/Extraction Engineer", "Celery queue, Model Layer 2 activation, confidence fallback"],
            ["Verifier", "Business Logic Engineer", "Line-item matching, tolerance config, vendor master"],
            ["Frontend", "UI/UX Engineer", "Auth UI, search/filter, analytics, extraction notifications"],
            ["Integration", "Systems Engineer", "ERP ingestion, webhooks, bulk upload API"],
            ["QA", "Quality Assurance", "Runs 5-step CLAUDE.md gate, real-document validation, blocks phase if failed"],
          ],
          [1800, 1800, 5760]
        ),
        blank(),

        h2("9.2 Context Engineering Specs"),
        blank(),
        h3("Coordinator Agent"),
        ratingTable(
          ["Attribute", "Specification"],
          [
            ["Role", "Orchestrator. Decomposes requests into phased tasks, assigns to specialists, gates completion using CLAUDE.md 5-step protocol."],
            ["Tools", "TaskCreate, TaskUpdate, TaskList, Read, WebSearch"],
            ["Token Budget", "8,000 tokens per turn"],
            ["Loop Constraint", "Max 3 re-routes per phase before escalating to human"],
            ["System Prompt Core", "You are the Coordinator for Order Assurance. Every phase MUST run all 5 CLAUDE.md test steps before declaring done. You assign tasks to specialist agents by name. You resolve blockers by splitting tasks, not expanding scope."],
            ["Handoff Output", "phase_report.md: task summary, test output, changed files, open blockers"],
          ],
          [2200, 7160]
        ),
        blank(),
        h3("Architect Agent"),
        ratingTable(
          ["Attribute", "Specification"],
          [
            ["Role", "Reviews all proposals before implementation. Sets API shapes, DB schema deltas, interface signatures that other agents must follow."],
            ["Tools", "Read, Write, WebSearch, WebFetch"],
            ["Token Budget", "12,000 tokens per turn"],
            ["Loop Constraint", "1 ADR per session. Max 2 revision rounds before locking."],
            ["Scope Constraint", "Read-only on existing code. Writes only to docs/adr/. Never edits implementation files."],
            ["Output Format", "ADR: Status / Context / Decision / Consequences / Implementation Checklist"],
          ],
          [2200, 7160]
        ),
        blank(),
        h3("DB Migration Agent"),
        ratingTable(
          ["Attribute", "Specification"],
          [
            ["Role", "Owns all database schema changes: PostgreSQL migration, Alembic setup, multi-tenant schema."],
            ["Tools", "Read, Write, Edit, Bash"],
            ["Token Budget", "6,000 tokens per turn"],
            ["Loop Constraint", "Max 1 migration file per session. Must run test_migrations.py before completing."],
            ["Scope", "backend/app/models/, backend/migrations/, backend/app/database.py, alembic.ini only"],
            ["Acceptance Criterion", "Migration idempotent (up/down), test_migrations.py passes, no existing test broken"],
          ],
          [2200, 7160]
        ),
        blank(),
        h3("Auth Agent"),
        ratingTable(
          ["Attribute", "Specification"],
          [
            ["Role", "Implements JWT auth, user model, and RBAC. Wraps all existing routes with auth dependency."],
            ["Tools", "Read, Write, Edit, Bash"],
            ["Token Budget", "8,000 tokens per turn"],
            ["Loop Constraint", "Phase 1: user model + login. Phase 2: RBAC roles. Phase 3: scope routes. Never mixes phases."],
            ["Key Constraint", "Auth must be bypassable in tests via DISABLE_AUTH=true env flag. Must not break existing tests."],
            ["Acceptance Criterion", "Login returns JWT, 401 without token, 403 on wrong role, all existing tests pass"],
          ],
          [2200, 7160]
        ),
        blank(),
        h3("OCR Pipeline Agent"),
        ratingTable(
          ["Attribute", "Specification"],
          [
            ["Role", "Owns extraction pipeline improvements: Celery queue, Model Layer 2 activation, confidence auto-approve."],
            ["Tools", "Read, Write, Edit, Bash"],
            ["Token Budget", "10,000 tokens per turn"],
            ["Loop Constraint", "Phase 1: Celery integration only. Phase 2: Model Layer 2. Never mixes. Max 3 retries on test failure."],
            ["Scope", "backend/app/services/extraction/, extraction_queue.py, extraction_service.py"],
            ["Key Constraint", "Must preserve OCR provider registry pattern. Must run real-document validation after any extraction change."],
            ["Acceptance Criterion", "Extraction is async background job, validation baselines maintained, queue survives API restart"],
          ],
          [2200, 7160]
        ),
        blank(),
        h3("Verifier Agent"),
        ratingTable(
          ["Attribute", "Specification"],
          [
            ["Role", "Owns verification logic improvements: line-item matching, tolerance thresholds, vendor master."],
            ["Tools", "Read, Write, Edit, Bash"],
            ["Token Budget", "10,000 tokens per turn"],
            ["Loop Constraint", "Phase 1: tolerance only. Phase 2: vendor master model. Phase 3: line-item. Strictly sequential."],
            ["Scope", "order_bundle_verifier.py, document_normalizer.py, models/vendor.py (new), repositories/vendors.py (new)"],
            ["Key Constraint", "All 3 real-doc baselines (Panimalar 24/24, Trade zero-failed, AMC 27/28) must be maintained."],
            ["Acceptance Criterion", "Tolerance respected in checks, vendor GST validated, line items reconciled as check results"],
          ],
          [2200, 7160]
        ),
        blank(),
        h3("QA Agent"),
        ratingTable(
          ["Attribute", "Specification"],
          [
            ["Role", "Enforces CLAUDE.md 5-step test gate on every phase. Blocks completion if any step fails."],
            ["Tools", "Bash, Read"],
            ["Token Budget", "4,000 tokens per turn (reports only)"],
            ["Loop Constraint", "Runs after every agent phase. Does not write code. Reports blockers to Coordinator only."],
            ["Output Format", "Phase QA Report: Step 1-5 results with exact counts, real-doc run summary, block/pass verdict"],
            ["Key Constraint", "Never accepts 'tests pass' without exact pass/skip/fail count. Never declares phase done with a failing test."],
          ],
          [2200, 7160]
        ),
        blank(),

        h2("9.3 Execution Loop"),
        numbered("Coordinator receives improvement request, creates phase task list"),
        numbered("Architect writes ADR, reviewed and approved before any code"),
        numbered("Specialist agents implement per ADR contracts, scoped strictly to their directories"),
        numbered("QA Agent runs 5-step gate, returns block/pass verdict"),
        numbered("If blocked: Coordinator re-routes to specialist with specific fix instruction (max 3 attempts)"),
        numbered("If passed: Coordinator marks phase complete, delivers phase_report.md to human"),
        blank(),
        p("Key principles: No agent expands its own scope. No phase is done without the QA gate. The Coordinator is the only agent that crosses agent boundaries. Agent context is reset between phases to prevent stale assumptions."),
        blank(),

        h2("9.4 Token Allocation Summary"),
        ratingTable(
          ["Agent", "Budget/Turn", "Rationale"],
          [
            ["Coordinator", "8,000", "Task context, not deep code reading"],
            ["Architect", "12,000", "Must read full codebase to write accurate ADRs"],
            ["DB Migration", "6,000", "Focused scope: schema + test files"],
            ["Auth", "8,000", "Multi-file: routes, models, deps"],
            ["OCR Pipeline", "10,000", "Complex multi-file extraction code"],
            ["Verifier", "10,000", "466-line verifier + new vendor logic"],
            ["Frontend", "8,000", "Multiple pages, hooks, API types"],
            ["Integration", "8,000", "ERP schema + webhook config + API design"],
            ["QA", "4,000", "Read-only, test output parsing only"],
          ],
          [2800, 2000, 4560]
        ),
        blank(),

        // 10. OPINION
        h1("10. My Opinion"),
        p("Having read the full codebase and compared it against the current state of the IDP market, here is my honest assessment."),
        blank(),
        p("Order Assurance is genuinely impressive as a solo-built document intelligence system. The extraction pipeline shows deep domain knowledge: the field alias dictionaries, the header-targeted OCR crop strategy, the evidence bounding-box system. These are not obvious engineering decisions. The test suite is mature, with real-document regression fixtures pinned to specific baselines. The export XLSX is formatted to a professional standard. This is not a toy prototype."),
        blank(),
        p("The platform's core strength is also its most defensible competitive advantage: it runs entirely locally with India-specific document logic, zero cloud dependency, and zero per-page cost. No commercial IDP platform understands Indian delivery challans, GST invoice structure, and SO-based reconciliation the way this system does. That specificity is genuinely valuable."),
        blank(),
        p("The critical problem is that none of this value can be shared without authentication and a PostgreSQL migration. Right now the platform is one accidental concurrent write away from database corruption, and anyone on the network can access every financial document ever uploaded. These are not minor issues. They are existential blockers to any team use."),
        blank(),
        p("My recommended sequence is direct: Auth + PostgreSQL first, everything else second. Once those land, the path to a genuinely competitive logistics document intelligence platform is clear."),
        blank(),
        p("The gap between Order Assurance today and where Rossum or Nanonets are is not a technology gap. It is an infrastructure gap. The document intelligence quality is comparable to commercial tools on Indian-format documents. The missing pieces (auth, DB, async queue, line-item matching) are well-understood engineering problems. With a focused 8-12 week push using the agent team in Section 9, Order Assurance could become a credible, production-grade alternative for Indian logistics companies at a fraction of the per-page cost of cloud IDP services."),
        blank(),

        // APPENDIX
        h1("Appendix A: Key File Map"),
        ratingTable(
          ["Path", "Purpose"],
          [
            ["backend/app/main.py", "FastAPI app factory, CORS, lifespan hook"],
            ["backend/app/config.py", "All env-var settings (frozen dataclass)"],
            ["backend/app/domain/enums.py", "DocumentType, BundleStatus, CheckResult enums"],
            ["backend/app/services/extraction_service.py", "Main extraction orchestrator"],
            ["backend/app/services/extraction/structured_text_parser.py", "Regex + alias field parser"],
            ["backend/app/services/extraction/model_layer2.py", "LLM structured extraction (inactive)"],
            ["backend/app/services/extraction/ocr_providers/", "Provider registry: GLM + PaddleOCR"],
            ["backend/app/services/order_bundle_verifier.py", "Cross-document verification logic (466 lines)"],
            ["backend/app/services/export_service.py", "XLSX multi-sheet export (openpyxl)"],
            ["backend/app/services/extraction_queue.py", "In-process asyncio OCR queue"],
            ["frontend/src/App.tsx", "React router configuration"],
            ["frontend/src/lib/build1.ts", "Business logic helpers for UI status computation"],
            ["frontend/src/types/api.ts", "TypeScript API contract types"],
            [".env", "Production config (APP_ENV=production, PaddleOCR GPU, SQLite)"],
          ],
          [3800, 5560]
        ),
        blank(),

        h1("Appendix B: Validation Baselines"),
        ratingTable(
          ["Fixture", "Baseline", "Run Reference"],
          [
            ["Panimalar", "24/24 fields, zero failed doc statuses, XLSX passed, vendor partial billing open", "real-doc-001-tradefix-final8"],
            ["Trade", "Zero failed document statuses, XLSX passed", "real-doc-002-trade-fix7"],
            ["AMC", "27/28 fields, missing Delivery Challan only, vendor PASS, XLSX passed", "real-doc-003-amc-fix1"],
          ],
          [1800, 4000, 3560]
        ),
        blank(),

        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 600 },
          children: [new TextRun({ text: "— End of Report —", font: "Arial", size: 22, italics: true, color: "595959" })]
        }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('/sessions/upbeat-cool-albattani/mnt/order-assurance/Order-Assurance-Platform-Intelligence-Report.docx', buffer);
  console.log('Written: Order-Assurance-Platform-Intelligence-Report.docx');
}).catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
