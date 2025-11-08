-- PostgreSQL DDL for enterprise.lookup_requests table and temp_id_sequence
--
-- This table provides asynchronous queue processing for EQC company lookups that
-- exceed the synchronous budget limit. Supports atomic dequeue operations with
-- FOR UPDATE SKIP LOCKED pattern for multi-worker scenarios.
--
-- Schema: enterprise
-- Primary Key: Serial ID for efficient queue operations
-- Performance: Status-based index for fast queue processing, normalized_name index for duplicate detection

-- Create enterprise schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS enterprise;

-- Drop tables if exist (for clean reinstalls)
DROP TABLE IF EXISTS enterprise.lookup_requests;
DROP TABLE IF EXISTS enterprise.temp_id_sequence;

-- Create the lookup requests queue table
CREATE TABLE enterprise.lookup_requests (
    -- Primary key
    id SERIAL PRIMARY KEY,

    -- Company identification fields
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,

    -- Queue processing fields
    status VARCHAR(20) DEFAULT 'pending' NOT NULL CHECK (
        status IN ('pending', 'processing', 'done', 'failed')
    ),
    attempts INTEGER DEFAULT 0 NOT NULL CHECK (attempts >= 0),
    last_error TEXT,

    -- Audit trail
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Create temporary ID sequence table for atomic TEMP_* ID generation
-- MIGRATION NOTE: For existing deployments, run:
-- ALTER TABLE enterprise.temp_id_sequence RENAME COLUMN id TO last_number;
-- ALTER TABLE enterprise.temp_id_sequence ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();
-- UPDATE enterprise.temp_id_sequence SET updated_at = now();
-- INSERT INTO enterprise.temp_id_sequence (last_number, updated_at)
-- SELECT 0, now() WHERE NOT EXISTS (SELECT 1 FROM enterprise.temp_id_sequence);
CREATE TABLE enterprise.temp_id_sequence (
    last_number INTEGER DEFAULT 0 NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Seed initial sequence row to keep UPDATE...RETURNING stable
INSERT INTO enterprise.temp_id_sequence (last_number)
SELECT 0
WHERE NOT EXISTS (SELECT 1 FROM enterprise.temp_id_sequence);

-- Performance indexes for queue processing operations
-- Status-based index for atomic dequeue operations (pending -> processing)
CREATE INDEX idx_lookup_requests_status_created
ON enterprise.lookup_requests (status, created_at ASC)
WHERE status IN ('pending', 'processing');

-- Normalized name index for duplicate detection and conflict resolution
CREATE INDEX idx_lookup_requests_normalized_name
ON enterprise.lookup_requests (normalized_name);

-- Status transitions index for monitoring and retry logic
CREATE INDEX idx_lookup_requests_status_attempts
ON enterprise.lookup_requests (status, attempts, updated_at DESC);

-- Created timestamp for queue age monitoring
CREATE INDEX idx_lookup_requests_created_at
ON enterprise.lookup_requests (created_at DESC);

-- Add table comments for documentation
COMMENT ON TABLE enterprise.lookup_requests IS
'Asynchronous queue for EQC company lookups that exceed synchronous budget limits. Supports atomic FOR UPDATE SKIP LOCKED processing for multi-worker scenarios.';

COMMENT ON COLUMN enterprise.lookup_requests.name IS
'Original company name to lookup via EQC API';

COMMENT ON COLUMN enterprise.lookup_requests.normalized_name IS
'Normalized version of name for duplicate detection and consistency';

COMMENT ON COLUMN enterprise.lookup_requests.status IS
'Queue processing status: pending (queued), processing (locked by worker), done (successfully processed), failed (permanent failure)';

COMMENT ON COLUMN enterprise.lookup_requests.attempts IS
'Number of processing attempts (for retry logic and failure tracking)';

COMMENT ON COLUMN enterprise.lookup_requests.last_error IS
'Last error message from failed processing attempt';

COMMENT ON COLUMN enterprise.lookup_requests.created_at IS
'Request creation timestamp for queue age tracking';

COMMENT ON COLUMN enterprise.lookup_requests.updated_at IS
'Last status update timestamp for monitoring and debugging';

COMMENT ON TABLE enterprise.temp_id_sequence IS
'Atomic sequence for generating temporary company IDs (TEMP_000001 format). Uses UPDATE...RETURNING for thread-safe increments.';

-- Grant appropriate permissions (adjust based on actual user roles)
-- GRANT SELECT ON enterprise.lookup_requests TO read_only_role;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON enterprise.lookup_requests TO etl_role;
-- GRANT SELECT, UPDATE ON enterprise.temp_id_sequence TO etl_role;