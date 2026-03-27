-- =========================================================
-- smart_home DATABASE - 
-- =========================================================

CREATE DATABASE IF NOT EXISTS smart_home
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE smart_home;

-- =========================================================
-- 1. USERS
-- [FIX 1] Bỏ 'ai_service' khỏi ENUM.
--         Service account nên dùng bảng service_api_keys riêng.
-- =========================================================
CREATE TABLE users (
    id            BIGINT       PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(100) NOT NULL UNIQUE,
    full_name     VARCHAR(150) NOT NULL,
    email         VARCHAR(150) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role   ENUM('owner','resident','admin','guest','maintenance') NOT NULL DEFAULT 'resident',
    status ENUM('active','inactive')                             NOT NULL DEFAULT 'active',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 2. ROOMS
-- =========================================================
CREATE TABLE rooms (
    id        BIGINT       PRIMARY KEY AUTO_INCREMENT,
    room_name VARCHAR(100) NOT NULL UNIQUE,
    room_type VARCHAR(50)
);

-- =========================================================
-- 3. SCENES + AUTOMATION_RULES
-- Phải tạo TRƯỚC devices_usage_sessions và device_actions
-- vì các bảng đó FK vào đây. [FIX 11]
-- [FIX 10] automation_rules: thêm trigger_count và last_result
-- =========================================================
CREATE TABLE scenes (
    id                 BIGINT       PRIMARY KEY AUTO_INCREMENT,
    created_by_user_id BIGINT       NOT NULL,
    scene_name         VARCHAR(100) NOT NULL,
    description        VARCHAR(255),
    trigger_type ENUM('manual','schedule','condition') NOT NULL DEFAULT 'manual',
    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_scenes_user
        FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_scenes_creator (created_by_user_id),
    INDEX idx_scenes_active (is_active)
);

CREATE TABLE automation_rules (
    id                 BIGINT       PRIMARY KEY AUTO_INCREMENT,
    created_by_user_id BIGINT       NOT NULL,
    rule_name          VARCHAR(100) NOT NULL,
    condition_json     JSON         NOT NULL,
    action_json        JSON         NOT NULL,
    is_enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    last_triggered_at  DATETIME     NULL,
    trigger_count      INT          NOT NULL DEFAULT 0,           -- [FIX 10]
    last_result        ENUM('success','failed') NULL,            -- [FIX 10]
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_automation_rules_user
        FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_automation_rules_enabled (is_enabled),
    INDEX idx_automation_rules_last_triggered (last_triggered_at)
);

-- =========================================================
-- 4. DEVICES
-- [FIX 2] Thêm created_by_user_id để hiện thực hoá quan hệ users->devices (manages).
--         ON DELETE SET NULL: device không bị xóa khi user bị xóa.
-- =========================================================
CREATE TABLE devices (
    id                 BIGINT       PRIMARY KEY AUTO_INCREMENT,
    room_id            BIGINT       NOT NULL,
    created_by_user_id BIGINT       NULL,                        -- [FIX 2]
    device_code        VARCHAR(100) NOT NULL UNIQUE,
    device_type        VARCHAR(50)  NOT NULL,
    device_name        VARCHAR(150) NOT NULL,
    mqtt_topic_status  VARCHAR(255),
    mqtt_topic_command VARCHAR(255),
    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_devices_room
        FOREIGN KEY (room_id) REFERENCES rooms(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_devices_created_by                             -- [FIX 2]
        FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_devices_room (room_id),
    INDEX idx_devices_type (device_type),
    INDEX idx_devices_created_by (created_by_user_id)
);

-- =========================================================
-- 5. DEVICE STATE / SENSOR
-- [FIX 3] device_states: weak entity -> composite PK (device_id, state_key, recorded_at)
--         Bỏ id AUTO_INCREMENT vì định danh phụ thuộc vào devices.
-- =========================================================
CREATE TABLE device_states (
    device_id   BIGINT       NOT NULL,
    state_key   VARCHAR(100) NOT NULL,
    state_value VARCHAR(255) NOT NULL,
    recorded_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (device_id, state_key, recorded_at),             -- [FIX 3]
    CONSTRAINT fk_device_states_device
        FOREIGN KEY (device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    INDEX idx_device_states_device_time (device_id, recorded_at),
    INDEX idx_device_states_key_time (device_id, state_key, recorded_at)
);

CREATE TABLE sensor_readings (
    id            BIGINT        PRIMARY KEY AUTO_INCREMENT,
    device_id     BIGINT        NOT NULL,
    reading_type  VARCHAR(50)   NOT NULL,
    value_decimal DECIMAL(12,4) NOT NULL,
    unit          VARCHAR(20),
    quality_flag  ENUM('normal','warning','danger') NOT NULL DEFAULT 'normal',
    recorded_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sensor_readings_device
        FOREIGN KEY (device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    INDEX idx_sensor_readings_device_time (device_id, recorded_at),
    INDEX idx_sensor_readings_type_time (reading_type, recorded_at)
);

-- =========================================================
-- 6. DEVICE USAGE SESSIONS
-- [FIX 4] Bỏ duration_seconds (dư thừa — dùng VIEW thay thế).
--         Thêm triggered_by_scene_id và triggered_by_rule_id để truy vết nguồn kích hoạt.
-- =========================================================
CREATE TABLE device_usage_sessions (
    id                    BIGINT        PRIMARY KEY AUTO_INCREMENT,
    device_id             BIGINT        NOT NULL,
    triggered_by_user_id  BIGINT        NULL,
    triggered_by_scene_id BIGINT        NULL,                    -- [FIX 4]
    triggered_by_rule_id  BIGINT        NULL,                    -- [FIX 4]
    start_source ENUM('manual','auto','scene','ai','mqtt')       NOT NULL DEFAULT 'manual',
    started_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at              DATETIME      NULL,
    -- duration_seconds: ĐÃ BỎ [FIX 4] -> dùng v_device_usage_with_duration view
    estimated_energy_wh   DECIMAL(12,3) NULL,
    estimated_cost        DECIMAL(12,2) NULL,
    note                  VARCHAR(255)  NULL,
    CONSTRAINT fk_device_usage_sessions_device
        FOREIGN KEY (device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_device_usage_sessions_user
        FOREIGN KEY (triggered_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_device_usage_sessions_scene                   -- [FIX 4]
        FOREIGN KEY (triggered_by_scene_id) REFERENCES scenes(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_device_usage_sessions_rule                    -- [FIX 4]
        FOREIGN KEY (triggered_by_rule_id) REFERENCES automation_rules(id)
        ON DELETE SET NULL,
    INDEX idx_device_usage_sessions_device_time (device_id, started_at, ended_at),
    INDEX idx_device_usage_sessions_user_time (triggered_by_user_id, started_at),
    INDEX idx_device_usage_sessions_scene (triggered_by_scene_id),
    INDEX idx_device_usage_sessions_rule (triggered_by_rule_id)
);

-- =========================================================
-- 7. DEVICE ACTIONS
-- [FIX 5] Thêm triggered_by_scene_id và triggered_by_rule_id.
-- =========================================================
CREATE TABLE device_actions (
    id                    BIGINT       PRIMARY KEY AUTO_INCREMENT,
    device_id             BIGINT       NOT NULL,
    triggered_by_user_id  BIGINT       NULL,
    triggered_by_scene_id BIGINT       NULL,                     -- [FIX 5]
    triggered_by_rule_id  BIGINT       NULL,                     -- [FIX 5]
    action_name           VARCHAR(100) NOT NULL,
    action_value          VARCHAR(255),
    action_source ENUM('manual','auto','scene','ai','mqtt')      NOT NULL DEFAULT 'manual',
    result_status ENUM('success','failed','pending')             NOT NULL DEFAULT 'pending',
    executed_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_device_actions_device
        FOREIGN KEY (device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_device_actions_user
        FOREIGN KEY (triggered_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_device_actions_scene                          -- [FIX 5]
        FOREIGN KEY (triggered_by_scene_id) REFERENCES scenes(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_device_actions_rule                           -- [FIX 5]
        FOREIGN KEY (triggered_by_rule_id) REFERENCES automation_rules(id)
        ON DELETE SET NULL,
    INDEX idx_device_actions_device_time (device_id, executed_at),
    INDEX idx_device_actions_user_time (triggered_by_user_id, executed_at),
    INDEX idx_device_actions_source_time (action_source, executed_at),
    INDEX idx_device_actions_scene (triggered_by_scene_id),
    INDEX idx_device_actions_rule (triggered_by_rule_id)
);

-- =========================================================
-- 8. ACTIVITY LOGS
-- Đổi entity_type thành ENUM để tránh giá trị tự do gây lỗi.
-- =========================================================
CREATE TABLE activity_logs (
    id            BIGINT       PRIMARY KEY AUTO_INCREMENT,
    user_id       BIGINT       NULL,
    activity_type VARCHAR(100) NOT NULL,
    entity_type   ENUM(
        'devices','rooms','users','scenes','automation_rules',
        'security_events','access_credentials','ai_recommendations',
        'guest_device_permissions','sensor_readings'
    )                          NULL,
    entity_id     BIGINT       NULL,
    detail_json   JSON         NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_activity_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_activity_logs_time (created_at),
    INDEX idx_activity_logs_user_time (user_id, created_at),
    INDEX idx_activity_logs_type_time (activity_type, created_at)
);

-- =========================================================
-- 9. ACCESS CONTROL
-- [FIX 6] access_credentials: BỎ UNIQUE(user_id, auth_method).
--         1 user được có nhiều credential (hỗ trợ cấp lại PIN/FACE_ID mới).
--         Dùng view v_active_credentials để lấy credential đang active.
-- =========================================================
CREATE TABLE access_credentials (
    id                BIGINT       PRIMARY KEY AUTO_INCREMENT,
    user_id           BIGINT       NOT NULL,
    auth_method       ENUM('PIN','FACE_ID') NOT NULL,
    credential_hash   VARCHAR(255) NOT NULL,
    valid_from        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at        DATETIME     NULL,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    issued_by_user_id BIGINT       NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- BỎ: UNIQUE KEY uk_user_auth_method (user_id, auth_method) [FIX 6]
    CONSTRAINT fk_access_credentials_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_access_credentials_issued_by
        FOREIGN KEY (issued_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_access_credentials_user_method (user_id, auth_method),
    INDEX idx_access_credentials_validity (valid_from, expires_at),
    INDEX idx_access_credentials_active (is_active)
);

CREATE TABLE access_logs (
    id             BIGINT       PRIMARY KEY AUTO_INCREMENT,
    user_id        BIGINT       NULL,
    device_id      BIGINT       NOT NULL,
    auth_method    ENUM('PIN','FACE_ID') NOT NULL,
    access_result  ENUM('success','failed') NOT NULL,
    failure_reason VARCHAR(255) NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_access_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_access_logs_device
        FOREIGN KEY (device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    INDEX idx_access_logs_time (created_at),
    INDEX idx_access_logs_user_time (user_id, created_at),
    INDEX idx_access_logs_device_time (device_id, created_at)
);

-- =========================================================
-- 10. SECURITY EVENTS
-- [FIX 7] Thêm resolved_by_user_id và resolved_at.
--         acknowledge (xác nhận đã thấy) khác resolve (đã xử lý xong).
-- =========================================================
CREATE TABLE security_events (
    id                      BIGINT       PRIMARY KEY AUTO_INCREMENT,
    source_device_id        BIGINT       NOT NULL,
    event_type   ENUM('intrusion','forced_entry','fire','gas_alert','motion_alert') NOT NULL,
    severity     ENUM('low','medium','high','critical')                             NOT NULL DEFAULT 'medium',
    event_status ENUM('open','verified','dismissed','resolved')                     NOT NULL DEFAULT 'open',
    event_detail            VARCHAR(255) NULL,
    detected_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notified_at             DATETIME     NULL,
    acknowledged_by_user_id BIGINT       NULL,
    acknowledged_at         DATETIME     NULL,
    resolved_by_user_id     BIGINT       NULL,                   -- [FIX 7]
    resolved_at             DATETIME     NULL,                   -- [FIX 7]
    CONSTRAINT fk_security_events_device
        FOREIGN KEY (source_device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_security_events_ack_user
        FOREIGN KEY (acknowledged_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_security_events_resolved_user                 -- [FIX 7]
        FOREIGN KEY (resolved_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_security_events_type_time (event_type, detected_at),
    INDEX idx_security_events_status_time (event_status, detected_at),
    INDEX idx_security_events_ack_time (acknowledged_by_user_id, acknowledged_at),
    INDEX idx_security_events_resolved_time (resolved_by_user_id, resolved_at)
);

-- =========================================================
-- 11. SCENE DEVICES (weak entity)
-- Thêm UNIQUE(scene_id, device_id, execution_order) để ngăn duplicate.
-- =========================================================
CREATE TABLE scene_devices (
    id              BIGINT       PRIMARY KEY AUTO_INCREMENT,
    scene_id        BIGINT       NOT NULL,
    device_id       BIGINT       NOT NULL,
    action_name     VARCHAR(100) NOT NULL,
    action_value    VARCHAR(255),
    execution_order INT          NOT NULL DEFAULT 1,
    CONSTRAINT fk_scene_devices_scene
        FOREIGN KEY (scene_id) REFERENCES scenes(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_scene_devices_device
        FOREIGN KEY (device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    UNIQUE KEY uk_scene_device_order (scene_id, device_id, execution_order),
    INDEX idx_scene_devices_scene_order (scene_id, execution_order),
    INDEX idx_scene_devices_device (device_id)
);

-- =========================================================
-- 12. GUEST DEVICE PERMISSIONS
-- [FIX 8] Bỏ UNIQUE(guest_user_id, device_id) -> nhiều khoảng thời gian khác nhau.
--         Thêm updated_at để track lần cập nhật gần nhất.
-- =========================================================
CREATE TABLE guest_device_permissions (
    id                 BIGINT       PRIMARY KEY AUTO_INCREMENT,
    guest_user_id      BIGINT       NOT NULL,
    device_id          BIGINT       NOT NULL,
    can_view           BOOLEAN      NOT NULL DEFAULT TRUE,
    can_control        BOOLEAN      NOT NULL DEFAULT FALSE,
    valid_from         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until        DATETIME     NULL,
    granted_by_user_id BIGINT       NOT NULL,
    updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP, -- [FIX 8]
    -- BỎ: UNIQUE KEY uk_guest_device_permission (guest_user_id, device_id) [FIX 8]
    CONSTRAINT fk_guest_device_permissions_guest
        FOREIGN KEY (guest_user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_guest_device_permissions_device
        FOREIGN KEY (device_id) REFERENCES devices(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_guest_device_permissions_granted_by
        FOREIGN KEY (granted_by_user_id) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_guest_device_guest_device (guest_user_id, device_id),
    INDEX idx_guest_device_permissions_validity (valid_from, valid_until)
);

-- =========================================================
-- 13. AI RECOMMENDATIONS
-- [FIX 9] Thêm expires_at để cron job tự động set status='expired'.
-- =========================================================
CREATE TABLE ai_recommendations (
    id                   BIGINT       PRIMARY KEY AUTO_INCREMENT,
    target_user_id       BIGINT       NULL,
    recommendation_type  ENUM('device_action','scene_action','scene_suggestion','energy_saving') NOT NULL,
    title                VARCHAR(150) NOT NULL,
    recommendation_text  TEXT         NOT NULL,
    suggested_action_json JSON        NULL,
    status ENUM('new','accepted','rejected','applied','expired')  NOT NULL DEFAULT 'new',
    approved_by_user_id  BIGINT       NULL,
    expires_at           DATETIME     NULL,                      -- [FIX 9]
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at         DATETIME     NULL,
    executed_at          DATETIME     NULL,
    CONSTRAINT fk_ai_recommendations_target_user
        FOREIGN KEY (target_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_ai_recommendations_approved_by
        FOREIGN KEY (approved_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_ai_recommendations_target_status (target_user_id, status, created_at),
    INDEX idx_ai_recommendations_type_time (recommendation_type, created_at),
    INDEX idx_ai_recommendations_expires (expires_at)            -- [FIX 9]
);

-- =========================================================
-- VIEWS TIỆN ÍCH
-- =========================================================

-- Thay thế duration_seconds đã bỏ [FIX 4]
CREATE OR REPLACE VIEW v_device_usage_with_duration AS
SELECT
    id,
    device_id,
    triggered_by_user_id,
    triggered_by_scene_id,
    triggered_by_rule_id,
    start_source,
    started_at,
    ended_at,
    TIMESTAMPDIFF(SECOND, started_at, ended_at) AS duration_seconds,
    estimated_energy_wh,
    estimated_cost,
    note
FROM device_usage_sessions;

-- Thay thế UNIQUE constraint đã bỏ ở access_credentials [FIX 6]
-- Lấy credential đang active của từng user + auth_method
CREATE OR REPLACE VIEW v_active_credentials AS
SELECT *
FROM access_credentials
WHERE is_active = TRUE
  AND (expires_at IS NULL OR expires_at > NOW());

-- Lấy permission đang còn hiệu lực của guest
CREATE OR REPLACE VIEW v_active_guest_permissions AS
SELECT *
FROM guest_device_permissions
WHERE valid_until IS NULL OR valid_until > NOW();

-- AI recommendations sắp hết hạn (cron job dùng để set expired)
CREATE OR REPLACE VIEW v_expired_ai_recommendations AS
SELECT id, target_user_id, title, expires_at
FROM ai_recommendations
WHERE status = 'new'
  AND expires_at IS NOT NULL
  AND expires_at <= NOW();

