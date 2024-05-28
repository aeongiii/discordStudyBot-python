-- 멤버 기본정보
CREATE TABLE member (
    member_id SERIAL PRIMARY KEY,
    member_nickname VARCHAR(255) NOT NULL,
    member_username VARCHAR(255) NOT NULL,
    member_join_date DATE NOT NULL
);

-- 멤버의 재참여 정보
CREATE TABLE membership_period (
    period_id SERIAL PRIMARY KEY,
    member_id INT NOT NULL,
    period_start_date DATE NOT NULL,
    period_end_date DATE,
    period_now_active BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (member_id) REFERENCES member(member_id)
);

-- 세션별(카메라 온오프) 공부 기록
CREATE TABLE study_session (
    session_id SERIAL PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    session_start_time TIMESTAMP NOT NULL,
    session_end_time TIMESTAMP,
    session_duration INT NOT NULL DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 일별 공부 기록
CREATE TABLE activity_log (
    log_id SERIAL PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    log_date DATE NOT NULL,
    log_message_count INT NOT NULL DEFAULT 0,
    log_study_time INT NOT NULL,
    log_login_count INT NOT NULL DEFAULT 0,
    log_attendance BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 휴가 기록
CREATE TABLE vacation_log (
    vacation_id SERIAL PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    vacation_date DATE NOT NULL,
    vacation_week_start DATE NOT NULL,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 멤버별 활동 시간대
CREATE TABLE behavioral_segment (
    segment_id SERIAL PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    segment_active_hour VARCHAR(50) NOT NULL,
    segment_active_period VARCHAR(50) NOT NULL CHECK (segment_active_period IN ('Day', 'Night')),
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 이탈률 예측
CREATE TABLE churn_prediction (
    prediction_id SERIAL PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    prediction_date DATE NOT NULL,
    prediction_absence_count INT NOT NULL,
    prediction_risk_level VARCHAR(50) NOT NULL CHECK (prediction_risk_level IN ('Low', 'Moderate', 'High')),
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);
