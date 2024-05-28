-- 데이터베이스를 UTF-8로 설정
ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 기존 테이블을 UTF-8로 변경
ALTER TABLE member CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;



-- 멤버 기본정보
CREATE TABLE member (
    member_id INT AUTO_INCREMENT PRIMARY KEY,
    member_nickname VARCHAR(255) NOT NULL,
    member_username VARCHAR(255) NOT NULL,
    member_join_date DATE NOT NULL
);
-- 이후에 컬럼 수정
ALTER TABLE member MODIFY COLUMN member_nickname VARCHAR(255) NOT NULL;
ALTER TABLE member MODIFY COLUMN member_username VARCHAR(255) NOT NULL;
ALTER TABLE member MODIFY COLUMN member_join_date DATE NOT NULL;



-- 멤버의 재참여 정보
CREATE TABLE membership_period (
    period_id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    period_start_date DATE NOT NULL,
    period_end_date DATE,
    period_now_active BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (member_id) REFERENCES member(member_id)
);
-- 이후에 컬럼 수정
ALTER TABLE membership_period MODIFY COLUMN member_id INT NOT NULL;
ALTER TABLE membership_period MODIFY COLUMN period_start_date DATE NOT NULL;
ALTER TABLE membership_period MODIFY COLUMN period_end_date DATE NULL;
ALTER TABLE membership_period MODIFY COLUMN period_now_active BOOLEAN NOT NULL DEFAULT TRUE;





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
-- 이후에 컬럼 수정
ALTER TABLE study_session MODIFY COLUMN member_id INT NOT NULL;
ALTER TABLE study_session MODIFY COLUMN period_id INT NOT NULL;
ALTER TABLE study_session MODIFY COLUMN session_start_time DATETIME NOT NULL;
ALTER TABLE study_session MODIFY COLUMN session_end_time DATETIME NULL;
ALTER TABLE study_session MODIFY COLUMN session_duration INT NOT NULL DEFAULT 0;




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
-- 이후에 컬럼 수정
ALTER TABLE activity_log MODIFY COLUMN member_id INT NOT NULL;
ALTER TABLE activity_log MODIFY COLUMN period_id INT NOT NULL;
ALTER TABLE activity_log MODIFY COLUMN log_date DATE NOT NULL;
ALTER TABLE activity_log MODIFY COLUMN log_message_count INT NOT NULL DEFAULT 0;
ALTER TABLE activity_log MODIFY COLUMN log_study_time INT NOT NULL;
ALTER TABLE activity_log MODIFY COLUMN log_login_count INT NOT NULL DEFAULT 0;
ALTER TABLE activity_log MODIFY COLUMN log_attendance BOOLEAN NOT NULL DEFAULT TRUE;




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
-- 이후에 컬럼 수정
ALTER TABLE vacation_log MODIFY COLUMN member_id INT NOT NULL;
ALTER TABLE vacation_log MODIFY COLUMN period_id INT NOT NULL;
ALTER TABLE vacation_log MODIFY COLUMN vacation_date DATE NOT NULL;
ALTER TABLE vacation_log MODIFY COLUMN vacation_week_start DATE NOT NULL;





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
-- 이후에 컬럼 수정
ALTER TABLE behavioral_segment MODIFY COLUMN member_id INT NOT NULL;
ALTER TABLE behavioral_segment MODIFY COLUMN period_id INT NOT NULL;
ALTER TABLE behavioral_segment MODIFY COLUMN segment_active_hour VARCHAR(50) NOT NULL;
ALTER TABLE behavioral_segment MODIFY COLUMN segment_active_period ENUM('Day', 'Night') NOT NULL;





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
-- 이후에 컬럼 수정
ALTER TABLE churn_prediction MODIFY COLUMN member_id INT NOT NULL;
ALTER TABLE churn_prediction MODIFY COLUMN period_id INT NOT NULL;
ALTER TABLE churn_prediction MODIFY COLUMN prediction_date DATE NOT NULL;
ALTER TABLE churn_prediction MODIFY COLUMN prediction_absence_count INT NOT NULL;
ALTER TABLE churn_prediction MODIFY COLUMN prediction_risk_level ENUM('Low', 'Moderate', 'High') NOT NULL;


-- //////////////////////////////// 저장된 데이터 초기화 코드 ///////////////////////////////////
-- study_session 테이블 데이터 초기화 및 ID 리셋
TRUNCATE TABLE study_session;

-- activity_log 테이블 데이터 초기화 및 ID 리셋
TRUNCATE TABLE activity_log;


-- //////////////////////////////// 테이블 완전히 삭제 ///////////////////////////////////
DROP TABLE IF EXISTS member;
DROP TABLE IF EXISTS membership_period;
DROP TABLE IF EXISTS study_session;
DROP TABLE IF EXISTS activity_log;
DROP TABLE IF EXISTS vacation_log;
DROP TABLE IF EXISTS churn_prediction;
DROP TABLE IF EXISTS behavioral_segment;
