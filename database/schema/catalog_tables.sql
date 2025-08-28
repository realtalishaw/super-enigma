-- Catalog System Database Schema
-- This schema provides tables for storing provider, action, and trigger information

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Toolkit categories table
CREATE TABLE IF NOT EXISTS toolkit_categories (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Toolkits table (providers)
CREATE TABLE IF NOT EXISTS toolkits (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES toolkit_categories(id),
    icon_url TEXT,
    website_url TEXT,
    auth_scheme JSONB,
    rate_limits JSONB,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Toolkit authentication schemes
CREATE TABLE IF NOT EXISTS toolkit_auth_schemes (
    id SERIAL PRIMARY KEY,
    toolkit_id INTEGER REFERENCES toolkits(id) ON DELETE CASCADE,
    scheme_type VARCHAR(50) NOT NULL, -- 'oauth2', 'api_key', 'basic', etc.
    scheme_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tools table (actions and triggers)
CREATE TABLE IF NOT EXISTS tools (
    id SERIAL PRIMARY KEY,
    toolkit_id INTEGER REFERENCES toolkits(id) ON DELETE CASCADE,
    slug VARCHAR(100) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    tool_type VARCHAR(20) NOT NULL CHECK (tool_type IN ('action', 'trigger')),
    input_schema JSONB,
    output_schema JSONB,
    examples JSONB,
    rate_limits JSONB,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(toolkit_id, slug)
);

-- Tool parameters
CREATE TABLE IF NOT EXISTS tool_parameters (
    id SERIAL PRIMARY KEY,
    tool_id INTEGER REFERENCES tools(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    parameter_type VARCHAR(50) NOT NULL,
    required BOOLEAN DEFAULT false,
    default_value TEXT,
    description TEXT,
    validation_rules JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tool returns
CREATE TABLE IF NOT EXISTS tool_returns (
    id SERIAL PRIMARY KEY,
    tool_id INTEGER REFERENCES tools(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    return_type VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tool examples
CREATE TABLE IF NOT EXISTS tool_examples (
    id SERIAL PRIMARY KEY,
    tool_id INTEGER REFERENCES tools(id) ON DELETE CASCADE,
    title VARCHAR(200),
    description TEXT,
    input_example JSONB,
    output_example JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Toolkit rate limits
CREATE TABLE IF NOT EXISTS toolkit_rate_limits (
    id SERIAL PRIMARY KEY,
    toolkit_id INTEGER REFERENCES toolkits(id) ON DELETE CASCADE,
    limit_type VARCHAR(50) NOT NULL, -- 'requests_per_minute', 'requests_per_hour', etc.
    limit_value INTEGER NOT NULL,
    window_size INTEGER NOT NULL, -- in seconds
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Catalog snapshots for versioning
CREATE TABLE IF NOT EXISTS catalog_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    toolkit_count INTEGER DEFAULT 0,
    tool_count INTEGER DEFAULT 0,
    category_count INTEGER DEFAULT 0,
    metadata JSONB
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_toolkits_category_id ON toolkits(category_id);
CREATE INDEX IF NOT EXISTS idx_tools_toolkit_id ON tools(toolkit_id);
CREATE INDEX IF NOT EXISTS idx_tools_type ON tools(tool_type);
CREATE INDEX IF NOT EXISTS idx_tool_parameters_tool_id ON tool_parameters(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_returns_tool_id ON tool_returns(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_examples_tool_id ON tool_examples(tool_id);

-- Insert default categories
INSERT INTO toolkit_categories (slug, name, description, display_order) VALUES
    ('collaboration', 'Collaboration & Communication', 'Team communication and collaboration tools', 1),
    ('productivity', 'Productivity & Project Management', 'Tools for managing projects and increasing productivity', 2),
    ('crm', 'Customer Relationship Management', 'Tools for managing customer relationships and sales', 3),
    ('marketing', 'Marketing & Social Media', 'Marketing automation and social media management', 4),
    ('developer', 'Developer Tools & DevOps', 'Development, deployment, and operations tools', 5),
    ('finance', 'Finance & Accounting', 'Financial management and accounting tools', 6),
    ('ecommerce', 'E-commerce & Retail', 'Online selling and retail management tools', 7),
    ('analytics', 'Analytics & Data', 'Data analysis and business intelligence tools', 8),
    ('design', 'Design & Creative', 'Design, creative, and multimedia tools', 9),
    ('other', 'Other & Miscellaneous', 'Other tools and integrations', 10)
ON CONFLICT (slug) DO NOTHING;
