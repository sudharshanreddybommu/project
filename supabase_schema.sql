-- ═══════════════════════════════════════════════════════
-- OPMD AI Detection Platform — Supabase Schema
-- Run this in: Supabase Dashboard > SQL Editor > New Query
-- ═══════════════════════════════════════════════════════

-- 1. PATIENTS table
CREATE TABLE IF NOT EXISTS patients (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password TEXT,
    name TEXT,
    phone TEXT,
    address TEXT,
    age INTEGER,
    is_verified INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. DOCTORS table
CREATE TABLE IF NOT EXISTS doctors (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password TEXT,
    name TEXT,
    phone TEXT,
    hospital TEXT,
    address TEXT,
    specialization TEXT,
    is_verified INTEGER DEFAULT 0,
    verification_status TEXT DEFAULT 'pending',
    hospital_id_doc TEXT,
    medical_cert_doc TEXT,
    degree_cert_doc TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. SCANS table
CREATE TABLE IF NOT EXISTS scans (
    id BIGSERIAL PRIMARY KEY,
    patient_id BIGINT NOT NULL REFERENCES patients(id),
    left_image TEXT,
    front_image TEXT,
    right_image TEXT,
    prediction TEXT,
    risk_level TEXT,
    suggestions TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. APPOINTMENTS table
CREATE TABLE IF NOT EXISTS appointments (
    id BIGSERIAL PRIMARY KEY,
    patient_id BIGINT NOT NULL REFERENCES patients(id),
    doctor_id BIGINT NOT NULL REFERENCES doctors(id),
    scan_id BIGINT REFERENCES scans(id),
    status TEXT DEFAULT 'pending',
    scheduled_date TIMESTAMPTZ,
    notes TEXT,
    patient_notified INTEGER DEFAULT 0,
    doctor_notified INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. NOTIFICATIONS table
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_type TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════
-- Disable Row Level Security (for backend-controlled access)
-- ═══════════════════════════════════════════════════════
ALTER TABLE patients DISABLE ROW LEVEL SECURITY;
ALTER TABLE doctors DISABLE ROW LEVEL SECURITY;
ALTER TABLE scans DISABLE ROW LEVEL SECURITY;
ALTER TABLE appointments DISABLE ROW LEVEL SECURITY;
ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;
