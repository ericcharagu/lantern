-- =============================================================================
-- Lantern Platform - Full Database Initialization Script for PostgreSQL
-- =============================================================================
-- This script creates all necessary tables, indexes, and constraints for the
-- entire application. It is designed to be run once to set up a new database.
-- It is idempotent, using 'CREATE TABLE IF NOT EXISTS'.
-- =============================================================================

-- Best practice: Create a dedicated schema to keep the database organized.
CREATE SCHEMA IF NOT EXISTS lantern_app;

-- Set the search path to our new schema for the current session.
-- All subsequent commands will operate within this schema.
SET search_path TO lantern_app;

-- =============================================================================
-- Table: users
-- Stores user account information for authentication and access control.
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    last_login TIMESTAMPTZ
);

-- Add comments for clarity
COMMENT ON TABLE users IS 'Stores user accounts, credentials, and role information for authentication.';
COMMENT ON COLUMN users.id IS 'Unique identifier for the user.';
COMMENT ON COLUMN users.username IS 'Unique username for login.';
COMMENT ON COLUMN users.password_hash IS 'Hashed password for security (using passlib/bcrypt).';
COMMENT ON COLUMN users.is_active IS 'Flags if the user account is enabled or disabled.';
COMMENT ON COLUMN users.created_at IS 'UTC timestamp of when the user account was created.';
COMMENT ON COLUMN users.last_login IS 'UTC timestamp of the user''s last successful login.';

-- Create indexes to speed up login and lookups.
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);


-- =============================================================================
-- Table: detection_logs
-- Stores every individual object detection event from all camera feeds.
-- This is a high-volume table and is indexed for performance.
-- =============================================================================
CREATE TABLE IF NOT EXISTS detection_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    camera_name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    object_name VARCHAR(50) NOT NULL,
    confidence REAL NOT NULL,
    box_x1 REAL NOT NULL,
    box_y1 REAL NOT NULL,
    box_x2 REAL NOT NULL,
    box_y2 REAL NOT NULL
);

-- Add comments for clarity
COMMENT ON TABLE detection_logs IS 'Stores individual object detection events from all cameras. This is a high-volume table.';
COMMENT ON COLUMN detection_logs.id IS 'Unique identifier for each detection event.';
COMMENT ON COLUMN detection_logs.timestamp IS 'The exact UTC timestamp when the detection occurred.';
COMMENT ON COLUMN detection_logs.camera_name IS 'The name of the camera that captured the detection.';
COMMENT ON COLUMN detection_logs.object_name IS 'The class name of the detected object (e.g., ''person'').';
COMMENT ON COLUMN detection_logs.confidence IS 'The confidence score (0.0 to 1.0) from the YOLO model.';
COMMENT ON COLUMN detection_logs.box_x1 IS 'Bounding box top-left x-coordinate.';
COMMENT ON COLUMN detection_logs.box_y1 IS 'Bounding box top-left y-coordinate.';
COMMENT ON COLUMN detection_logs.box_x2 IS 'Bounding box bottom-right x-coordinate.';
COMMENT ON COLUMN detection_logs.box_y2 IS 'Bounding box bottom-right y-coordinate.';

-- Create indexes for performance-critical queries.
-- Composite index for the nightly report (most important query).
CREATE INDEX IF NOT EXISTS idx_detection_logs_object_name_timestamp ON detection_logs (object_name, timestamp DESC);
-- Index for filtering by camera.
CREATE INDEX IF NOT EXISTS idx_detection_logs_camera_name ON detection_logs (camera_name);
-- Index for general time-based queries.
CREATE INDEX IF NOT EXISTS idx_detection_logs_timestamp ON detection_logs (timestamp DESC);


-- =============================================================================
-- End of Script
-- =============================================================================