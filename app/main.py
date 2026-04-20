from datetime import date
from decimal import Decimal
from uuid import UUID

import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from app.database import fetch_all, fetch_one, transaction


app = FastAPI(title="Pulse API", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
app.add_middleware(
	SessionMiddleware,
	secret_key=os.getenv("SESSION_SECRET", "pulse-dev-secret-key"),
	https_only=False,
	same_site="lax",
)


ALLOWED_ANALYTICS_VIEWS = {
	"v_sales_analytics",
	"v_client_activity",
	"v_trainer_performance",
	"v_workout_popularity",
	"v_financial_summary",
	"v_active_subscriptions",
}

ROLE_CLIENT = "client"
ROLE_TRAINER = "trainer"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
DEMO_OPEN_ACCESS = True


class BookingPayload(BaseModel):
	client_id: UUID
	schedule_id: UUID
	subscription_id: UUID | None = None


class CheckInPayload(BaseModel):
	client_id: UUID
	schedule_id: UUID


class PurchaseSubscriptionPayload(BaseModel):
	client_id: UUID
	membership_type_id: UUID
	sold_by_staff_id: UUID | None = None
	trainer_id: UUID | None = None
	auto_book_schedule: bool = True
	is_paid: bool = True
	start_date: date | None = None


class TransactionPayload(BaseModel):
	client_id: UUID
	staff_id: UUID | None = None
	service_type: str = Field(pattern="^(subscription|personal_training|bar|test|penalty)$")
	reference_id: UUID | None = None
	amount: Decimal = Field(gt=0)
	payment_status: str = Field(pattern="^(pending|paid|refunded|deposit)$")
	notes: str | None = None


class LoginPayload(BaseModel):
	phone: str
	password: str


def _verify_password(phone: str, password: str) -> bool:
	# Demo rule: password is last 4 digits of phone.
	digits = "".join(ch for ch in phone if ch.isdigit())
	return len(digits) >= 4 and password == digits[-4:]


def _authenticate(phone: str, password: str) -> dict | None:
	user = fetch_one(
		"""
		SELECT
			p.person_id,
			p.phone,
			CONCAT(p.first_name, ' ', p.last_name) AS full_name,
			CASE
				WHEN sp.role IN ('admin', 'manager') THEN 'admin'
				WHEN sp.role = 'trainer' THEN 'trainer'
				WHEN cp.person_id IS NOT NULL THEN 'client'
				ELSE 'client'
			END AS app_role,
			COALESCE(sp.role, 'client') AS staff_role
		FROM persons p
		LEFT JOIN client_profiles cp ON cp.person_id = p.person_id
		LEFT JOIN staff_profiles sp ON sp.person_id = p.person_id
		WHERE p.phone = %s
		LIMIT 1
		""",
		(phone,),
	)
	if not user:
		return None
	if not _verify_password(user["phone"], password):
		return None
	return user


def _require_auth(request: Request) -> dict:
	user = request.session.get("user")
	if not user:
		raise HTTPException(status_code=401, detail="Authentication required")
	return user


def _require_role(request: Request, allowed_roles: set[str]) -> dict:
	user = _require_auth(request)
	if user.get("role") not in allowed_roles:
		raise HTTPException(status_code=403, detail="Insufficient role")
	return user


def _dashboard_snapshot() -> dict:
	totals = fetch_one(
		"""
		SELECT
			(SELECT COUNT(*) FROM client_profiles) AS clients_count,
			(SELECT COUNT(*) FROM staff_profiles) AS staff_count,
			(SELECT COUNT(*) FROM subscriptions WHERE end_date >= CURRENT_DATE AND is_paid = TRUE) AS active_subscriptions,
			(SELECT COUNT(*) FROM attendance WHERE status = 'booked') AS pending_bookings,
			(SELECT COUNT(*) FROM attendance WHERE status = 'attended') AS attended_visits
		"""
	)

	today_schedule = fetch_all(
		"""
		SELECT
			sch.schedule_id,
			wt.title,
			wt.category,
			sch.room_name,
			sch.start_time,
			sch.end_time,
			CONCAT(p.first_name, ' ', p.last_name) AS trainer_name,
			wt.max_capacity,
			COUNT(a.attendance_id) FILTER (WHERE a.status IN ('booked', 'attended')) AS used_slots
		FROM schedule sch
		JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
		JOIN persons p ON p.person_id = sch.trainer_id
		LEFT JOIN attendance a ON a.schedule_id = sch.schedule_id
		WHERE sch.start_time::date = CURRENT_DATE
		  AND sch.is_cancelled = FALSE
		GROUP BY sch.schedule_id, wt.title, wt.category, sch.room_name, sch.start_time, sch.end_time,
				 trainer_name, wt.max_capacity
		ORDER BY sch.start_time
		"""
	)

	top_workouts = fetch_all(
		"""
		SELECT workout_name, total_bookings, total_attendances, attendance_rate_percent
		FROM v_workout_popularity
		ORDER BY total_bookings DESC NULLS LAST
		LIMIT 5
		"""
	)

	return {
		"totals": totals or {},
		"today_schedule": today_schedule,
		"top_workouts": top_workouts,
	}


@app.get("/")
def index(request: Request):
	user = request.session.get("user")
	if user:
		role = user.get("role")
		if role == ROLE_CLIENT:
			return RedirectResponse(url="/client", status_code=302)
		if role == ROLE_TRAINER:
			return RedirectResponse(url="/trainer", status_code=302)
		return RedirectResponse(url="/admin", status_code=302)

	error = None
	totals = {}
	try:
		totals = _dashboard_snapshot().get("totals", {})
	except Exception as exc:
		error = f"Database is not ready: {exc}"

	return templates.TemplateResponse(request, "index.html", {"error": error, "totals": totals, "user": None})


@app.get("/login")
def login_page(request: Request):
	if request.session.get("user"):
		return RedirectResponse(url="/", status_code=302)
	return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/api/auth/login")
def login(payload: LoginPayload, request: Request):
	user = _authenticate(payload.phone, payload.password)
	if not user:
		raise HTTPException(status_code=401, detail="Invalid credentials")

	request.session["user"] = {
		"person_id": str(user["person_id"]),
		"phone": user["phone"],
		"full_name": user["full_name"],
		"role": user["app_role"],
		"staff_role": user["staff_role"],
	}

	role = user["app_role"]
	redirect_to = "/admin"
	if role == ROLE_CLIENT:
		redirect_to = "/client"
	elif role == ROLE_TRAINER:
		redirect_to = "/trainer"

	return {"status": "ok", "redirect_to": redirect_to}


@app.post("/api/auth/logout")
def logout(request: Request):
	request.session.clear()
	return {"status": "ok"}


@app.get("/api/auth/me")
def me(request: Request):
	user = _require_auth(request)
	return {"user": user}


@app.get("/client")
def client_page(request: Request):
	user = request.session.get("user")
	if not user:
		return RedirectResponse(url="/login", status_code=302)
	if user.get("role") not in {ROLE_CLIENT, ROLE_ADMIN}:
		return RedirectResponse(url="/", status_code=302)
	error = None
	initial_client_id = None
	try:
		if user.get("role") == ROLE_CLIENT:
			client = {"client_id": user.get("person_id")}
		else:
			client = fetch_one(
				"""
				SELECT p.person_id AS client_id
				FROM persons p
				JOIN client_profiles cp ON cp.person_id = p.person_id
				ORDER BY cp.registration_date DESC
				LIMIT 1
				"""
			)
		if client:
			initial_client_id = client["client_id"]
	except Exception as exc:
		error = f"Database is not ready: {exc}"

	return templates.TemplateResponse(
		request,
		"client.html",
		{"error": error, "initial_client_id": initial_client_id, "user": user},
	)


@app.get("/trainer")
def trainer_page(request: Request):
	user = request.session.get("user")
	if not user:
		return RedirectResponse(url="/login", status_code=302)
	if user.get("role") not in {ROLE_TRAINER, ROLE_ADMIN}:
		return RedirectResponse(url="/", status_code=302)
	error = None
	initial_trainer_id = None
	try:
		if user.get("role") == ROLE_TRAINER:
			trainer = {"trainer_id": user.get("person_id")}
		else:
			trainer = fetch_one(
				"""
				SELECT p.person_id AS trainer_id
				FROM persons p
				JOIN staff_profiles sp ON sp.person_id = p.person_id
				WHERE sp.role = 'trainer'
				ORDER BY p.last_name, p.first_name
				LIMIT 1
				"""
			)
		if trainer:
			initial_trainer_id = trainer["trainer_id"]
	except Exception as exc:
		error = f"Database is not ready: {exc}"

	return templates.TemplateResponse(
		request,
		"trainer.html",
		{"error": error, "initial_trainer_id": initial_trainer_id, "user": user},
	)


@app.get("/admin")
def admin_page(request: Request):
	user = request.session.get("user")
	if not user:
		return RedirectResponse(url="/login", status_code=302)
	if user.get("role") not in {ROLE_ADMIN}:
		return RedirectResponse(url="/", status_code=302)
	error = None
	metrics = {"kpis": {}, "monthly_revenue": [], "attendance_by_category": []}
	try:
		metrics = _admin_metrics()
	except Exception as exc:
		error = f"Database is not ready: {exc}"

	return templates.TemplateResponse(request, "admin.html", {"error": error, "metrics": metrics, "user": user, "analytics_views": sorted(ALLOWED_ANALYTICS_VIEWS)})


@app.get("/health")
def health_check():
	try:
		fetch_one("SELECT 1 AS ok")
	except Exception as exc:
		return JSONResponse(status_code=503, content={"status": "degraded", "error": str(exc)})
	return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard(request: Request):
	_require_role(request, {ROLE_ADMIN, ROLE_TRAINER})
	return _dashboard_snapshot()


def _admin_metrics() -> dict:
	kpis = fetch_one(
		"""
		SELECT
			(SELECT COUNT(*) FROM client_profiles) AS clients_total,
			(SELECT COUNT(*) FROM staff_profiles WHERE role = 'trainer') AS trainers_total,
			(SELECT COUNT(*) FROM subscriptions WHERE is_paid = TRUE AND end_date >= CURRENT_DATE) AS active_subscriptions,
			(SELECT COALESCE(SUM(amount), 0)::double precision FROM transactions WHERE payment_status = 'paid') AS total_revenue
		"""
	)

	monthly_revenue = fetch_all(
		"""
		SELECT
			TO_CHAR(fin_month, 'YYYY-MM') AS month,
			COALESCE(SUM(total_amount), 0)::double precision AS revenue
		FROM v_financial_summary
		WHERE payment_status = 'paid'
		GROUP BY fin_month
		ORDER BY fin_month DESC
		LIMIT 6
		"""
	)

	attendance_by_category = fetch_all(
		"""
		SELECT
			category,
			COALESCE(SUM(total_attendances), 0)::bigint AS attendances
		FROM v_workout_popularity
		GROUP BY category
		ORDER BY attendances DESC
		"""
	)

	return {
		"kpis": kpis or {},
		"monthly_revenue": list(reversed(monthly_revenue)),
		"attendance_by_category": attendance_by_category,
	}


@app.get("/api/clients")
def get_clients(request: Request, search: str | None = Query(default=None)):
	_require_role(request, {ROLE_ADMIN, ROLE_TRAINER})
	where = ""
	params: tuple | None = None
	if search:
		where = "WHERE (p.first_name || ' ' || p.last_name) ILIKE %s OR p.phone ILIKE %s"
		params = (f"%{search}%", f"%{search}%")

	return fetch_all(
		f"""
		SELECT
			p.person_id AS client_id,
			p.first_name,
			p.last_name,
			p.phone,
			p.email,
			cp.registration_date,
			p.is_active
		FROM persons p
		JOIN client_profiles cp ON cp.person_id = p.person_id
		{where}
		ORDER BY cp.registration_date DESC, p.last_name, p.first_name
		""",
		params,
	)


@app.get("/api/lookups")
def lookups(request: Request):
	user = _require_auth(request)
	clients = fetch_all(
		"""
		SELECT p.person_id AS id, CONCAT(p.first_name, ' ', p.last_name) AS name
		FROM persons p
		JOIN client_profiles cp ON cp.person_id = p.person_id
		ORDER BY cp.registration_date DESC
		"""
	)

	trainers = fetch_all(
		"""
		SELECT p.person_id AS id, CONCAT(p.first_name, ' ', p.last_name) AS name
		FROM persons p
		JOIN staff_profiles sp ON sp.person_id = p.person_id
		WHERE sp.role = 'trainer'
		ORDER BY p.last_name, p.first_name
		"""
	)

	staff = fetch_all(
		"""
		SELECT p.person_id AS id, CONCAT(p.first_name, ' ', p.last_name) AS name, sp.role
		FROM persons p
		JOIN staff_profiles sp ON sp.person_id = p.person_id
		ORDER BY sp.role, p.last_name, p.first_name
		"""
	)
	users = fetch_all(
		"""
		SELECT
			p.person_id AS id,
			CONCAT(p.first_name, ' ', p.last_name) AS name,
			COALESCE(sp.role, p.person_type) AS role
		FROM persons p
		LEFT JOIN staff_profiles sp ON sp.person_id = p.person_id
		ORDER BY p.person_type DESC, p.last_name, p.first_name
		"""
	)

	if not DEMO_OPEN_ACCESS:
		if user.get("role") == ROLE_CLIENT:
			clients = [c for c in clients if str(c["id"]) == user.get("person_id")]
		if user.get("role") == ROLE_TRAINER:
			trainers = [t for t in trainers if str(t["id"]) == user.get("person_id")]

	return {"clients": clients, "trainers": trainers, "staff": staff, "users": users}


@app.get("/api/client/{client_id}/overview")
def client_overview(client_id: UUID, request: Request):
	user = _require_role(request, {ROLE_CLIENT, ROLE_ADMIN})
	if not DEMO_OPEN_ACCESS and user.get("role") == ROLE_CLIENT and user.get("person_id") != str(client_id):
		raise HTTPException(status_code=403, detail="Access denied for this client")

	profile = fetch_one(
		"""
		SELECT
			p.person_id AS client_id,
			CONCAT(p.first_name, ' ', p.last_name) AS full_name,
			p.phone,
			p.email,
			cp.registration_date,
			cp.last_activity_at
		FROM persons p
		JOIN client_profiles cp ON cp.person_id = p.person_id
		WHERE p.person_id = %s
		""",
		(client_id,),
	)
	if not profile:
		raise HTTPException(status_code=404, detail="Client not found")

	active_subscription = fetch_one(
		"""
		SELECT membership_name, start_date, end_date, max_visits, used_visits, visits_left
		FROM v_active_subscriptions
		WHERE client_id = %s
		ORDER BY end_date ASC
		LIMIT 1
		""",
		(client_id,),
	)

	upcoming_sessions = fetch_all(
		"""
		SELECT
			a.attendance_id,
			wt.title,
			sch.start_time,
			sch.end_time,
			a.status,
			CONCAT(p.first_name, ' ', p.last_name) AS trainer_name
		FROM attendance a
		JOIN schedule sch ON sch.schedule_id = a.schedule_id
		JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
		JOIN persons p ON p.person_id = sch.trainer_id
		WHERE a.client_id = %s
		  AND sch.start_time >= NOW() - INTERVAL '1 day'
		ORDER BY sch.start_time ASC
		LIMIT 8
		""",
		(client_id,),
	)

	stats = fetch_one(
		"""
		SELECT
			COUNT(*) FILTER (WHERE status = 'attended') AS total_attended,
			COUNT(*) FILTER (WHERE status = 'booked') AS total_booked,
			COUNT(*) FILTER (WHERE status = 'no-show') AS total_no_show
		FROM attendance
		WHERE client_id = %s
		""",
		(client_id,),
	)

	attended_days = fetch_all(
		"""
		SELECT DISTINCT sch.start_time::date AS day
		FROM attendance a
		JOIN schedule sch ON sch.schedule_id = a.schedule_id
		WHERE a.client_id = %s
		  AND a.status = 'attended'
		  AND sch.start_time >= NOW() - INTERVAL '180 day'
		ORDER BY day ASC
		""",
		(client_id,),
	)

	return {
		"profile": profile,
		"active_subscription": active_subscription,
		"upcoming_sessions": upcoming_sessions,
		"stats": stats or {},
		"attended_days": attended_days,
	}


@app.get("/api/trainer/{trainer_id}/overview")
def trainer_overview(trainer_id: UUID, request: Request):
	user = _require_role(request, {ROLE_TRAINER, ROLE_ADMIN})
	if user.get("role") == ROLE_TRAINER and user.get("person_id") != str(trainer_id):
		raise HTTPException(status_code=403, detail="Access denied for this trainer")

	profile = fetch_one(
		"""
		SELECT
			p.person_id AS trainer_id,
			CONCAT(p.first_name, ' ', p.last_name) AS full_name,
			sp.qualification_lvl,
			sp.rate_per_session,
			COALESCE(STRING_AGG(s.name, ', ' ORDER BY s.name), '') AS specializations
		FROM persons p
		JOIN staff_profiles sp ON sp.person_id = p.person_id
		LEFT JOIN staff_specializations ss ON ss.staff_id = p.person_id
		LEFT JOIN specializations s ON s.specialization_id = ss.specialization_id
		WHERE p.person_id = %s AND sp.role = 'trainer'
		GROUP BY p.person_id, p.first_name, p.last_name, sp.qualification_lvl, sp.rate_per_session
		""",
		(trainer_id,),
	)
	if not profile:
		raise HTTPException(status_code=404, detail="Trainer not found")

	upcoming_classes = fetch_all(
		"""
		SELECT
			sch.schedule_id,
			wt.title,
			wt.category,
			sch.start_time,
			sch.end_time,
			sch.room_name,
			wt.max_capacity,
			COUNT(a.attendance_id) FILTER (WHERE a.status IN ('booked', 'attended')) AS occupied_slots
		FROM schedule sch
		JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
		LEFT JOIN attendance a ON a.schedule_id = sch.schedule_id
		WHERE sch.trainer_id = %s
		  AND sch.start_time >= NOW() - INTERVAL '1 day'
		  AND sch.is_cancelled = FALSE
		GROUP BY sch.schedule_id, wt.title, wt.category, sch.start_time, sch.end_time, sch.room_name, wt.max_capacity
		ORDER BY sch.start_time ASC
		LIMIT 8
		""",
		(trainer_id,),
	)

	assigned_client_schedule = fetch_all(
		"""
		SELECT
			a.attendance_id,
			a.status,
			sch.start_time,
			sch.end_time,
			sch.room_name,
			wt.title,
			CONCAT(pc.first_name, ' ', pc.last_name) AS client_name,
			vs.membership_name,
			vs.end_date AS subscription_end_date
		FROM attendance a
		JOIN schedule sch ON sch.schedule_id = a.schedule_id
		JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
		JOIN persons pc ON pc.person_id = a.client_id
		LEFT JOIN v_active_subscriptions vs ON vs.subscription_id = a.subscription_id
		WHERE sch.trainer_id = %s
		  AND sch.start_time >= NOW() - INTERVAL '1 day'
		ORDER BY sch.start_time ASC, client_name ASC
		LIMIT 30
		""",
		(trainer_id,),
	)

	performance = fetch_all(
		"""
		SELECT period_month, classes_conducted, total_clients_attended, avg_occupancy_rate_percent
		FROM v_trainer_performance
		WHERE trainer_id = %s
		ORDER BY period_month DESC
		LIMIT 6
		""",
		(trainer_id,),
	)

	return {
		"profile": profile,
		"upcoming_classes": upcoming_classes,
		"performance": list(reversed(performance)),
		"assigned_client_schedule": assigned_client_schedule,
	}


@app.get("/api/admin/metrics")
def admin_metrics(request: Request):
	_require_role(request, {ROLE_ADMIN})
	return _admin_metrics()


@app.get("/api/trainers")
def get_trainers(request: Request):
	_require_auth(request)
	return fetch_all(
		"""
		SELECT
			p.person_id AS trainer_id,
			p.first_name,
			p.last_name,
			sp.qualification_lvl,
			sp.rate_per_session,
			COALESCE(STRING_AGG(s.name, ', ' ORDER BY s.name), '') AS specializations
		FROM persons p
		JOIN staff_profiles sp ON sp.person_id = p.person_id
		LEFT JOIN staff_specializations ss ON ss.staff_id = p.person_id
		LEFT JOIN specializations s ON s.specialization_id = ss.specialization_id
		WHERE sp.role = 'trainer'
		GROUP BY p.person_id, p.first_name, p.last_name, sp.qualification_lvl, sp.rate_per_session
		ORDER BY p.last_name, p.first_name
		"""
	)


@app.get("/api/membership-types")
def get_membership_types(request: Request):
	_require_auth(request)
	return fetch_all(
		"""
		SELECT
			membership_type_id,
			name,
			description,
			price,
			duration_days,
			max_visits,
			max_freezes,
			guest_visits
		FROM membership_types
		ORDER BY price
		"""
	)


@app.get("/api/schedule")
def get_schedule(request: Request, date_from: date | None = None, date_to: date | None = None):
	_require_auth(request)
	where = []
	params: list = []

	if date_from:
		where.append("sch.start_time::date >= %s")
		params.append(date_from)
	if date_to:
		where.append("sch.start_time::date <= %s")
		params.append(date_to)

	where_sql = f"WHERE {' AND '.join(where)}" if where else ""

	return fetch_all(
		f"""
		SELECT
			sch.schedule_id,
			sch.start_time,
			sch.end_time,
			sch.room_name,
			sch.is_cancelled,
			wt.title AS workout_title,
			wt.category,
			wt.max_capacity,
			CONCAT(p.first_name, ' ', p.last_name) AS trainer_name,
			COUNT(a.attendance_id) FILTER (WHERE a.status IN ('booked', 'attended')) AS occupied_slots
		FROM schedule sch
		JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
		JOIN persons p ON p.person_id = sch.trainer_id
		LEFT JOIN attendance a ON a.schedule_id = sch.schedule_id
		{where_sql}
		GROUP BY sch.schedule_id, sch.start_time, sch.end_time, sch.room_name, sch.is_cancelled,
				 wt.title, wt.category, wt.max_capacity, trainer_name
		ORDER BY sch.start_time ASC
		""",
		tuple(params) if params else None,
	)


@app.get("/api/subscriptions/active")
def get_active_subscriptions(request: Request):
	_require_role(request, {ROLE_ADMIN, ROLE_TRAINER})
	return fetch_all(
		"""
		SELECT *
		FROM v_active_subscriptions
		ORDER BY end_date ASC
		"""
	)


@app.post("/api/bookings")
def create_booking(payload: BookingPayload, request: Request):
	user = _require_role(request, {ROLE_CLIENT, ROLE_TRAINER, ROLE_ADMIN})
	if not DEMO_OPEN_ACCESS and user.get("role") == ROLE_CLIENT and user.get("person_id") != str(payload.client_id):
		raise HTTPException(status_code=403, detail="Client can create bookings only for self")

	with transaction() as conn:
		with conn.cursor() as cur:
			cur.execute(
				"""
				SELECT
					sch.schedule_id,
					wt.max_capacity,
					COUNT(a.attendance_id) FILTER (WHERE a.status IN ('booked', 'attended')) AS occupied
				FROM schedule sch
				JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
				LEFT JOIN attendance a ON a.schedule_id = sch.schedule_id
				WHERE sch.schedule_id = %s AND sch.is_cancelled = FALSE
				GROUP BY sch.schedule_id, wt.max_capacity
				""",
				(payload.schedule_id,),
			)
			schedule_data = cur.fetchone()
			if not schedule_data:
				raise HTTPException(status_code=404, detail="Schedule item not found")
			if schedule_data["occupied"] >= schedule_data["max_capacity"]:
				raise HTTPException(status_code=400, detail="No free slots for this session")

			subscription_id = payload.subscription_id
			if subscription_id is None:
				cur.execute(
					"""
					SELECT subscription_id
					FROM subscriptions
					WHERE client_id = %s
					  AND is_paid = TRUE
					  AND start_date <= CURRENT_DATE
					  AND end_date >= CURRENT_DATE
					ORDER BY end_date DESC
					LIMIT 1
					""",
					(payload.client_id,),
				)
				sub = cur.fetchone()
				if not sub:
					raise HTTPException(status_code=400, detail="Client has no active paid subscription")
				subscription_id = sub["subscription_id"]

			cur.execute(
				"""
				INSERT INTO attendance (client_id, schedule_id, subscription_id, status)
				VALUES (%s, %s, %s, 'booked')
				ON CONFLICT (client_id, schedule_id)
				DO UPDATE SET status = 'booked', subscription_id = EXCLUDED.subscription_id
				RETURNING attendance_id
				""",
				(payload.client_id, payload.schedule_id, subscription_id),
			)
			booking = cur.fetchone()

	return {"status": "ok", "attendance_id": booking["attendance_id"]}


@app.post("/api/check-in")
def check_in(payload: CheckInPayload, request: Request):
	user = _require_role(request, {ROLE_TRAINER, ROLE_ADMIN})
	if user.get("role") == ROLE_TRAINER:
		trainer_session = fetch_one(
			"SELECT trainer_id FROM schedule WHERE schedule_id = %s",
			(payload.schedule_id,),
		)
		if not trainer_session or str(trainer_session["trainer_id"]) != user.get("person_id"):
			raise HTTPException(status_code=403, detail="Trainer can check-in only own sessions")

	with transaction() as conn:
		with conn.cursor() as cur:
			cur.execute("SELECT check_in_client(%s, %s) AS result", (payload.client_id, payload.schedule_id))
			outcome = cur.fetchone()

	if not outcome:
		raise HTTPException(status_code=400, detail="Check-in failed")
	return {"status": "ok", "result": outcome["result"]}


@app.post("/api/subscriptions")
def purchase_subscription(payload: PurchaseSubscriptionPayload, request: Request):
	user = _require_role(request, {ROLE_CLIENT, ROLE_ADMIN})
	if not DEMO_OPEN_ACCESS and user.get("role") == ROLE_CLIENT and user.get("person_id") != str(payload.client_id):
		raise HTTPException(status_code=403, detail="Client can buy subscription only for self")

	with transaction() as conn:
		with conn.cursor() as cur:
			cur.execute(
				"""
				SELECT membership_type_id, price, duration_days, max_visits
				FROM membership_types
				WHERE membership_type_id = %s
				""",
				(payload.membership_type_id,),
			)
			mt = cur.fetchone()
			if not mt:
				raise HTTPException(status_code=404, detail="Membership type not found")

			if payload.trainer_id is not None:
				cur.execute(
					"""
					SELECT 1
					FROM staff_profiles
					WHERE person_id = %s AND role = 'trainer'
					LIMIT 1
					""",
					(payload.trainer_id,),
				)
				if not cur.fetchone():
					raise HTTPException(status_code=404, detail="Trainer not found")

			cur.execute(
				"""
				INSERT INTO subscriptions (
					client_id,
					membership_type_id,
					start_date,
					end_date,
					is_paid,
					sold_by_staff_id
				) VALUES (
					%s,
					%s,
					COALESCE(%s, CURRENT_DATE),
					COALESCE(%s, CURRENT_DATE) + (%s || ' days')::interval,
					%s,
					%s
				)
				RETURNING subscription_id, start_date, end_date
				""",
				(
					payload.client_id,
					payload.membership_type_id,
					payload.start_date,
					payload.start_date,
					mt["duration_days"],
					payload.is_paid,
					payload.sold_by_staff_id,
				),
			)
			subscription = cur.fetchone()

			cur.execute(
				"""
				INSERT INTO transactions (
					client_id,
					staff_id,
					service_type,
					reference_id,
					amount,
					payment_status,
					notes
				) VALUES (%s, %s, 'subscription', %s, %s, %s, %s)
				RETURNING transaction_id
				""",
				(
					payload.client_id,
					payload.sold_by_staff_id,
					subscription["subscription_id"],
					mt["price"],
					"paid" if payload.is_paid else "deposit",
					"Created via API",
				),
			)
			tx = cur.fetchone()

			auto_booked = 0
			if payload.auto_book_schedule and payload.trainer_id is not None and payload.is_paid:
				auto_limit = mt.get("max_visits") if mt.get("max_visits") is not None else 12
				cur.execute(
					"""
					SELECT COUNT(*) AS future_slots
					FROM schedule sch
					WHERE sch.trainer_id = %s
					  AND sch.is_cancelled = FALSE
					  AND sch.start_time::date BETWEEN %s AND %s
					  AND sch.start_time >= NOW()
					""",
					(
						payload.trainer_id,
						subscription["start_date"],
						subscription["end_date"],
					),
				)
				future_slots = cur.fetchone()
				if (future_slots["future_slots"] if future_slots else 0) == 0:
					cur.execute(
						"""
						WITH wt AS (
							SELECT COALESCE(
								(
									SELECT sch.workout_type_id
									FROM schedule sch
									WHERE sch.trainer_id = %s
									ORDER BY sch.start_time DESC
									LIMIT 1
								),
								(
									SELECT workout_type_id
									FROM workout_types
									ORDER BY title
									LIMIT 1
								)
							) AS workout_type_id
						), slots AS (
							SELECT (
								date_trunc('day', NOW())
								+ INTERVAL '1 day'
								+ (g.n - 1) * INTERVAL '2 day'
								+ INTERVAL '18 hour'
							) AS start_time
							FROM generate_series(1, LEAST(%s, 8)) AS g(n)
						)
						INSERT INTO schedule (
							schedule_id,
							workout_type_id,
							trainer_id,
							room_name,
							start_time,
							end_time,
							is_cancelled
						)
						SELECT
							gen_random_uuid(),
							wt.workout_type_id,
							%s,
							'Auto Group',
							slots.start_time,
							slots.start_time + INTERVAL '1 hour',
							FALSE
						FROM wt
						CROSS JOIN slots
						WHERE slots.start_time::date BETWEEN %s AND %s
						  AND NOT EXISTS (
							SELECT 1
							FROM schedule sch
							WHERE sch.trainer_id = %s
							  AND sch.start_time = slots.start_time
						  )
						""",
						(
							payload.trainer_id,
							auto_limit,
							payload.trainer_id,
							subscription["start_date"],
							subscription["end_date"],
							payload.trainer_id,
						),
					)
				cur.execute(
					"""
					WITH trainer_slots AS (
						SELECT
							sch.schedule_id,
							COUNT(a.attendance_id) FILTER (WHERE a.status IN ('booked', 'attended')) AS occupied,
							wt.max_capacity
						FROM schedule sch
						JOIN workout_types wt ON wt.workout_type_id = sch.workout_type_id
						LEFT JOIN attendance a ON a.schedule_id = sch.schedule_id
						WHERE sch.trainer_id = %s
						  AND sch.is_cancelled = FALSE
						  AND sch.start_time::date BETWEEN %s AND %s
						  AND sch.start_time >= NOW()
						GROUP BY sch.schedule_id, wt.max_capacity, sch.start_time
						ORDER BY sch.start_time ASC
						LIMIT %s
					), inserted AS (
						INSERT INTO attendance (client_id, schedule_id, subscription_id, status)
						SELECT %s, ts.schedule_id, %s, 'booked'
						FROM trainer_slots ts
						WHERE ts.occupied < ts.max_capacity
						ON CONFLICT (client_id, schedule_id)
						DO UPDATE SET status = 'booked', subscription_id = EXCLUDED.subscription_id
						RETURNING attendance_id
					)
					SELECT COUNT(*) AS auto_booked FROM inserted
					""",
					(
						payload.trainer_id,
						subscription["start_date"],
						subscription["end_date"],
						auto_limit,
						payload.client_id,
						subscription["subscription_id"],
					),
				)
				auto_booked_result = cur.fetchone()
				auto_booked = auto_booked_result["auto_booked"] if auto_booked_result else 0

	return {
		"status": "ok",
		"subscription_id": subscription["subscription_id"],
		"transaction_id": tx["transaction_id"],
		"start_date": subscription["start_date"],
		"end_date": subscription["end_date"],
		"trainer_id": payload.trainer_id,
		"auto_booked": auto_booked,
	}


@app.post("/api/transactions")
def create_transaction(payload: TransactionPayload, request: Request):
	user = _require_role(request, {ROLE_TRAINER, ROLE_ADMIN})
	if user.get("role") == ROLE_TRAINER:
		payload.staff_id = UUID(user.get("person_id"))

	tx = fetch_one(
		"""
		INSERT INTO transactions (
			client_id,
			staff_id,
			service_type,
			reference_id,
			amount,
			payment_status,
			notes
		) VALUES (%s, %s, %s, %s, %s, %s, %s)
		RETURNING transaction_id
		""",
		(
			payload.client_id,
			payload.staff_id,
			payload.service_type,
			payload.reference_id,
			payload.amount,
			payload.payment_status,
			payload.notes,
		),
	)
	return {"status": "ok", "transaction_id": tx["transaction_id"]}


@app.get("/api/analytics/{view_name}")
def get_analytics_view(view_name: str, request: Request, limit: int = Query(default=50, ge=1, le=500)):
	_require_role(request, {ROLE_ADMIN})
	if view_name not in ALLOWED_ANALYTICS_VIEWS:
		raise HTTPException(status_code=404, detail="Unknown analytics view")

	rows = fetch_all(f"SELECT * FROM {view_name} LIMIT %s", (limit,))
	return {"view": view_name, "rows": rows}
