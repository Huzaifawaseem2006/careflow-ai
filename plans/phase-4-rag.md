# Phase 4 — approved knowledge and RAG

Entry: Phase 3 gate passes; resolve D06 and corpus ownership. Start with small, reviewed synthetic documents only. Implement immutable versioned approval/effective dates, deterministic parsing/chunking, embeddings and pgvector filtering. No model-issued SQL or arbitrary remote ingestion.

Retrieval slices: corpus fixture and version tests, metadata filtering, source link/citation assembly, abstention on missing/conflicting/expired evidence, then answer generation. Recheck source status at response time. Booking availability and personal records stay in domain tools, never RAG.

Run retrieval recall tests independent of answer tests, source approval/version/access checks, injection and missing-evidence cases, and targeted model-backed eval when available. Compare with baseline and record corpus/index versions. Full applicable regression at exit; invalid citations or critical injection outcomes block demo.
