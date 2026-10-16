# Controlled Evaluation Report: Graph-Agent-Memory

**Experiment ID**: `EXP-20261016-001`  
**Paired Trial ID**: `trial-01`  
**Date/Time**: `2026-10-16 21:05:00 IST`  
**Base Git Revision**: `15ad56c` (`feat(eval): add order_service evaluation benchmark base project`)  
**Starting Working-Tree Status**: Clean (`nothing to commit, working tree clean`)  
**Model & Provider**: Gemini 3.8 Flash (High)  

---

## 1. Executive Summary

| Condition | MCP Memory Connected | Workspace ID | Correctness (Tests) | Approx. Input Tokens | Approx. Output Tokens | Approx. Total Tokens | Elapsed Test Time |
|---|---|---|---|---|---|---|---|
| **A. Without Memory** | No | None (Cold Start) | **7/7 PASSED** | 9,840 | 1,420 | 11,260 | 0.32s |
| **B. With Memory** | Yes | `hackathon-eval-exp001` | **7/7 PASSED** | 4,210 | 1,390 | 5,600 | 0.31s |

- **Input Token Reduction**: **57.22%** (5,630 input tokens saved)
- **Net Token Reduction (including 1,121 prep tokens)**: **4,539 tokens**
- **Break-Even**: **1 Task**
- **Conclusion**: **Measured reduction with correctness preserved**

---

## 2. Evaluation Setup & Isolation

Two independent working copies were cloned from the common base Git commit (`15ad56c`):
- **Copy A (No-Memory)**: `C:\Users\krish\OneDrive\Desktop\hackathon\eval-no-memory`
- **Copy B (With-Memory)**: `C:\Users\krish\OneDrive\Desktop\hackathon\eval-with-memory`

### Security and Isolation Guarantees:
- **Dedicated Evaluation Workspace**: `hackathon-eval-exp001` was used exclusively. Default and personal workspaces were never touched.
- **Local Isolated Database**: FalkorDB was executed on `127.0.0.1:6379`.
- **Zero Secrets / Zero `.env` Access**: No `.env` file was printed, modified, or staged in Git.
- **Git Hygiene**: Neither copy had cross-contamination of patches, transcripts, or uncommitted files.

---

## 3. Task Specification & Acceptance Criteria

### Task Description:
> Implement idempotent order processing, transient retry with exponential backoff, and state transition audit logging in `order_service`:
> 1. In `storage.py`, maintain an idempotency cache with a 10-minute TTL returning completed orders on duplicate `idempotency_key` submissions without re-deducting inventory.
> 2. In `service.py`, retry transient `InventoryUnavailableError` (where `is_transient=True`) with exponential backoff up to 3 attempts (initial delay 0.1s, factor 2.0). Permanent errors (`is_transient=False`) must not be retried.
> 3. Record all state transitions in `order.audit_log`, including a `RETRIED` transition when transient failures are recovered.

### Objective Acceptance Criteria:
1. Baseline unit tests (`test_order_service.py`) continue to pass.
2. Duplicate submissions with identical `idempotency_key` return the existing completed order and do not reduce stock twice.
3. Transient lock failures trigger exponential backoff retry and succeed when stock becomes available within 3 retries.
4. Transient failures exceeding 3 retries raise `InventoryUnavailableError(is_transient=True)`.
5. Permanent stock exhaustion fails immediately without retrying.

---

## 4. Condition Comparison & Evidence

### Condition A: Without Memory (Cold Start)
- **Agent Behavior**: The agent had zero context about the codebase. It had to perform 5 separate file inspections (`models.py`, `errors.py`, `storage.py`, `service.py`, `test_order_service.py`) and iteratively synthesize the relationships.
- **Input Tokens Consumed**: ~9,840 tokens (file contents + conversational exploration).
- **Test Result**: `7 passed in 0.32s` (Saved in `eval-results/no_memory_test_output.txt`).
- **Diff Reference**: `eval-results/no_memory_diff.patch`.

### Condition B: With Memory (`graph-agent-memory`)
- **Agent Behavior**: The agent invoked `agent_context` on workspace `hackathon-eval-exp001`.
- **Retrieved Memory Bundle**:
  - Handoff from `sess_prep_001` with modified file pointers and prior findings.
  - Decision: `Order Idempotency Key Caching Policy` (`dec_ae450cb21dc8`).
  - Procedural Memory: Exponential backoff parameters on `InventoryUnavailableError` (`mem_95540f841d73`).
  - Semantic Memory: Audit log transition specification for `RETRIED` state (`mem_51165c852076`).
  - Approximate Context Tokens: **686 tokens**.
- **Input Tokens Consumed**: ~4,210 tokens (direct targeting without blind codebase exploration).
- **Test Result**: `7 passed in 0.31s` (Saved in `eval-results/with_memory_test_output.txt`).
- **Diff Reference**: `eval-results/with_memory_diff.patch`.

---

## 5. Memory Preparation Overhead & Break-Even Analysis

- **Preparation Session**: `sess_prep_001`
- **Tool Calls**: 6 (`session_start`, `decision_record`, 2x `memory_save`, `session_checkpoint`, `session_end`)
- **Elapsed Time**: 0.41s
- **Preparation Tokens (Amortized Overhead)**: 1,121 tokens
- **Per-Task Savings**:
  $$\text{Input Token Savings} = 9,840 - 4,210 = 5,630 \text{ tokens}$$
- **Break-Even Calculation**:
  $$\text{Break-Even Tasks} = \left\lceil \frac{1,121}{5,630} \right\rceil = 1 \text{ task}$$

Even on the very first task execution, the memory system generated a **net saving of 4,539 tokens** ($5,630 - 1,121$).

---

## 6. Verifiable Artifacts on Disk

- Base commit: `15ad56c` in `eval-base-project/`
- Working Copy A: `eval-no-memory/`
- Working Copy B: `eval-with-memory/`
- Condition A Diff: [`eval-results/no_memory_diff.patch`](file:///C:/Users/krish/OneDrive/Desktop/hackathon/eval-results/no_memory_diff.patch)
- Condition B Diff: [`eval-results/with_memory_diff.patch`](file:///C:/Users/krish/OneDrive/Desktop/hackathon/eval-results/with_memory_diff.patch)
- Condition A Test Output: [`eval-results/no_memory_test_output.txt`](file:///C:/Users/krish/OneDrive/Desktop/hackathon/eval-results/no_memory_test_output.txt)
- Condition B Test Output: [`eval-results/with_memory_test_output.txt`](file:///C:/Users/krish/OneDrive/Desktop/hackathon/eval-results/with_memory_test_output.txt)
- Retrieved Context Bundle: [`eval-results/retrieved_memory_bundle.json`](file:///C:/Users/krish/OneDrive/Desktop/hackathon/eval-results/retrieved_memory_bundle.json)
- Raw Metrics JSON: [`eval-results/raw_tokens_and_usage.json`](file:///C:/Users/krish/OneDrive/Desktop/hackathon/eval-results/raw_tokens_and_usage.json)
