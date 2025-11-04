-- DDM Learning Journey Database Schema
-- PostgreSQL initialization script

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    ddm_student_id VARCHAR(50) UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token TEXT,
    verification_token_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_ddm_student_id ON users(ddm_student_id);

-- Email verification log
CREATE TABLE IF NOT EXISTS email_verifications (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    verification_token TEXT NOT NULL,
    verified_at TIMESTAMP,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Courses table
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    instructor VARCHAR(255),
    credits INTEGER NOT NULL,
    category VARCHAR(100),
    level VARCHAR(20),
    prerequisites TEXT[],
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(course_code);
CREATE INDEX IF NOT EXISTS idx_courses_status ON courses(status);

-- Course enrollments
CREATE TABLE IF NOT EXISTS course_enrollments (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    enrollment_date DATE DEFAULT CURRENT_DATE,
    completion_date DATE,
    status VARCHAR(20) DEFAULT 'enrolled',
    final_grade VARCHAR(10),
    credits_earned INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_enrollments_user ON course_enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course ON course_enrollments(course_id);

-- Credit transactions (learning journey credits)
CREATE TABLE IF NOT EXISTS credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    transaction_type VARCHAR(50) NOT NULL,
    credits_awarded INTEGER NOT NULL,
    description TEXT,
    awarded_date DATE DEFAULT CURRENT_DATE,
    approved_by VARCHAR(255),
    notes TEXT,
    certificate_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_credits_user ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credits_type ON credit_transactions(transaction_type);

-- Certificates
CREATE TABLE IF NOT EXISTS certificates (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    certificate_type VARCHAR(50) NOT NULL,
    course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    issue_date DATE DEFAULT CURRENT_DATE,
    certificate_number VARCHAR(50) UNIQUE NOT NULL,
    credential_url TEXT,
    digital_signature TEXT,
    pdf_url TEXT,
    status VARCHAR(20) DEFAULT 'valid',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_certificates_user ON certificates(user_id);
CREATE INDEX IF NOT EXISTS idx_certificates_number ON certificates(certificate_number);

-- Learning activities (query history, reading, etc.)
CREATE TABLE IF NOT EXISTS learning_activities (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    activity_data JSONB,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    credits_eligible BOOLEAN DEFAULT FALSE,
    credits_awarded INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_activities_user ON learning_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_activities_type ON learning_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_activities_date ON learning_activities(completed_at);

-- Query history (enhanced with user tracking)
CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    answer_summary TEXT,
    helpful BOOLEAN,
    bookmarked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_user ON query_history(user_id);
CREATE INDEX IF NOT EXISTS idx_query_date ON query_history(created_at);

-- Quiz results
CREATE TABLE IF NOT EXISTS quiz_results (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    quiz_type VARCHAR(100),
    score INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    reference_chunks TEXT[],
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quiz_user ON quiz_results(user_id);

-- Reading progress
CREATE TABLE IF NOT EXISTS reading_progress (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    book_isbn VARCHAR(20),
    progress_percent INTEGER CHECK (progress_percent >= 0 AND progress_percent <= 100),
    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_isbn)
);

CREATE INDEX IF NOT EXISTS idx_reading_user ON reading_progress(user_id);

-- Event attendance
CREATE TABLE IF NOT EXISTS event_attendance (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    event_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'registered',
    notes TEXT,
    attended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attendance_user ON event_attendance(user_id);

-- View: User credit summary
CREATE OR REPLACE VIEW user_credit_summary AS
SELECT
    user_id,
    SUM(credits_awarded) as total_credits,
    COUNT(DISTINCT course_id) as courses_completed,
    MAX(awarded_date) as last_credit_date
FROM credit_transactions
WHERE transaction_type = 'course_completion'
GROUP BY user_id;

-- View: User learning stats
CREATE OR REPLACE VIEW user_learning_stats AS
SELECT
    u.id as user_id,
    u.email,
    u.full_name,
    COALESCE(cs.total_credits, 0) as total_credits,
    COALESCE(cs.courses_completed, 0) as courses_completed,
    COUNT(DISTINCT qh.id) as total_queries,
    COUNT(DISTINCT qz.id) as quizzes_completed,
    COUNT(DISTINCT rp.id) as books_reading,
    COUNT(DISTINCT ea.id) as events_attended
FROM users u
LEFT JOIN user_credit_summary cs ON u.id = cs.user_id
LEFT JOIN query_history qh ON u.id = qh.user_id
LEFT JOIN quiz_results qz ON u.id = qz.user_id
LEFT JOIN reading_progress rp ON u.id = rp.user_id
LEFT JOIN event_attendance ea ON u.id = ea.user_id AND ea.attended_at IS NOT NULL
GROUP BY u.id, u.email, u.full_name, cs.total_credits, cs.courses_completed;

-- Insert sample courses
INSERT INTO courses (course_code, title, description, credits, category, level, status) VALUES
('BUD101', '佛學概論', '佛教基本教義與歷史概述，適合初學者認識佛法基礎', 3, '基礎佛學', '初級', 'active'),
('ZEN101', '禪修入門', '學習基本禪坐方法與正念練習', 3, '禪修實踐', '初級', 'active'),
('MED201', '正念禪修進階', '深入探討正念覺察與日常生活應用', 4, '禪修實踐', '中級', 'active'),
('BUD201', '四聖諦與八正道', '深入研讀佛教核心教義', 4, '基礎佛學', '中級', 'active'),
('ZEN202', '默照禪指導', '學習默照禪法與實修指導', 4, '禪修實踐', '中級', 'active')
ON CONFLICT (course_code) DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for courses table
CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ddm_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ddm_user;
