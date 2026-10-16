# Security & Data Isolation Policy

## 1. Threat Model & Mitigations

### 1.1 Secret & Credential Ingestion
**Risk**: AI agents unintentionally capturing API keys, JWT tokens, AWS credentials, or passwords into graph memory nodes.
**Mitigation**:
- Strict pattern matching and heuristic scanners detect high-entropy strings, known token formats (`sk_live_`, `ghp_`, `Bearer`, `BEGIN PRIVATE KEY`), and password fields.
- Content containing identified secrets is rejected prior to database ingestion.
- Agents are explicitly instructed in `.github/copilot-instructions.md` never to pass secrets.

### 1.2 Cypher Injection
**Risk**: Malicious agent input containing quotes or Cypher clauses executing arbitrary graph queries.
**Mitigation**:
- All Cypher queries use parameterized inputs (`$param`).
- No raw string interpolation or query concatenation is permitted in repository methods.
- Arbitrary Cypher execution is strictly prohibited through the MCP interface; only bounded, domain-specific tools are exposed.

### 1.3 Cross-Workspace Data Leakage
**Risk**: Agent A working in Project Alpha retrieving confidential architectural memories from Project Beta.
**Mitigation**:
- Strict multi-tenancy enforced at the service and query layer via `workspace_id`.
- Every Cypher traversal and search query constrains both start nodes and traversal edges to the requester's `workspace_id`.
- Default workspace configuration is isolated to local scope unless explicitly assigned.

### 1.4 Network Exposure
**Risk**: Unauthorized access to FalkorDB database port over local area networks or public interfaces.
**Mitigation**:
- FalkorDB Docker container is bound strictly to `127.0.0.1:6379`.
- No external `0.0.0.0` bindings are used.
- Production multi-node configurations require Redis ACL authentication (`users.acl`).

---

## 2. Authentication & Authorization

### Development Mode (Localhost)
- Authenticates through local process boundary and environment variables.
- One trusted local user per session.

### Multi-Agent Remote Deployment
- MCP connections authenticate via token/header authentication or mutual TLS.
- Workspace authorization tokens restrict agents to explicit workspace permissions (`READ`, `WRITE`, `ADMIN`).
