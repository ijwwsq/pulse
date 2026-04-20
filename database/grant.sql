-- Создаём роли
CREATE ROLE coach    NOLOGIN;
CREATE ROLE receptionist NOLOGIN;
CREATE ROLE admin_role   NOLOGIN;

-- Тренер: видит расписание, посещаемость, свой профиль
GRANT SELECT ON schedule, attendance, workout_types, persons TO coach;
GRANT SELECT ON v_trainer_performance, v_workout_popularity TO coach;

-- Ресепшн: работает с клиентами и абонементами
GRANT SELECT, INSERT, UPDATE ON persons, client_profiles, subscriptions, attendance TO receptionist;
GRANT SELECT ON v_active_subscriptions, v_client_activity TO receptionist;
GRANT INSERT ON transactions TO receptionist;

-- Админ: полный доступ
GRANT ALL ON ALL TABLES IN SCHEMA public TO admin_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO admin_role;