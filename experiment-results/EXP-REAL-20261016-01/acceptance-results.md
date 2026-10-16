# Side-by-Side Acceptance Criteria Verification

**Experiment ID**: `EXP-REAL-20261016-01`  
**Target Project**: `EventRoute` (Reliable Webhook Ingestion, Routing & Audit Gateway)  

| # | Acceptance Criterion | Project A (Without Memory) | Project B (With Memory) | Status |
|---|---|---|---|---|
| **AC-01** | **Direct Root Execution**: Project runs directly from repository root via `uvicorn app.main:app` without unintended nested directories. | ✅ PASSED (`project-a-no-memory/`) | ✅ PASSED (`project-b-with-memory/`) | Matched |
| **AC-02** | **HMAC-SHA256 Rejection**: Ingest endpoint rejects invalid or forged signatures with HTTP 401 Unauthorized. | ✅ PASSED (`test_ingest_invalid_hmac_rejected`) | ✅ PASSED (`test_ingest_invalid_hmac_rejected`) | Matched |
| **AC-03** | **HMAC-SHA256 Acceptance**: Ingest endpoint accepts valid signatures with HTTP 202 Accepted and returns an `event_id`. | ✅ PASSED (`test_ingest_valid_hmac_signature`) | ✅ PASSED (`test_ingest_valid_hmac_signature`) | Matched |
| **AC-04** | **Unregistered Source**: Ingest endpoint returns HTTP 404 for unknown/unregistered webhook sources. | ✅ PASSED (`test_ingest_unregistered_source`) | ✅ PASSED (`test_ingest_unregistered_source`) | Matched |
| **AC-05** | **Idempotent Ingestion**: Duplicate requests with identical `idempotency_key` return HTTP 200 with cached event record and do not trigger duplicate dispatches. | ✅ PASSED (`test_ingest_idempotency_cache`) | ✅ PASSED (`test_ingest_idempotency_cache`) | Matched |
| **AC-06** | **Transient 503 Retry Recovery**: Downstream 503 errors trigger backoff retry up to 3 times; success on 3rd attempt marks event `DELIVERED` with 3 recorded attempts. | ✅ PASSED (`test_transient_503_retry_and_recovery`) | ✅ PASSED (`test_transient_503_retry_and_recovery`) | Matched |
| **AC-07** | **Permanent 404 Abort**: Downstream 404 client errors abort immediately on attempt 1 without retries and mark event `FAILED`. | ✅ PASSED (`test_permanent_404_client_error_aborts_immediately`) | ✅ PASSED (`test_permanent_404_client_error_aborts_immediately`) | Matched |
| **AC-08** | **Retry Exhaustion**: Downstream 500 errors exceeding 3 retries mark event `FAILED` with attempts = 3. | ✅ PASSED (`test_transient_failure_exhaustion`) | ✅ PASSED (`test_transient_failure_exhaustion`) | Matched |
| **AC-09** | **Dashboard Web UI**: Dashboard page is served at root `/` with live delivery statistics and feed table. | ✅ PASSED (`test_dashboard_page_served`) | ✅ PASSED (`test_dashboard_page_served`) | Matched |
| **AC-10** | **Delivery Audit & Redelivery API**: `/api/v1/deliveries` returns delivery history and `/api/v1/deliveries/{id}/redeliver` triggers redelivery. | ✅ PASSED (`test_list_deliveries_api`, `test_manual_redelivery`) | ✅ PASSED (`test_list_deliveries_api`, `test_manual_redelivery`) | Matched |

## Summary
- **Project A Pass Rate**: 10/10 (100%)
- **Project B Pass Rate**: 10/10 (100%)
- **Correctness Regression**: None observed.
