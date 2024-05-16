-- 데이터베이스를 UTF-8로 설정
ALTER DATABASE study_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 기존 테이블을 UTF-8로 변경
ALTER TABLE member CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 멤버 기본정보
CREATE TABLE member (
    member_id INT AUTO_INCREMENT PRIMARY KEY,
    member_nickname VARCHAR(255) NOT NULL,
    member_username VARCHAR(255) NOT NULL,
    member_join_date DATE NOT NULL
);

-- 멤버의 재참여 정보
CREATE TABLE membership_period (
    period_id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    period_start_date DATE NOT NULL,
    period_end_date DATE,
    period_now_active BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (member_id) REFERENCES member(member_id)
);

-- 세션별(카메라 온오프) 공부 기록
CREATE TABLE study_session (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    session_start_time DATETIME NOT NULL,
    session_end_time DATETIME NOT NULL,
    session_duration INT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 공부 시작 시간 : 기본값 0
ALTER TABLE study_session MODIFY session_duration INT DEFAULT 0;

-- 공부 종료 시간 : NULL 허용
ALTER TABLE study_session MODIFY session_end_time DATETIME NULL;

-- 일별 공부 기록
CREATE TABLE activity_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    log_date DATE NOT NULL,
    log_message_count INT NOT NULL,
    log_study_time INT NOT NULL,
    log_login_count INT NOT NULL,
    log_attendance BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 휴가 기록
CREATE TABLE vacation_log (
    vacation_id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    vacation_date DATE NOT NULL,
    vacation_week_start DATE NOT NULL,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 멤버별 활동 시간대
CREATE TABLE behavioral_segment (
    segment_id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    segment_active_hour VARCHAR(50) NOT NULL,
    segment_active_period ENUM('Day', 'Night') NOT NULL,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);

-- 이탈률 예측
CREATE TABLE churn_prediction (
    prediction_id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    period_id INT NOT NULL,
    prediction_date DATE NOT NULL,
    prediction_absence_count INT NOT NULL,
    prediction_risk_level ENUM('Low', 'Moderate', 'High') NOT NULL,
    FOREIGN KEY (member_id) REFERENCES member(member_id),
    FOREIGN KEY (period_id) REFERENCES membership_period(period_id)
);


