-- Migration: Learning Journey System
-- Description: Add tables for quiz history, learning sessions, event attendance, master comments, and achievements
-- Date: 2025-11-04

-- Table 1: Quiz Attempts (store all quiz history)
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id SERIAL PRIMARY KEY,
    quiz_id VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,

    -- Quiz content snapshot
    source_query TEXT NOT NULL,
    reference_chunk_title VARCHAR(500),
    reference_chunk_id VARCHAR(200),
    questions JSONB NOT NULL,
    answers JSONB NOT NULL,

    -- Evaluation results
    evaluations JSONB NOT NULL,
    total_score INTEGER NOT NULL,
    max_score INTEGER NOT NULL,
    percentage DECIMAL(5,2) NOT NULL,
    overall_grade VARCHAR(20) NOT NULL,  -- 優秀/良好/及格/需加強
    overall_feedback TEXT,
    zen_master_response TEXT,

    -- Time tracking
    time_spent_seconds INTEGER DEFAULT 0,
    computation_time DECIMAL(10,6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    CONSTRAINT quiz_attempts_user_email_idx UNIQUE (user_email, quiz_id, created_at)
);

CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_email ON quiz_attempts(user_email);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_id ON quiz_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_created_at ON quiz_attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_percentage ON quiz_attempts(percentage);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_overall_grade ON quiz_attempts(overall_grade);

-- Table 2: Learning Sessions (track reading/study time)
CREATE TABLE IF NOT EXISTS learning_sessions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,

    -- Session details
    session_type VARCHAR(50) NOT NULL,  -- 'query', 'reading_answer', 'reading_sources', 'quiz'
    query_text TEXT,
    reference_id VARCHAR(200),

    -- Time tracking
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds INTEGER,

    -- Activity metadata
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_user_email ON learning_sessions(user_email);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_user_id ON learning_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_session_type ON learning_sessions(session_type);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_start_time ON learning_sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_created_at ON learning_sessions(created_at);

-- Table 3: Event Attendance
CREATE TABLE IF NOT EXISTS event_attendance (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,

    -- Event details
    event_id VARCHAR(100) NOT NULL,
    event_title VARCHAR(500) NOT NULL,
    event_category VARCHAR(100),  -- 禪修營、講座、共修等
    event_location VARCHAR(500),
    event_date DATE NOT NULL,
    event_duration_hours DECIMAL(4,1),

    -- Attendance verification
    attendance_status VARCHAR(50) DEFAULT 'pending',  -- pending, verified, rejected
    verification_code VARCHAR(100),
    verified_by VARCHAR(255),
    verified_at TIMESTAMP,

    -- User notes
    user_notes TEXT,
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_attendance_user_email ON event_attendance(user_email);
CREATE INDEX IF NOT EXISTS idx_event_attendance_user_id ON event_attendance(user_id);
CREATE INDEX IF NOT EXISTS idx_event_attendance_event_date ON event_attendance(event_date);
CREATE INDEX IF NOT EXISTS idx_event_attendance_status ON event_attendance(attendance_status);
CREATE INDEX IF NOT EXISTS idx_event_attendance_created_at ON event_attendance(created_at);

-- Table 4: Master Comments
CREATE TABLE IF NOT EXISTS master_comments (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,

    -- Comment details
    comment_type VARCHAR(50) NOT NULL,  -- 'milestone', 'encouragement', 'enlightenment', 'achievement'
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,

    -- Trigger conditions
    trigger_type VARCHAR(100),  -- 'quiz_count', 'study_hours', 'event_attendance', 'score_improvement', 'manual'
    trigger_value JSONB,

    -- Master info
    master_name VARCHAR(100) DEFAULT '聖嚴法師',
    is_ai_generated BOOLEAN DEFAULT true,

    -- Status
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_master_comments_user_email ON master_comments(user_email);
CREATE INDEX IF NOT EXISTS idx_master_comments_user_id ON master_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_master_comments_is_read ON master_comments(is_read);
CREATE INDEX IF NOT EXISTS idx_master_comments_created_at ON master_comments(created_at);
CREATE INDEX IF NOT EXISTS idx_master_comments_trigger_type ON master_comments(trigger_type);

-- Table 5: User Achievements
CREATE TABLE IF NOT EXISTS user_achievements (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,

    achievement_type VARCHAR(100) NOT NULL,
    achievement_name VARCHAR(200) NOT NULL,
    achievement_description TEXT,
    achievement_icon VARCHAR(100),  -- Emoji or icon class

    -- Progress tracking
    current_value INTEGER DEFAULT 0,
    target_value INTEGER,
    is_completed BOOLEAN DEFAULT false,
    completed_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure one achievement per user per type
    CONSTRAINT unique_user_achievement UNIQUE (user_email, achievement_type)
);

CREATE INDEX IF NOT EXISTS idx_user_achievements_user_email ON user_achievements(user_email);
CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_type ON user_achievements(achievement_type);
CREATE INDEX IF NOT EXISTS idx_user_achievements_completed ON user_achievements(is_completed);

-- Insert default achievements for all existing users
INSERT INTO user_achievements (user_email, achievement_type, achievement_name, achievement_description, achievement_icon, target_value)
SELECT
    email,
    achievement_type,
    achievement_name,
    achievement_description,
    achievement_icon,
    target_value
FROM users
CROSS JOIN (
    VALUES
        ('first_quiz', '初試啼聲', '完成第一次測驗', '🎓', 1),
        ('quiz_count_10', '十度圓滿', '完成10次測驗', '📚', 10),
        ('quiz_count_50', '半百之路', '完成50次測驗', '🎯', 50),
        ('quiz_count_100', '百尺竿頭', '完成100次測驗', '🏆', 100),
        ('study_hours_10', '勤學不倦', '累積學習10小時', '⏰', 10),
        ('study_hours_50', '精進修行', '累積學習50小時', '📖', 50),
        ('study_hours_100', '百小時修持', '累積學習100小時', '🌟', 100),
        ('first_event', '解行並重', '參加第一場實體活動', '🏮', 1),
        ('event_count_10', '十度參與', '參加10場實體活動', '🎋', 10),
        ('perfect_score', '心領神會', '獲得一次滿分', '💯', 1),
        ('perfect_score_3', '三次滿分', '獲得三次滿分', '⭐', 3),
        ('avg_score_80', '學有所成', '平均分數達80分', '📈', 80),
        ('consecutive_days_7', '七日精進', '連續7天學習', '🔥', 7),
        ('consecutive_days_30', '月月不輟', '連續30天學習', '💪', 30)
) AS achievements(achievement_type, achievement_name, achievement_description, achievement_icon, target_value)
ON CONFLICT (user_email, achievement_type) DO NOTHING;

-- Function: Update achievement progress
CREATE OR REPLACE FUNCTION update_achievement_progress(
    p_user_email VARCHAR,
    p_achievement_type VARCHAR,
    p_current_value INTEGER
) RETURNS VOID AS $$
BEGIN
    UPDATE user_achievements
    SET
        current_value = p_current_value,
        is_completed = (p_current_value >= target_value),
        completed_at = CASE
            WHEN p_current_value >= target_value AND completed_at IS NULL
            THEN CURRENT_TIMESTAMP
            ELSE completed_at
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_email = p_user_email
      AND achievement_type = p_achievement_type;
END;
$$ LANGUAGE plpgsql;

-- Function: Check and trigger master comments
CREATE OR REPLACE FUNCTION check_master_comment_triggers(
    p_user_email VARCHAR
) RETURNS TABLE (
    trigger_type VARCHAR,
    title VARCHAR,
    content TEXT,
    trigger_value JSONB
) AS $$
DECLARE
    quiz_count INTEGER;
    total_hours DECIMAL;
    verified_events INTEGER;
    avg_score DECIMAL;
BEGIN
    -- Get user statistics
    SELECT COUNT(*) INTO quiz_count FROM quiz_attempts WHERE user_email = p_user_email;
    SELECT COALESCE(SUM(duration_seconds) / 3600.0, 0) INTO total_hours FROM learning_sessions WHERE user_email = p_user_email;
    SELECT COUNT(*) INTO verified_events FROM event_attendance WHERE user_email = p_user_email AND attendance_status = 'verified';
    SELECT COALESCE(AVG(percentage), 0) INTO avg_score FROM quiz_attempts WHERE user_email = p_user_email;

    -- Check triggers and return suggestions (don't auto-create comments here)
    IF quiz_count = 1 THEN
        RETURN QUERY SELECT
            'first_quiz'::VARCHAR,
            '初發心，可貴也'::VARCHAR,
            '歡迎你開始學習佛法的旅程！記住「不怕念起，只怕覺遲」，保持覺察，持續精進。'::TEXT,
            jsonb_build_object('quiz_count', quiz_count);
    END IF;

    IF quiz_count = 10 THEN
        RETURN QUERY SELECT
            'quiz_milestone_10'::VARCHAR,
            '十度圓滿'::VARCHAR,
            '完成10次測驗，展現了學習的毅力。記住，學佛如同爬山，一步一腳印，莫急莫躁。'::TEXT,
            jsonb_build_object('quiz_count', quiz_count);
    END IF;

    IF quiz_count = 100 THEN
        RETURN QUERY SELECT
            'quiz_milestone_100'::VARCHAR,
            '百尺竿頭，更進一步'::VARCHAR,
            '恭喜你完成了第100次測驗！然而，切記「所知障」- 不要執著於知識的累積，更要將所學化為生活中的智慧與慈悲。'::TEXT,
            jsonb_build_object('quiz_count', quiz_count);
    END IF;

    IF total_hours >= 50 AND NOT EXISTS (
        SELECT 1 FROM master_comments
        WHERE user_email = p_user_email AND trigger_type = 'study_hours_50'
    ) THEN
        RETURN QUERY SELECT
            'study_hours_50'::VARCHAR,
            '精進不懈，值得嘉許'::VARCHAR,
            '看到你持續精進學習，已累積50小時的學習時光。記住，修行如同磨鏡，日日拂拭，方能明心見性。繼續保持這份精進之心！'::TEXT,
            jsonb_build_object('total_hours', total_hours);
    END IF;

    IF verified_events = 1 THEN
        RETURN QUERY SELECT
            'first_event'::VARCHAR,
            '解行並重，方為正道'::VARCHAR,
            '看到你不只在線上學習佛法，更實際參與禪修活動，這正是「解行並重」的體現。理論與實踐相輔相成，才能真正走在覺悟的道路上。'::TEXT,
            jsonb_build_object('verified_events', verified_events);
    END IF;

    RETURN;
END;
$$ LANGUAGE plpgsql;

-- Comment for documentation
COMMENT ON TABLE quiz_attempts IS 'Stores complete history of user quiz attempts with questions, answers, and evaluations';
COMMENT ON TABLE learning_sessions IS 'Tracks user learning time across different activities (reading, quiz, etc.)';
COMMENT ON TABLE event_attendance IS 'Records user attendance at offline events with verification status';
COMMENT ON TABLE master_comments IS 'Stores personalized messages/enlightenment from masters triggered by achievements';
COMMENT ON TABLE user_achievements IS 'Tracks user progress towards various learning milestones and badges';
