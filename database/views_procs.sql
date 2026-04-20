-- Active subscriptions with visit utilization
CREATE OR REPLACE VIEW v_active_subscriptions AS
SELECT
	s.subscription_id,
	s.client_id,
	CONCAT(p.first_name, ' ', p.last_name) AS client_name,
	mt.name AS membership_name,
	s.start_date,
	s.end_date,
	mt.max_visits,
	COUNT(a.attendance_id) FILTER (WHERE a.status = 'attended') AS used_visits,
	CASE
		WHEN mt.max_visits IS NULL THEN NULL
		ELSE GREATEST(mt.max_visits - COUNT(a.attendance_id) FILTER (WHERE a.status = 'attended'), 0)
	END AS visits_left
FROM subscriptions s
JOIN persons p ON p.person_id = s.client_id
JOIN membership_types mt ON mt.membership_type_id = s.membership_type_id
LEFT JOIN attendance a ON a.subscription_id = s.subscription_id
WHERE s.is_paid = TRUE
  AND s.start_date <= CURRENT_DATE
  AND s.end_date >= CURRENT_DATE
GROUP BY s.subscription_id, s.client_id, client_name, mt.name, s.start_date, s.end_date, mt.max_visits;


-- Ensure profile has a dedicated activity timestamp for trigger updates
ALTER TABLE client_profiles
ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;


-- Main check-in function used by API
CREATE OR REPLACE FUNCTION check_in_client(p_client_id UUID, p_schedule_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
	v_schedule RECORD;
	v_subscription RECORD;
	v_attendance_id UUID;
BEGIN
	SELECT sch.schedule_id, sch.start_time, sch.end_time, sch.is_cancelled,
		   wt.max_capacity,
		   COUNT(a.attendance_id) FILTER (WHERE a.status IN ('booked', 'attended')) AS occupied
	INTO v_schedule
	FROM schedule sch
	JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
	LEFT JOIN attendance a ON a.schedule_id = sch.schedule_id
	WHERE sch.schedule_id = p_schedule_id
	GROUP BY sch.schedule_id, sch.start_time, sch.end_time, sch.is_cancelled, wt.max_capacity;

	IF NOT FOUND THEN
		RAISE EXCEPTION 'Schedule not found';
	END IF;

	IF v_schedule.is_cancelled THEN
		RAISE EXCEPTION 'Session is cancelled';
	END IF;

	SELECT s.subscription_id, mt.max_visits,
		   COUNT(a.attendance_id) FILTER (WHERE a.status = 'attended') AS used_visits
	INTO v_subscription
	FROM subscriptions s
	JOIN membership_types mt ON mt.membership_type_id = s.membership_type_id
	LEFT JOIN attendance a ON a.subscription_id = s.subscription_id
	WHERE s.client_id = p_client_id
	  AND s.is_paid = TRUE
	  AND s.start_date <= CURRENT_DATE
	  AND s.end_date >= CURRENT_DATE
	GROUP BY s.subscription_id, mt.max_visits
	ORDER BY s.end_date DESC
	LIMIT 1;

	IF NOT FOUND THEN
		RAISE EXCEPTION 'Active paid subscription was not found';
	END IF;

	IF v_subscription.max_visits IS NOT NULL AND v_subscription.used_visits >= v_subscription.max_visits THEN
		RAISE EXCEPTION 'No visits left for current subscription';
	END IF;

	INSERT INTO attendance (client_id, schedule_id, subscription_id, status, check_in_time)
	VALUES (p_client_id, p_schedule_id, v_subscription.subscription_id, 'attended', NOW())
	ON CONFLICT (client_id, schedule_id)
	DO UPDATE
	   SET status = 'attended',
		   check_in_time = COALESCE(attendance.check_in_time, NOW()),
		   subscription_id = EXCLUDED.subscription_id
	RETURNING attendance_id INTO v_attendance_id;

	RETURN jsonb_build_object(
		'attendance_id', v_attendance_id,
		'subscription_id', v_subscription.subscription_id,
		'status', 'attended'
	);
END;
$$;


-- Wrapper procedure compatible with project brief
CREATE OR REPLACE PROCEDURE sp_register_visit(p_client_id UUID, p_schedule_id UUID)
LANGUAGE plpgsql
AS $$
BEGIN
	PERFORM check_in_client(p_client_id, p_schedule_id);
END;
$$;


-- Trigger function: update client last activity after successful check-in
CREATE OR REPLACE FUNCTION tg_update_last_visit()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
	IF NEW.status = 'attended' THEN
		UPDATE client_profiles
		SET last_activity_at = COALESCE(NEW.check_in_time, NOW())
		WHERE person_id = NEW.client_id;
	END IF;
	RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_update_last_visit ON attendance;

CREATE TRIGGER trg_update_last_visit
AFTER INSERT OR UPDATE OF status, check_in_time ON attendance
FOR EACH ROW
EXECUTE FUNCTION tg_update_last_visit();
