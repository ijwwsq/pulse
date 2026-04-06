-- =========================================================================
-- АНАЛИТИЧЕСКИЕ ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ ОТЧЕТНОСТИ И ДАШБОРДОВ
-- =========================================================================

-- 1. Аналитика продаж абонементов (Выручка по месяцам, типам абонементов и кто продал)
CREATE OR REPLACE VIEW v_sales_analytics AS
SELECT 
    DATE_TRUNC('month', t.created_at)::DATE AS sales_month,
    mt.name AS membership_name,
    CONCAT(p.first_name, ' ', p.last_name) AS sold_by_staff,
    COUNT(s.subscription_id) AS total_subscriptions_sold,
    SUM(t.amount) AS total_revenue
FROM transactions t
JOIN subscriptions s ON t.reference_id = s.subscription_id AND t.service_type = 'subscription'
JOIN membership_types mt ON s.membership_type_id = mt.membership_type_id
LEFT JOIN persons p ON s.sold_by_staff_id = p.person_id
WHERE t.payment_status = 'paid'
GROUP BY 1, 2, 3;

-- 2. Активность клиентов (Воронка, удержание, LTV метрики базы)
CREATE OR REPLACE VIEW v_client_activity AS
SELECT
    p.person_id AS client_id,
    CONCAT(p.first_name, ' ', p.last_name) AS client_name,
    cp.registration_date,
    COUNT(DISTINCT s.subscription_id) AS total_subscriptions_bought,
    COUNT(DISTINCT a.attendance_id) FILTER (WHERE a.status = 'attended') AS total_visits,
    MAX(a.check_in_time) AS last_visit_time,
    COUNT(DISTINCT a.attendance_id) FILTER (WHERE a.status = 'no-show') AS total_no_shows,
    CASE WHEN CURRENT_DATE <= MAX(s.end_date) THEN TRUE ELSE FALSE END AS has_active_subscription
FROM persons p
JOIN client_profiles cp ON p.person_id = cp.person_id
LEFT JOIN subscriptions s ON p.person_id = s.client_id
LEFT JOIN attendance a ON p.person_id = a.client_id
GROUP BY 1, 2, 3;

-- 3. Эффективность тренеров (KPI по проведенным занятиям и заполняемости)
CREATE OR REPLACE VIEW v_trainer_performance AS
WITH class_stats AS (
    SELECT 
        sch.schedule_id,
        DATE_TRUNC('month', sch.start_time)::DATE AS period_month,
        sch.trainer_id,
        COUNT(a.attendance_id) FILTER (WHERE a.status = 'attended') AS attended_count,
        wt.max_capacity
    FROM schedule sch
    JOIN workout_types wt ON sch.workout_type_id = wt.workout_type_id
    LEFT JOIN attendance a ON sch.schedule_id = a.schedule_id
    WHERE sch.is_cancelled = FALSE AND sch.start_time < CURRENT_TIMESTAMP
    GROUP BY sch.schedule_id, period_month, sch.trainer_id, wt.max_capacity
)
SELECT 
    cs.period_month,
    p.person_id AS trainer_id,
    CONCAT(p.first_name, ' ', p.last_name) AS trainer_name,
    sp.role,
    sp.qualification_lvl,
    COUNT(cs.schedule_id) AS classes_conducted,
    SUM(cs.attended_count) AS total_clients_attended,
    ROUND(AVG(cs.attended_count::NUMERIC / NULLIF(cs.max_capacity, 0)) * 100, 2) AS avg_occupancy_rate_percent
FROM class_stats cs
JOIN persons p ON cs.trainer_id = p.person_id
JOIN staff_profiles sp ON p.person_id = sp.person_id
GROUP BY 1, 2, 3, 4, 5;

-- 4. Популярность направлений и занятий (Для корректировки расписания)
CREATE OR REPLACE VIEW v_workout_popularity AS
SELECT
    wt.category,
    wt.title AS workout_name,
    wt.intensity_level,
    COUNT(DISTINCT sch.schedule_id) AS total_scheduled,
    COUNT(DISTINCT sch.schedule_id) FILTER (WHERE sch.is_cancelled = TRUE) AS total_cancelled,
    COUNT(a.attendance_id) FILTER (WHERE a.status = 'booked') AS total_bookings,
    COUNT(a.attendance_id) FILTER (WHERE a.status = 'attended') AS total_attendances,
    ROUND(
        COUNT(a.attendance_id) FILTER (WHERE a.status = 'attended')::NUMERIC / 
        NULLIF(COUNT(a.attendance_id) FILTER (WHERE a.status IN ('booked', 'attended', 'no-show')), 0) * 100
    , 2) AS attendance_rate_percent
FROM workout_types wt
LEFT JOIN schedule sch ON wt.workout_type_id = sch.workout_type_id
LEFT JOIN attendance a ON sch.schedule_id = a.schedule_id
GROUP BY 1, 2, 3;

-- 5. Финансовая сводка (Общие финансовые потоки)
CREATE OR REPLACE VIEW v_financial_summary AS
SELECT
    DATE_TRUNC('month', created_at)::DATE AS fin_month,
    service_type,
    payment_status,
    COUNT(transaction_id) AS transactions_count,
    SUM(amount) AS total_amount
FROM transactions
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 2;
