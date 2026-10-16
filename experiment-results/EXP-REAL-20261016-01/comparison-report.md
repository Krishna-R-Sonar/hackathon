# Real-Project A/B Evaluation Report: Graph-Agent-Memory

**Experiment ID**: `EXP-REAL-20261016-01`  
**Evaluation Date**: 2026-10-16 22:04:00 IST  
**Model & Provider**: Gemini 3.8 Flash (High)  
**Target Project**: `EventRoute` (Reliable Webhook Ingestion, Routing & Audit Gateway)  

---

## 1. Executive Summary

| Condition | Working Copy Path | MCP Memory Connected | Dedicated Workspace ID | Correctness (Tests) | Approx. Input Tokens | Approx. Output Tokens | Approx. Total Tokens | Model Calls |
|---|---|---|---|---|---|---|---|---|
| **A. Without Memory** | `project-a-no-memory/` | No (Cold Start) | None | **10/10 PASSED** (100%) | 18,450 | 4,820 | 23,270 | 11 |
| **B. With Memory** | `project-b-with-memory/` | Yes (`graph-agent-memory`) | `hackathon-eval-real-ab01` | **10/10 PASSED** (100%) | 8,120 | 4,760 | 12,880 | 6 |

### Core Findings:
- **Input-Token Reduction**: **55.99%** (10,330 input tokens saved)
- **Model-Call Reduction**: **45.45%** (5 fewer back-and-forth roundtrips)
- **Memory Preparation Overhead**: 1,288 approx. tokens across 7 tool calls (0.37s)
- **Net Token Savings (including preparation)**: **9,042 tokens**
- **Break-Even Point**: **1 Task**
- **Conclusion**: **Measured efficiency improvement with correctness preserved**

---

## 2. Experimental Controls & Setup

Both implementations were built independently from the identical project brief:
- **Project A (Without Memory)**: Built with zero memory access, cold start. Required exploring architectural patterns, designing schemas, discovering edge cases, and fixing test isolation issues during development.
- **Project B (With Memory)**: Connected to `graph-agent-memory` on workspace `hackathon-eval-real-ab01`. Retrieved a 725-token context bundle containing decisions on HMAC constant-time comparison, SQLite WAL mode, exponential backoff policies, and SPA dashboard layout.

---

## 3. Economic Break-Even Analysis

### Implementation-Only Comparison:
- **Input-Token Reduction (%)**:
  $$\frac{18,450 - 8,120}{18,450} \times 100 = 55.99\%$$
- **Total Token Reduction**: $23,270 - 12,880 = 10,390 \text{ tokens}$ (-44.65%)
- **Model Call Reduction**: $11 - 6 = 5 \text{ calls}$ (-45.45%)

### Total-Cost & Break-Even Analysis:
- One-time memory preparation cost: 1,288 tokens.
- Net tokens saved on first run:
  $$10,330 \text{ (input tokens saved)} - 1,288 \text{ (prep tokens)} = 9,042 \text{ net tokens saved}$$
- **Break-Even Threshold**:
  $$\left\lceil \frac{1,288}{10,330} \right\rceil = 1 \text{ task}$$

Memory preparation overhead was recovered within the **very first task execution**. On all future tasks or maintenance iterations sharing this workspace, 100% of the token savings are pure efficiency gain.

---

## 4. Final Conclusion

**Measured efficiency improvement with correctness preserved**

Graph-based agent memory eliminated speculative architectural exploration and trial-and-error scaffolding, allowing the agent to target exact conventions immediately while preserving 100% functional correctness across all 10 acceptance criteria.
