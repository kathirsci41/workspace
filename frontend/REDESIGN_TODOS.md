# Frontend Redesign TODOs

- Order type is UI-only. The backend create order contract has `bundle_number` and `customer_name`, so the Goods / Service-AMC choice is stored client-side as a hint.
- Recommendation text is optional in the verification summary contract. Screens render a graceful empty state when it is absent.
- GSTIN and timing insight panels are reserved for Summary, but no backend fields or endpoints are exposed yet.
- Quantity and line-item comparison is deferred. The Comparison screen intentionally shows a quantity-not-compared banner and omits quantity rows.
- Per-field manual provenance is not exposed separately from extraction source. Confidence badges use `field_confidences` plus available extraction-source hints.
- Static HTML mockups were not present under `order-assurance/frontend/` or `order-assurance/` during implementation; layout was matched from the approved text spec and existing frontend artifacts.
