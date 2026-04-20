CREATE OR REPLACE VIEW v_active_subscriptions AS
SELECT 
    s.subscription_id,
    p.person_id AS client_id,
    CONCAT(p.first_name, ' ', p.last_name) AS client_name,
    mt.name AS membership_name,
    s.start_date,
    s.end_date,
    s.end_date - CURRENT_DATE AS days_left
FROM subscriptions s
JOIN persons p ON s.client_id = p.person_id
JOIN membership_types mt ON s.membership_type_id = mt.membership_type_id
WHERE s.end_date >= CURRENT_DATE AND s.is_paid = TRUE;

--Процедура проверяет на активность абонемент, нет ли записи и ставит статус Attended
CREATE OR REPLACE FUNCTION check_in_client(
    p_client_id  UUID,
    p_schedule_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
--наши переменки UUID тип ключа(алфавит от a-f)
DECLARE
    v_attendance_id UUID;
    v_subscription_id UUID;
BEGIN
    -- Проверяем активный абонемент по view
    SELECT subscription_id INTO v_subscription_id
    FROM subscriptions
    WHERE client_id = p_client_id
      AND end_date >= CURRENT_DATE
      AND is_paid = TRUE
    LIMIT 1;
	
	--Если нет id
    IF v_subscription_id IS NULL THEN
        RETURN 'ERROR: No active subscription';
    END IF;

    -- Ищем запись на занятие
    SELECT attendance_id INTO v_attendance_id
    FROM attendance
    WHERE client_id = p_client_id AND schedule_id = p_schedule_id;

	--Нет записи на это занятие
    IF v_attendance_id IS NULL THEN
        RETURN 'ERROR: Not booked for this class';
    END IF;

    -- Отмечаем приход как раз отмечаем подобие прихода
    UPDATE attendance
    SET status = 'attended',
        check_in_time = NOW()
    WHERE attendance_id = v_attendance_id;

    RETURN 'OK: Checked in successfully';
END;
$$;

-- Вызов процедурки что отмечает приход
SELECT check_in_client('uuid-клиента', 'uuid-занятия');

--Функция для тригера по изменению статуса
CREATE OR REPLACE FUNCTION fn_log_last_visit()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Только если статус изменился на attended
    IF NEW.status = 'attended' AND OLD.status != 'attended' THEN
        -- Можно в логи писать или обновлять, но мы сделаем алерт 
        -- Демонстрационный момент
        RAISE NOTICE 'Client % checked in at %', NEW.client_id, NEW.check_in_time;
    END IF;
    RETURN NEW;
END;
$$;

-- Сам триггер
CREATE OR REPLACE TRIGGER tg_update_last_visit
AFTER UPDATE ON attendance
FOR EACH ROW
EXECUTE FUNCTION fn_log_last_visit();


