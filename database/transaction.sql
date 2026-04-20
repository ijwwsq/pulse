--Надо вставить реальные ID
DO $$
DECLARE
    v_client_id        UUID := 'uuid-клиента';
    v_membership_id    UUID := 'uuid-типа-абонемента';
    v_staff_id         UUID := 'uuid-сотрудника';
    v_price            DECIMAL(10,2);
    v_duration         INTEGER;
    v_subscription_id  UUID;
BEGIN
    -- Получаем цену и срок
    SELECT price, duration_days
    INTO v_price, v_duration
    FROM membership_types
    WHERE membership_type_id = v_membership_id;

    IF v_price IS NULL THEN
        RAISE EXCEPTION 'Неизвестный тип подписки';
    END IF;

    -- Создаём абонемент для человека
    INSERT INTO subscriptions (
        client_id, membership_type_id,
        start_date, end_date,
        is_paid, sold_by_staff_id
    )
    VALUES (
        v_client_id, v_membership_id,
        CURRENT_DATE, CURRENT_DATE + v_duration,
        TRUE, v_staff_id
    )
    RETURNING subscription_id INTO v_subscription_id;

    -- Транзакция по оплате
    INSERT INTO transactions (
        client_id, staff_id, service_type,
        reference_id, amount, payment_status
    )
    VALUES (
        v_client_id, v_staff_id, 'subscription',
        v_subscription_id, v_price, 'paid'
    );

    RAISE NOTICE 'Subscription % created, amount %', v_subscription_id, v_price;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'ROLLBACK: %', SQLERRM;
        RAISE;
END;
$$;

BEGIN;

-- Блокируем строку расписания пока не завершим запись
SELECT schedule_id, is_cancelled
FROM schedule
WHERE schedule_id = 'uuid-занятия'
FOR UPDATE;

-- Проверяем что ещё не записан и есть места
DO $$
DECLARE
    v_booked INTEGER;
    v_capacity INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_booked
    FROM attendance
    WHERE schedule_id = 'uuid-занятия'
      AND status IN ('booked', 'attended');

    SELECT max_capacity INTO v_capacity
    FROM workout_types wt
    JOIN schedule s ON s.workout_type_id = wt.workout_type_id
    WHERE s.schedule_id = 'uuid-занятия';

    IF v_booked >= v_capacity THEN
        RAISE EXCEPTION 'Class is full';
    END IF;
END;
$$;

INSERT INTO attendance (client_id, schedule_id, status)
VALUES ('uuid-клиента', 'uuid-занятия', 'booked');

COMMIT;