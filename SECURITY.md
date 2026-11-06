# Security and research boundaries

RAGLab is a local, single-user research application. It is not an authenticated public multi-tenant service. Bind native servers to loopback for a faculty demo. Before public exposure, add authentication, authorization, tenant isolation, rate limits, TLS and operational backups. Do not assume CORS is authentication.

The API rejects oversized aggregate and streaming bodies, disguised binary text, invalid extensions and control-character filenames. PDF extraction is isolated in a resource-limited subprocess (two active parsers, timeout, page/text/decoded-stream caps and a Linux memory limit). These controls reduce resource risk; they do not make native PDF parsing a general-purpose security sandbox. Keep Python/PyMuPDF dependencies patched. No OCR or execution of uploaded content is provided.

Explicit browser write-origin checks reject untrusted origins. Local programmatic clients without Origin remain allowed. Provider credentials stay in server environment variables; health responses expose only safe configuration, never keys or provider error bodies. A reachable model list is not a successful generation test. Automatic generation retries default to zero and are limited to bounded explicit 429 responses when enabled.

Human evidence and answer reviews require explicit self-attestation; reviewer names are not authenticated identities. Edits revoke evidence approval, rejected questions never enter experiments, imports reset review flags, and review events append at the API level. A local administrator can still modify SQLite directly; this is not a cryptographically tamper-proof audit log or a guarantee of scientifically correct labels.

Generated answers require verifiable source IDs and exact quotes. This establishes citation provenance, not semantic entailment. No automatic semantic correctness or groundedness score is invented. Human answer judgments are explicitly attributed and separated from immutable automated measurements. Provisional samples cannot establish superiority, and repeated queries are not independent research questions.

Private source text, extracted pages, references and reviewer attribution may be present in explicit PDF/CSV/JSON exports. Inspect exports before sharing. Spreadsheet formula prefixes are escaped in CSV; JSON preserves original text. Never commit .env, keys, private uploads, runtime databases, generated vectors/indexes or model weights. The staged-file audit checks recognized secrets, prohibited paths and large blobs, but is not a guarantee that every possible secret format is detected.

Report vulnerabilities privately to the repository owner through an appropriate private channel. Do not include credentials, private PDFs or extracted passages in public issues.
