import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.getenv(
	"DATABASE_URL",
	"postgresql://postgres:postgres@localhost:5432/pulse",
)


def get_connection() -> psycopg.Connection:
	return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@contextmanager
def transaction():
	conn = get_connection()
	try:
		with conn.transaction():
			yield conn
	finally:
		conn.close()


def fetch_all(query: str, params: tuple | dict | None = None) -> list[dict]:
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute(query, params)
			return list(cur.fetchall())


def fetch_one(query: str, params: tuple | dict | None = None) -> dict | None:
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute(query, params)
			return cur.fetchone()


def execute(query: str, params: tuple | dict | None = None) -> None:
	with get_connection() as conn:
		with conn.cursor() as cur:
			cur.execute(query, params)
		conn.commit()
