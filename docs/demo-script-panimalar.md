# Panimalar Demo Script

1. Start the backend and frontend.
2. Seed the demo bundle:
   ```powershell
   cd order-assurance/backend
   python -m app.scripts.seed_panimalar_demo
   ```
   Or in local development only:
   ```powershell
   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8100/api/dev/seed-panimalar
   ```
3. Open `http://127.0.0.1:5180`.
4. Open the Panimalar bundle.
5. Confirm:
   - bundle status: `REVIEW_REQUIRED`
   - customer delivery: `PARTIAL_PASS`
   - vendor procurement: `REVIEW_REQUIRED`
   - vendor billing difference: `141600`
6. Open a document review section and show manual metadata fields.
7. Click `Export Verification Report` and confirm workbook download.

## Demo Talking Points

- The release-candidate extraction path is deterministic: digital text extraction plus structured rules.
- `glm-ocr:latest` handles scanned or low-text OCR acquisition; manual entry remains available when OCR fails or misses required fields.
- Model Layer 2 is not part of the demo decision path and cannot decide order status.
- Customer invoice and DC references match, so the customer delivery flow can be reviewed independently.
- Customer PO is intentionally absent in the seeded demo, so customer delivery remains `PARTIAL_PASS`.
- Vendor bill is linked to Vendor PO `1PTR2526000467`, but only covers `554600` against `696200`.
- The recommendation is to review vendor-side partial billing before closure.

## Deferred Scope

- Auth/RBAC is intentionally deferred.
- Line-item description matching is intentionally deferred.
- ERP integration is intentionally deferred.
