-- PostgreSQL DDL for enterprise.company_mapping table
--
-- This table replaces the legacy 5-layer COMPANY_ID mapping structure
-- (COMPANY_ID1-5_MAPPING) with a unified, priority-based lookup system
-- that maintains 100% backward compatibility with existing logic.
--
-- Schema: enterprise
-- Primary Key: Compound key (alias_name, match_type) allows same alias
--              across different match types while preventing duplicates
-- Performance: Priority-based index for fast resolution queries (<100ms)

-- Create enterprise schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS enterprise;

-- Drop table if exists (for clean reinstalls)
DROP TABLE IF EXISTS enterprise.company_mapping;

-- Create the unified company mapping table
CREATE TABLE enterprise.company_mapping (
    -- Compound primary key fields
    alias_name VARCHAR(255) NOT NULL,
    canonical_id VARCHAR(50) NOT NULL,

    -- Classification fields
    source VARCHAR(20) DEFAULT 'internal' NOT NULL,
    match_type VARCHAR(20) NOT NULL CHECK (
        match_type IN ('plan', 'account', 'hardcode', 'name', 'account_name')
    ),
    priority INTEGER NOT NULL CHECK (priority >= 1 AND priority <= 5),

    -- Audit trail
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,

    -- Compound primary key (allows same alias across different match types)
    PRIMARY KEY (alias_name, match_type)
);

-- Performance indexes for fast company ID resolution
-- Priority-based index for the main resolution query path
CREATE INDEX idx_company_mapping_priority_lookup
ON enterprise.company_mapping (priority ASC, match_type, alias_name);

-- Individual match_type lookups for targeted searches
CREATE INDEX idx_company_mapping_match_type
ON enterprise.company_mapping (match_type, alias_name);

-- Canonical ID reverse lookup (for audit/debugging)
CREATE INDEX idx_company_mapping_canonical_id
ON enterprise.company_mapping (canonical_id);

-- Updated timestamp for incremental processing
CREATE INDEX idx_company_mapping_updated_at
ON enterprise.company_mapping (updated_at DESC);

-- Add table comments for documentation
COMMENT ON TABLE enterprise.company_mapping IS
'Unified company ID mapping table replacing legacy 5-layer COMPANY_ID1-5_MAPPING structure. Provides priority-based company ID resolution with exact backward compatibility.';

COMMENT ON COLUMN enterprise.company_mapping.alias_name IS
'Source identifier (plan code, account number, customer name, etc.) used for lookup';

COMMENT ON COLUMN enterprise.company_mapping.canonical_id IS
'Target company_id that the alias_name resolves to - typically 9-digit numeric string';

COMMENT ON COLUMN enterprise.company_mapping.source IS
'Data source identifier - currently always "internal" for legacy mappings';

COMMENT ON COLUMN enterprise.company_mapping.match_type IS
'Mapping category: plan=1, account=2, hardcode=3, name=4, account_name=5 (priority order)';

COMMENT ON COLUMN enterprise.company_mapping.priority IS
'Search priority (1=highest) matching legacy _update_company_id precedence order';

COMMENT ON COLUMN enterprise.company_mapping.updated_at IS
'Record update timestamp for audit trail and incremental processing';

-- Grant appropriate permissions (adjust based on actual user roles)
-- GRANT SELECT ON enterprise.company_mapping TO read_only_role;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON enterprise.company_mapping TO etl_role;