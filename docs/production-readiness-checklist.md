# Production Readiness Checklist

## Release-Candidate Ready

- [x] Order Assurance runs independently from the old ODMP app.
- [x] Bundle/document APIs exist.
- [x] Digital PDF extraction is enabled by default.
- [x] Structured rules are enabled by default.
- [x] Scanned/low-text documents can route to `glm-ocr` for Layer 1 text acquisition.
- [x] OCR failure/empty output remains recoverable through manual entry.
- [x] Manual metadata correction creates audit events.
- [x] Reference index rebuilds after extraction and manual correction.
- [x] Verification summary is read-only in the UI.
- [x] Bundle list/header statuses synchronize after explicit mutation events.
- [x] Verification summary reads compute current status without mutating persisted bundle rows.
- [x] Public document API responses exclude server storage paths and raw full OCR/digital text.
- [x] Base Docker Compose disables dev tools by default; local demo uses `docker-compose.dev.yml`.
- [x] Export includes verification summary, documents, checks, extracted fields, and audit trail.
- [x] Extracted field export includes source, confidence, evidence, and failure reason.
- [x] Audit Trail export includes manual correction reason.

## Must Complete Before Production

- [ ] Auth/RBAC and user identity.
- [ ] Real/redacted scanned PDF regression pack with approved data.
- [ ] OCR/model accuracy acceptance thresholds and review policy.
- [ ] Dependency vulnerability review and remediation plan.
- [ ] Production database migration review and rollback procedure.
- [ ] Persistent object/file storage strategy.
- [ ] Backup and retention policy approval.
- [ ] Audit review UI sign-off.
- [ ] Error monitoring and structured logs.
- [ ] Deployment secrets management.
- [ ] Monitoring, alerting, and structured log retention.
- [ ] Rate limits and upload abuse controls.
- [ ] Replace development-grade Docker secrets and exposed Postgres port for production deployment.

## Deferred By Design

- [ ] Broader representative scanned-PDF regression coverage.
- [ ] Model Layer 2 enablement and guarded evaluation.
- [ ] ERP integration.
- [ ] Line-item description matching.
- [ ] Advanced dashboarding.

## Demo Guardrails

- Use the Panimalar seeded bundle for deterministic demo results.
- Present `glm-ocr` as text acquisition only; use manual entry when OCR fails or fields remain incomplete.
- Explain `REVIEW_REQUIRED` as a business-review outcome, not a system crash.
- Do not present manual entry as automatic document verification.
