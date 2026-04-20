-- Draft procedure for demo purposes.
-- This file is intentionally NOT connected to init scripts.

CREATE OR REPLACE PROCEDURE sp_subscription_autobook_workouts(
    p_subscription_id UUID,
    p_client_id UUID,
    p_trainer_id UUID,
    p_limit INTEGER DEFAULT 12
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_start_date DATE;
    v_end_date DATE;
BEGIN
    SELECT s.start_date, s.end_date
      INTO v_start_date, v_end_date
    FROM subscriptions s
    WHERE s.subscription_id = p_subscription_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Subscription % not found', p_subscription_id;
    END IF;

    INSERT INTO attendance (client_id, schedule_id, subscription_id, status)
    SELECT
        p_client_id,
        slot.schedule_id,
        p_subscription_id,
        'booked'
    FROM (
        SELECT
            sch.schedule_id
        FROM schedule sch
        JOIN workout_types wt
          ON wt.workout_type_id = sch.workout_type_id
        LEFT JOIN attendance a
          ON a.schedule_id = sch.schedule_id
         AND a.status IN ('booked', 'attended')
        WHERE sch.trainer_id = p_trainer_id
          AND sch.is_cancelled = FALSE
          AND sch.start_time::date BETWEEN v_start_date AND v_end_date
          AND sch.start_time >= NOW()
        GROUP BY sch.schedule_id, sch.start_time, wt.max_capacity
        HAVING COUNT(a.attendance_id) < wt.max_capacity
        ORDER BY sch.start_time ASC
        LIMIT GREATEST(p_limit, 1)
    ) AS slot
    ON CONFLICT (client_id, schedule_id)
    DO UPDATE
       SET subscription_id = EXCLUDED.subscription_id,
           status = 'booked';
END;
$$;
