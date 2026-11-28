-- Agro AI — Dataset Management, pgvector Hybrid RAG & External API Intelligence Migration
-- Target: PostgreSQL 15+ / Supabase (enable pgvector extension for semantic cosine search)

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS dataset_registry (
    id TEXT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(120) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    parent_dataset_id TEXT REFERENCES dataset_registry(id) ON DELETE SET NULL,
    file_format VARCHAR(30) NOT NULL,
    subject VARCHAR(60) NOT NULL DEFAULT 'general_agronomy',
    crop VARCHAR(100),
    region VARCHAR(120) NOT NULL DEFAULT 'India',
    language VARCHAR(20) NOT NULL DEFAULT 'en',
    source_name VARCHAR(200),
    publisher VARCHAR(200),
    source_url VARCHAR(500),
    original_publication_date VARCHAR(40),
    trust_level VARCHAR(40) NOT NULL DEFAULT 'unverified_upload',
    approval_status VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    ingestion_status VARCHAR(30) NOT NULL DEFAULT 'parsed',
    total_records INTEGER NOT NULL DEFAULT 0,
    valid_records INTEGER NOT NULL DEFAULT 0,
    duplicate_records INTEGER NOT NULL DEFAULT 0,
    invalid_records INTEGER NOT NULL DEFAULT 0,
    conflict_records INTEGER NOT NULL DEFAULT 0,
    stale_records INTEGER NOT NULL DEFAULT 0,
    schema_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    preview_rows JSONB NOT NULL DEFAULT '[]'::jsonb,
    staged_records JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    conflicts_detected JSONB NOT NULL DEFAULT '[]'::jsonb,
    review_notes TEXT,
    uploaded_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dataset_registry_slug ON dataset_registry(slug);
CREATE INDEX IF NOT EXISTS idx_dataset_registry_approval ON dataset_registry(approval_status);
CREATE INDEX IF NOT EXISTS idx_dataset_registry_crop ON dataset_registry(crop);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    dataset_id TEXT REFERENCES dataset_registry(id) ON DELETE CASCADE,
    knowledge_source_id TEXT REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    structured_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    subject VARCHAR(60) NOT NULL DEFAULT 'general_agronomy',
    crop VARCHAR(80),
    disease VARCHAR(120),
    state VARCHAR(80),
    district VARCHAR(80),
    season VARCHAR(40),
    language VARCHAR(20) NOT NULL DEFAULT 'en',
    source_name VARCHAR(200),
    publisher VARCHAR(200),
    source_url VARCHAR(500),
    publication_date VARCHAR(40),
    is_official BOOLEAN NOT NULL DEFAULT FALSE,
    trust_score DOUBLE PRECISION NOT NULL DEFAULT 0.65,
    embedding_vec JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding_pgvec vector(128),
    content_hash VARCHAR(64) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_crop_active ON knowledge_chunks(crop, is_active);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_disease ON knowledge_chunks(disease);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_state_lang ON knowledge_chunks(state, language);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts ON knowledge_chunks USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')));
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_pgvec ON knowledge_chunks USING hnsw (embedding_pgvec vector_cosine_ops);

CREATE TABLE IF NOT EXISTS external_api_call_logs (
    id TEXT PRIMARY KEY,
    provider_key VARCHAR(60) NOT NULL,
    endpoint_category VARCHAR(40) NOT NULL,
    http_status INTEGER,
    schema_valid BOOLEAN NOT NULL DEFAULT FALSE,
    freshness_status VARCHAR(30) NOT NULL DEFAULT 'UNAVAILABLE',
    latency_ms INTEGER,
    source_timestamp VARCHAR(50),
    error_code VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_external_api_logs_provider_created ON external_api_call_logs(provider_key, created_at DESC);

CREATE TABLE IF NOT EXISTS evidence_verification_logs (
    id TEXT PRIMARY KEY,
    channel VARCHAR(30) NOT NULL,
    request_id VARCHAR(64),
    crop VARCHAR(80),
    subject VARCHAR(60),
    evidence_status VARCHAR(40) NOT NULL,
    chunks_retrieved INTEGER NOT NULL DEFAULT 0,
    official_sources_count INTEGER NOT NULL DEFAULT 0,
    dataset_sources_count INTEGER NOT NULL DEFAULT 0,
    api_sources_count INTEGER NOT NULL DEFAULT 0,
    conflict_count INTEGER NOT NULL DEFAULT 0,
    stale_count INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_logs_channel_status ON evidence_verification_logs(channel, evidence_status, created_at DESC);
