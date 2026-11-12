import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


DB_PATH = Path(os.environ.get("LIBRARY_DB_PATH", Path(__file__).with_name("library.db")))


def get_connection() -> sqlite3.Connection:
	connection = sqlite3.connect(DB_PATH, timeout=10)
	connection.row_factory = sqlite3.Row
	connection.execute("PRAGMA foreign_keys = ON")
	return connection


def init_db() -> None:
	with get_connection() as connection:
		connection.executescript(
			"""
			CREATE TABLE IF NOT EXISTS books (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				isbn TEXT UNIQUE,
				title TEXT NOT NULL,
				author TEXT NOT NULL,
				publisher TEXT,
				category TEXT NOT NULL,
				publication_year INTEGER,
				total_copies INTEGER NOT NULL CHECK (total_copies >= 0),
				available_copies INTEGER NOT NULL CHECK (
					available_copies >= 0 AND available_copies <= total_copies
				),
				is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
			);

			CREATE TABLE IF NOT EXISTS members (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				member_code TEXT NOT NULL UNIQUE,
				full_name TEXT NOT NULL,
				email TEXT,
				phone TEXT,
				department TEXT NOT NULL,
				is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
			);

			CREATE TABLE IF NOT EXISTS loans (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				book_id INTEGER NOT NULL REFERENCES books(id),
				member_id INTEGER NOT NULL REFERENCES members(id),
				issue_date TEXT NOT NULL,
				due_date TEXT NOT NULL,
				return_date TEXT,
				CHECK (due_date >= issue_date),
				CHECK (return_date IS NULL OR return_date >= issue_date)
			);

			CREATE INDEX IF NOT EXISTS idx_loans_active_due
				ON loans(return_date, due_date);
			CREATE INDEX IF NOT EXISTS idx_loans_book ON loans(book_id);
			CREATE INDEX IF NOT EXISTS idx_loans_member ON loans(member_id);
			"""
		)


def _clean_optional(value: str | None) -> str | None:
	cleaned = (value or "").strip()
	return cleaned or None


def add_book(
	isbn: str,
	title: str,
	author: str,
	publisher: str,
	category: str,
	publication_year: int | None,
	total_copies: int,
) -> int:
	if total_copies < 0:
		raise ValueError("Total copies cannot be negative.")
	with get_connection() as connection:
		cursor = connection.execute(
			"""INSERT INTO books
			   (isbn, title, author, publisher, category, publication_year,
				total_copies, available_copies)
			   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
			(
				_clean_optional(isbn), title.strip(), author.strip(),
				_clean_optional(publisher), category.strip(), publication_year,
				total_copies, total_copies,
			),
		)
		return int(cursor.lastrowid)


def update_book(
	book_id: int,
	isbn: str,
	title: str,
	author: str,
	publisher: str,
	category: str,
	publication_year: int | None,
	total_copies: int,
) -> None:
	with get_connection() as connection:
		active_loans = connection.execute(
			"SELECT COUNT(*) FROM loans WHERE book_id = ? AND return_date IS NULL",
			(book_id,),
		).fetchone()[0]
		if total_copies < active_loans:
			raise ValueError(f"At least {active_loans} copies are currently on loan.")
		connection.execute(
			"""UPDATE books SET isbn = ?, title = ?, author = ?, publisher = ?,
			   category = ?, publication_year = ?, total_copies = ?,
			   available_copies = ? - ? WHERE id = ? AND is_active = 1""",
			(
				_clean_optional(isbn), title.strip(), author.strip(),
				_clean_optional(publisher), category.strip(), publication_year,
				total_copies, total_copies, active_loans, book_id,
			),
		)


def archive_book(book_id: int) -> None:
	with get_connection() as connection:
		active_loans = connection.execute(
			"SELECT COUNT(*) FROM loans WHERE book_id = ? AND return_date IS NULL",
			(book_id,),
		).fetchone()[0]
		if active_loans:
			raise ValueError("Return all copies before archiving this book.")
		connection.execute("UPDATE books SET is_active = 0 WHERE id = ?", (book_id,))


def restore_book(book_id: int) -> None:
	with get_connection() as connection:
		connection.execute("UPDATE books SET is_active = 1 WHERE id = ?", (book_id,))


def add_member(
	member_code: str,
	full_name: str,
	email: str,
	phone: str,
	department: str,
) -> int:
	with get_connection() as connection:
		cursor = connection.execute(
			"""INSERT INTO members
			   (member_code, full_name, email, phone, department)
			   VALUES (?, ?, ?, ?, ?)""",
			(
				member_code.strip().upper(), full_name.strip(),
				_clean_optional(email), _clean_optional(phone), department.strip(),
			),
		)
		return int(cursor.lastrowid)


def update_member(
	member_id: int,
	member_code: str,
	full_name: str,
	email: str,
	phone: str,
	department: str,
) -> None:
	with get_connection() as connection:
		connection.execute(
			"""UPDATE members SET member_code = ?, full_name = ?, email = ?,
			   phone = ?, department = ? WHERE id = ? AND is_active = 1""",
			(
				member_code.strip().upper(), full_name.strip(),
				_clean_optional(email), _clean_optional(phone), department.strip(),
				member_id,
			),
		)


def archive_member(member_id: int) -> None:
	with get_connection() as connection:
		active_loans = connection.execute(
			"SELECT COUNT(*) FROM loans WHERE member_id = ? AND return_date IS NULL",
			(member_id,),
		).fetchone()[0]
		if active_loans:
			raise ValueError("Return all borrowed books before archiving this member.")
		connection.execute("UPDATE members SET is_active = 0 WHERE id = ?", (member_id,))


def restore_member(member_id: int) -> None:
	with get_connection() as connection:
		connection.execute("UPDATE members SET is_active = 1 WHERE id = ?", (member_id,))


def checkout_book(book_id: int, member_id: int, due_date: date) -> int:
	issue_date = date.today()
	if due_date < issue_date:
		raise ValueError("Due date cannot be before today.")
	with get_connection() as connection:
		connection.execute("BEGIN IMMEDIATE")
		book = connection.execute(
			"SELECT available_copies FROM books WHERE id = ? AND is_active = 1",
			(book_id,),
		).fetchone()
		member = connection.execute(
			"SELECT id FROM members WHERE id = ? AND is_active = 1", (member_id,)
		).fetchone()
		if book is None:
			raise ValueError("This book is not in the active catalog.")
		if member is None:
			raise ValueError("This member is not active.")
		if book["available_copies"] < 1:
			raise ValueError("No copies of this book are currently available.")
		connection.execute(
			"UPDATE books SET available_copies = available_copies - 1 WHERE id = ?",
			(book_id,),
		)
		cursor = connection.execute(
			"INSERT INTO loans (book_id, member_id, issue_date, due_date) VALUES (?, ?, ?, ?)",
			(book_id, member_id, issue_date.isoformat(), due_date.isoformat()),
		)
		return int(cursor.lastrowid)


def return_loan(loan_id: int) -> None:
	with get_connection() as connection:
		connection.execute("BEGIN IMMEDIATE")
		loan = connection.execute(
			"SELECT book_id FROM loans WHERE id = ? AND return_date IS NULL", (loan_id,)
		).fetchone()
		if loan is None:
			raise ValueError("This loan is already returned or does not exist.")
		connection.execute(
			"UPDATE loans SET return_date = ? WHERE id = ? AND return_date IS NULL",
			(date.today().isoformat(), loan_id),
		)
		connection.execute(
			"UPDATE books SET available_copies = available_copies + 1 WHERE id = ?",
			(loan["book_id"],),
		)


def get_books(search: str = "", include_archived: bool = False) -> list[dict[str, Any]]:
	conditions = []
	parameters: list[Any] = []
	if not include_archived:
		conditions.append("b.is_active = 1")
	if search.strip():
		term = f"%{search.strip()}%"
		conditions.append("(b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? OR b.category LIKE ?)")
		parameters.extend([term, term, term, term])
	where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	with get_connection() as connection:
		rows = connection.execute(
			f"""SELECT b.*, b.total_copies - b.available_copies AS checked_out
				FROM books b {where} ORDER BY b.title COLLATE NOCASE""",
			parameters,
		).fetchall()
		return [dict(row) for row in rows]


def get_members(search: str = "", include_archived: bool = False) -> list[dict[str, Any]]:
	conditions = []
	parameters: list[Any] = []
	if not include_archived:
		conditions.append("m.is_active = 1")
	if search.strip():
		term = f"%{search.strip()}%"
		conditions.append("(m.full_name LIKE ? OR m.member_code LIKE ? OR m.department LIKE ?)")
		parameters.extend([term, term, term])
	where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	with get_connection() as connection:
		rows = connection.execute(
			f"SELECT m.* FROM members m {where} ORDER BY m.full_name COLLATE NOCASE",
			parameters,
		).fetchall()
		return [dict(row) for row in rows]


def get_loans(status: str = "All", search: str = "") -> list[dict[str, Any]]:
	conditions = []
	parameters: list[Any] = []
	today = date.today().isoformat()
	if status == "On loan":
		conditions.append("l.return_date IS NULL AND l.due_date >= ?")
		parameters.append(today)
	elif status == "Overdue":
		conditions.append("l.return_date IS NULL AND l.due_date < ?")
		parameters.append(today)
	elif status == "Returned":
		conditions.append("l.return_date IS NOT NULL")
	if search.strip():
		term = f"%{search.strip()}%"
		conditions.append("(b.title LIKE ? OR m.full_name LIKE ? OR m.member_code LIKE ?)")
		parameters.extend([term, term, term])
	where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	with get_connection() as connection:
		rows = connection.execute(
			f"""SELECT l.id, b.title AS book_title, b.isbn, m.full_name,
					   m.member_code, l.issue_date, l.due_date, l.return_date,
					   CASE WHEN l.return_date IS NOT NULL THEN 'Returned'
							WHEN l.due_date < ? THEN 'Overdue'
							ELSE 'On loan' END AS status
				FROM loans l
				JOIN books b ON b.id = l.book_id
				JOIN members m ON m.id = l.member_id
				{where}
				ORDER BY CASE WHEN l.return_date IS NULL THEN 0 ELSE 1 END,
						 l.due_date, l.id DESC""",
			[today, *parameters],
		).fetchall()
		return [dict(row) for row in rows]


def get_dashboard_stats() -> dict[str, int]:
	with get_connection() as connection:
		row = connection.execute(
			"""SELECT
				(SELECT COUNT(*) FROM books WHERE is_active = 1) AS titles,
				(SELECT COALESCE(SUM(total_copies), 0) FROM books WHERE is_active = 1) AS copies,
				(SELECT COALESCE(SUM(available_copies), 0) FROM books WHERE is_active = 1) AS available,
				(SELECT COUNT(*) FROM loans WHERE return_date IS NULL) AS on_loan,
				(SELECT COUNT(*) FROM loans WHERE return_date IS NULL AND due_date < date('now')) AS overdue,
				(SELECT COUNT(*) FROM members WHERE is_active = 1) AS members"""
		).fetchone()
		return dict(row)


def get_category_stats() -> list[dict[str, Any]]:
	with get_connection() as connection:
		rows = connection.execute(
			"""SELECT category, SUM(total_copies) AS copies, COUNT(*) AS titles
			   FROM books WHERE is_active = 1 GROUP BY category
			   ORDER BY copies DESC, category"""
		).fetchall()
		return [dict(row) for row in rows]


def get_popular_books(limit: int = 5) -> list[dict[str, Any]]:
	with get_connection() as connection:
		rows = connection.execute(
			"""SELECT b.title, b.author, COUNT(l.id) AS loans
			   FROM books b LEFT JOIN loans l ON l.book_id = b.id
			   WHERE b.is_active = 1 GROUP BY b.id
			   ORDER BY loans DESC, b.title COLLATE NOCASE LIMIT ?""",
			(limit,),
		).fetchall()
		return [dict(row) for row in rows]
