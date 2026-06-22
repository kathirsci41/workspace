#!/usr/bin/env pwsh
# Upload all sample bundles to the Order Assurance platform

$BASE = "http://localhost:8100"
$SAMPLE = "$PSScriptRoot\..\sample\extracted"

function Create-Bundle($number, $customer, $po, $so) {
    $body = @{ bundle_number=$number; customer_name=$customer; customer_po_no=$po; so_no=$so } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$BASE/bundles" -Method POST -Body $body -ContentType "application/json" -ErrorAction Stop
    Write-Host "  Created bundle: $($resp.id) [$number]"
    return $resp.id
}

function Upload-Doc($bundleId, $filePath, $docType) {
    $name = Split-Path $filePath -Leaf
    $form = @{
        document_type = $docType
        file = Get-Item $filePath
    }
    try {
        $resp = Invoke-RestMethod -Uri "$BASE/bundles/$bundleId/documents" -Method POST -Form $form -ErrorAction Stop
        Write-Host "    Uploaded [$docType]: $name"
    } catch {
        Write-Host "    ERROR uploading $name : $_" -ForegroundColor Red
    }
}

# ── 1. PANIMALAR ──────────────────────────────────────────────────────────────
Write-Host "`n=== Panimalar ===" -ForegroundColor Cyan
$id = Create-Bundle "Panimalar-001" "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE" "PNM/WO/2021-2022" "SO-PNM-001"
$dir = "$SAMPLE\Panimalar"
Upload-Doc $id "$dir\Customer PO_.pdf"                     "CUSTOMER_PO"
Upload-Doc $id "$dir\Customer Invoice 1ITR2526001878.pdf"  "CUSTOMER_INVOICE"
Upload-Doc $id "$dir\DC 1DNT2526DC3100.pdf"                "DELIVERY_CHALLAN"
Upload-Doc $id "$dir\Vendor PO 1PTR2526000467.pdf"         "VENDOR_PO"
Upload-Doc $id "$dir\Vendor Bill 2526PSI25087738.pdf"      "VENDOR_INVOICE"

# ── 2. SRIRAM FINANCE (AMC bundle) ──────────────────────────────────────────
Write-Host "`n=== Sriram Finance ===" -ForegroundColor Cyan
$id = Create-Bundle "SriramFin-001" "SHRIRAM FINANCE LIMITED" "PO-SRIRAM-2526" "SO-SRIRAM-001"
$dir = "$SAMPLE\Sriram fin"
Upload-Doc $id "$dir\Purchase order shriram fin.pdf"       "CUSTOMER_PO"
Upload-Doc $id "$dir\Tax Invoice Shriram fin.pdf"          "CUSTOMER_INVOICE"
Upload-Doc $id "$dir\PO AMC corro health.pdf"              "VENDOR_PO"
Upload-Doc $id "$dir\Tax invoice corro health.pdf"         "VENDOR_INVOICE"
Upload-Doc $id "$dir\Purchase order Inflow.pdf"            "VENDOR_PO"
Upload-Doc $id "$dir\Tax invoice inflow AMC.pdf"           "VENDOR_INVOICE"
Upload-Doc $id "$dir\purchase order reddington.pdf"        "VENDOR_PO"
Upload-Doc $id "$dir\Tax invoice reddington.pdf"           "VENDOR_INVOICE"

# ── 3. TRADE ─────────────────────────────────────────────────────────────────
Write-Host "`n=== Trade ===" -ForegroundColor Cyan
$id = Create-Bundle "Trade-001" "TRADE CUSTOMER" "TRADE-CPO-2526" "SO-TRADE-001"
$dir = "$SAMPLE\Trade\Trade"
Upload-Doc $id "$dir\TRADE - CUSTOMER PO.pdf"              "CUSTOMER_PO"
Upload-Doc $id "$dir\TRADE - INVOICE 1ITR2526001785.pdf"   "CUSTOMER_INVOICE"
Upload-Doc $id "$dir\TRADE - DC 1DNT2526DC2915.pdf"        "DELIVERY_CHALLAN"
Upload-Doc $id "$dir\TRADE - PURCHASE ORDER.pdf"           "VENDOR_PO"
Upload-Doc $id "$dir\TRADE - VENDOR BILL -C190224826.pdf"  "VENDOR_INVOICE"
Upload-Doc $id "$dir\TRADE -VENDOR BILL - C190224835.pdf"  "VENDOR_INVOICE"

Write-Host "`nAll done." -ForegroundColor Green
