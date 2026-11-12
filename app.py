import sqlite3
from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

import database


st.set_page_config(page_title="BMSIT Library", layout="wide")
database.init_db()


def show_database_error(error: Exception) -> None:
	message = str(error)
	if isinstance(error, sqlite3.IntegrityError) and "books.isbn" in message:
		st.error("That ISBN is already in the catalog.")
	elif isinstance(error, sqlite3.IntegrityError) and "members.member_code" in message:
		st.error("That member ID is already registered.")
	else:
		st.error(message)


def show_table(rows: list[dict[str, Any]], alt: str) -> None:
	if rows:
		st.dataframe(pd.DataFrame(rows), hide_index=True, alt=alt)
	else:
		st.info("No records match this view yet.")


def render_metric_card(column: Any, label: str, value: str, icon: str, color: str) -> None:
	with column:
		st.badge(label, icon=f":material/{icon}:", color=color)
		st.metric(label, value, label_visibility="collapsed")


def navigate_to(page: str) -> None:
	st.session_state["workspace_page"] = page


def download_csv(label: str, rows: list[dict[str, Any]], file_name: str, key: str) -> None:
	if rows:
		csv_data = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
		st.download_button(
			label,
			csv_data,
			file_name=file_name,
			mime="text/csv",
			key=key,
			icon=":material/download:",
		)
	else:
		st.button(label, disabled=True, key=key, icon=":material/download:")


def render_dashboard() -> None:
	st.title("Library overview", icon=":material/dashboard:")
	st.caption("BMSIT Engineering College | Inventory and circulation")
	with st.container(horizontal=True):
		st.button(
			"Add a book", icon=":material/add:", key="quick_add_book",
			on_click=navigate_to, args=("Books",),
		)
		st.button(
			"Register a member", icon=":material/person_add:", key="quick_add_member",
			on_click=navigate_to, args=("Members",),
		)
		st.button(
			"Check out a book", icon=":material/bookmark_add:", type="primary",
			key="quick_checkout", on_click=navigate_to, args=("Circulation",),
		)
	stats = database.get_dashboard_stats()
	metric_columns = st.columns(4, border=True)
	for column, label, value, icon in [
		(metric_columns[0], "Catalog titles", f"{stats['titles']:,}", "menu_book"),
		(metric_columns[1], "Total copies", f"{stats['copies']:,}", "library_books"),
		(metric_columns[2], "Available copies", f"{stats['available']:,}", "check_circle"),
		(metric_columns[3], "Currently on loan", f"{stats['on_loan']:,}", "swap_horiz"),
	]:
		color = {"Catalog titles": "blue", "Total copies": "violet", "Available copies": "green"}.get(label, "orange")
		render_metric_card(column, label, value, icon, color)

	detail_columns = st.columns(3, border=True)
	render_metric_card(detail_columns[0], "Active members", f"{stats['members']:,}", "group", "blue")
	render_metric_card(detail_columns[1], "Overdue loans", f"{stats['overdue']:,}", "schedule", "red")
	render_metric_card(
		detail_columns[2],
		"Availability rate",
		f"{(stats['available'] / stats['copies'] * 100) if stats['copies'] else 0:.0f}%",
		"donut_large",
		"green",
	)

	chart_columns = st.columns(2)
	categories = database.get_category_stats()
	with chart_columns[0]:
		with st.container(border=True):
			st.subheader("Copies by category", icon=":material/category:")
			if categories:
				st.bar_chart(pd.DataFrame(categories), x="category", y="copies", alt="Available inventory copies by category")
			else:
				st.info("Add books to see category distribution.")
	with chart_columns[1]:
		with st.container(border=True):
			st.subheader("Most borrowed titles", icon=":material/trending_up:")
			popular = [book for book in database.get_popular_books() if book["loans"]]
			if popular:
				st.bar_chart(pd.DataFrame(popular), x="title", y="loans", alt="Most borrowed books by loan count")
			else:
				st.info("Checkout activity will appear here.")

	overdue = database.get_loans("Overdue")
	st.subheader("Overdue attention", icon=":material/warning:")
	if overdue:
		show_table(overdue, "Overdue loans with member and due-date details")
	else:
		st.success("There are no overdue books.", icon=":material/check_circle:")

	st.subheader("Recent circulation", icon=":material/history:")
	show_table(database.get_loans()[:8], "Recent library loans and returns")


def render_books() -> None:
	st.title("Book catalog", icon=":material/library_books:")
	st.caption("Maintain titles, copy counts, and catalog status.")
	add_tab, catalog_tab = st.tabs(["Add a book", "Catalog"])

	with add_tab:
		with st.form("add_book_form", clear_on_submit=True):
			title = st.text_input("Book title")
			author = st.text_input("Author")
			isbn = st.text_input("ISBN", help="Optional; ISBN values must be unique when supplied.")
			publisher = st.text_input("Publisher")
			category = st.text_input("Category", placeholder="For example, Computer Science")
			year = st.number_input("Publication year", min_value=0, max_value=date.today().year + 1, value=0)
			copies = st.number_input("Total copies", min_value=0, step=1, value=1)
			submitted = st.form_submit_button("Add book", type="primary", icon=":material/add:")
		if submitted:
			if not title.strip() or not author.strip() or not category.strip():
				st.error("Title, author, and category are required.")
			else:
				try:
					database.add_book(isbn, title, author, publisher, category, year or None, int(copies))
					st.success(f'Added "{title.strip()}" to the catalog.')
				except (sqlite3.IntegrityError, ValueError) as error:
					show_database_error(error)

	with catalog_tab:
		search = st.text_input("Search catalog", placeholder="Title, author, ISBN, or category", key="book_search")
		include_archived = st.checkbox("Include archived books", key="include_archived_books")
		books = database.get_books(search, include_archived)
		display_books = [
			{
				"Title": book["title"],
				"Author": book["author"],
				"ISBN": book["isbn"] or "",
				"Category": book["category"],
				"Year": book["publication_year"] or "",
				"Total": book["total_copies"],
				"Available": book["available_copies"],
				"On loan": book["checked_out"],
				"Status": "Active" if book["is_active"] else "Archived",
			}
			for book in books
		]
		show_table(display_books, "Book catalog with total, available, and checked-out copy counts")

		if books:
			book_by_id = {book["id"]: book for book in books}
			selected_id = st.selectbox(
				"Manage a book",
				options=list(book_by_id),
				format_func=lambda book_id: f"{book_by_id[book_id]['title']} | {book_by_id[book_id]['author']}",
				key="manage_book_id",
			)
			selected = book_by_id[selected_id]
			if selected["is_active"]:
				with st.expander("Edit selected book"):
					with st.form(f"edit_book_{selected_id}"):
						edit_title = st.text_input("Book title", value=selected["title"], key=f"edit_title_{selected_id}")
						edit_author = st.text_input("Author", value=selected["author"], key=f"edit_author_{selected_id}")
						edit_isbn = st.text_input("ISBN", value=selected["isbn"] or "", key=f"edit_isbn_{selected_id}")
						edit_publisher = st.text_input("Publisher", value=selected["publisher"] or "", key=f"edit_publisher_{selected_id}")
						edit_category = st.text_input("Category", value=selected["category"], key=f"edit_category_{selected_id}")
						edit_year = st.number_input(
							"Publication year", min_value=0, max_value=date.today().year + 1,
							value=selected["publication_year"] or 0, key=f"edit_year_{selected_id}",
						)
						edit_copies = st.number_input(
							"Total copies", min_value=0, step=1, value=selected["total_copies"],
							key=f"edit_copies_{selected_id}",
						)
						save_book = st.form_submit_button("Save changes", type="primary", icon=":material/save:")
					if save_book:
						if not edit_title.strip() or not edit_author.strip() or not edit_category.strip():
							st.error("Title, author, and category are required.")
						else:
							try:
								database.update_book(
									selected_id, edit_isbn, edit_title, edit_author,
									edit_publisher, edit_category, edit_year or None, int(edit_copies),
								)
								st.success("Book details updated.")
							except (sqlite3.IntegrityError, ValueError) as error:
								show_database_error(error)
				if st.button("Archive selected book", key=f"archive_book_{selected_id}", icon=":material/archive:"):
					try:
						database.archive_book(selected_id)
						st.success('Book archived. Turn on "Include archived books" to restore it.')
					except ValueError as error:
						show_database_error(error)
			elif st.button("Restore selected book", key=f"restore_book_{selected_id}", icon=":material/unarchive:"):
				try:
					database.restore_book(selected_id)
					st.success("Book restored to the active catalog.")
				except sqlite3.IntegrityError as error:
					show_database_error(error)


def render_members() -> None:
	st.title("Library members", icon=":material/groups:")
	st.caption("Manage student and staff borrower records.")
	add_tab, members_tab = st.tabs(["Add a member", "Members"])

	with add_tab:
		with st.form("add_member_form", clear_on_submit=True):
			member_code = st.text_input("Member ID", placeholder="For example, 1BM23CS001")
			full_name = st.text_input("Full name")
			department = st.text_input("Department", placeholder="For example, Computer Science")
			email = st.text_input("Email")
			phone = st.text_input("Phone")
			submitted = st.form_submit_button("Add member", type="primary", icon=":material/person_add:")
		if submitted:
			if not member_code.strip() or not full_name.strip() or not department.strip():
				st.error("Member ID, full name, and department are required.")
			else:
				try:
					database.add_member(member_code, full_name, email, phone, department)
					st.success(f"Registered {full_name.strip()}.")
				except (sqlite3.IntegrityError, ValueError) as error:
					show_database_error(error)

	with members_tab:
		search = st.text_input("Search members", placeholder="Name, member ID, or department", key="member_search")
		include_archived = st.checkbox("Include archived members", key="include_archived_members")
		members = database.get_members(search, include_archived)
		display_members = [
			{
				"Member ID": member["member_code"],
				"Name": member["full_name"],
				"Department": member["department"],
				"Email": member["email"] or "",
				"Phone": member["phone"] or "",
				"Status": "Active" if member["is_active"] else "Archived",
			}
			for member in members
		]
		show_table(display_members, "Library members and their registration details")

		if members:
			member_by_id = {member["id"]: member for member in members}
			selected_id = st.selectbox(
				"Manage a member",
				options=list(member_by_id),
				format_func=lambda member_id: f"{member_by_id[member_id]['full_name']} | {member_by_id[member_id]['member_code']}",
				key="manage_member_id",
			)
			selected = member_by_id[selected_id]
			if selected["is_active"]:
				with st.expander("Edit selected member"):
					with st.form(f"edit_member_{selected_id}"):
						edit_code = st.text_input("Member ID", value=selected["member_code"], key=f"edit_code_{selected_id}")
						edit_name = st.text_input("Full name", value=selected["full_name"], key=f"edit_name_{selected_id}")
						edit_department = st.text_input("Department", value=selected["department"], key=f"edit_department_{selected_id}")
						edit_email = st.text_input("Email", value=selected["email"] or "", key=f"edit_email_{selected_id}")
						edit_phone = st.text_input("Phone", value=selected["phone"] or "", key=f"edit_phone_{selected_id}")
						save_member = st.form_submit_button("Save changes", type="primary", icon=":material/save:")
					if save_member:
						if not edit_code.strip() or not edit_name.strip() or not edit_department.strip():
							st.error("Member ID, full name, and department are required.")
						else:
							try:
								database.update_member(
									selected_id, edit_code, edit_name, edit_email,
									edit_phone, edit_department,
								)
								st.success("Member details updated.")
							except (sqlite3.IntegrityError, ValueError) as error:
								show_database_error(error)
				if st.button("Archive selected member", key=f"archive_member_{selected_id}", icon=":material/archive:"):
					try:
						database.archive_member(selected_id)
						st.success('Member archived. Turn on "Include archived members" to restore them.')
					except ValueError as error:
						show_database_error(error)
			elif st.button("Restore selected member", key=f"restore_member_{selected_id}", icon=":material/unarchive:"):
				try:
					database.restore_member(selected_id)
					st.success("Member restored.")
				except sqlite3.IntegrityError as error:
					show_database_error(error)


def render_circulation() -> None:
	st.title("Circulation desk", icon=":material/swap_horiz:")
	st.caption("Issue books, track due dates, and record returns.")
	checkout_tab, loans_tab = st.tabs(["Check out a book", "Loans and returns"])

	with checkout_tab:
		books = [book for book in database.get_books() if book["available_copies"] > 0]
		members = database.get_members()
		if not books:
			st.info("There are no available books to check out.")
		elif not members:
			st.info("Register an active member before checking out a book.")
		else:
			book_by_id = {book["id"]: book for book in books}
			member_by_id = {member["id"]: member for member in members}
			with st.form("checkout_form"):
				book_id = st.selectbox(
					"Book", options=list(book_by_id),
					format_func=lambda item_id: f"{book_by_id[item_id]['title']} | {book_by_id[item_id]['available_copies']} available",
				)
				member_id = st.selectbox(
					"Member", options=list(member_by_id),
					format_func=lambda item_id: f"{member_by_id[item_id]['full_name']} | {member_by_id[item_id]['member_code']}",
				)
				due_date = st.date_input("Due date", value=date.today() + timedelta(days=14), min_value=date.today())
				submitted = st.form_submit_button("Check out book", type="primary", icon=":material/bookmark_add:")
			if submitted:
				try:
					database.checkout_book(book_id, member_id, due_date)
					st.success("Checkout recorded.")
				except ValueError as error:
					show_database_error(error)

	with loans_tab:
		filter_columns = st.columns(2)
		status = filter_columns[0].selectbox("Loan status", ["All", "On loan", "Overdue", "Returned"])
		search = filter_columns[1].text_input("Search loans", placeholder="Book, member, or member ID")
		loans = database.get_loans(status, search)
		show_table(loans, "Loans with book, member, issue date, due date, and status")

		open_loans = [loan for loan in database.get_loans() if loan["return_date"] is None]
		if open_loans:
			loan_by_id = {loan["id"]: loan for loan in open_loans}
			selected_loan = st.selectbox(
				"Record a return",
				options=list(loan_by_id),
				format_func=lambda loan_id: f"{loan_by_id[loan_id]['book_title']} | {loan_by_id[loan_id]['full_name']} | due {loan_by_id[loan_id]['due_date']}",
			)
			if st.button("Mark as returned", type="primary", key="return_loan", icon=":material/assignment_return:"):
				try:
					database.return_loan(selected_loan)
					st.success("Return recorded and available copies updated.")
				except ValueError as error:
					show_database_error(error)
		else:
			st.caption("There are no books awaiting return.")


def render_reports() -> None:
	st.title("Inventory and reports", icon=":material/analytics:")
	st.caption("Review current holdings and export records for further analysis.")
	stats = database.get_dashboard_stats()
	metric_columns = st.columns(4)
	metric_columns[0].metric("Active titles", f"{stats['titles']:,}")
	metric_columns[1].metric("Physical copies", f"{stats['copies']:,}")
	metric_columns[2].metric("Available now", f"{stats['available']:,}")
	metric_columns[3].metric("Overdue", f"{stats['overdue']:,}")

	categories = database.get_category_stats()
	if categories:
		st.subheader("Category inventory")
		show_table(categories, "Book titles and copy totals grouped by category")

	st.subheader("Inventory export")
	inventory = [
		{key: book[key] for key in ("isbn", "title", "author", "publisher", "category", "publication_year", "total_copies", "available_copies", "checked_out")}
		for book in database.get_books()
	]
	download_csv("Download inventory CSV", inventory, "bmsit-library-inventory.csv", "download_inventory")

	st.subheader("Circulation export")
	download_csv(
		"Download loan history CSV",
		database.get_loans(),
		"bmsit-library-loan-history.csv",
		"download_loans",
	)


with st.sidebar:
	st.title("BMSIT Library", icon=":material/local_library:")
	st.caption("Engineering College | Library operations")
	page = st.radio(
		"Workspace",
		["Overview", "Books", "Members", "Circulation", "Reports"],
		label_visibility="collapsed",
		key="workspace_page",
	)
	st.divider()
	st.caption("Local SQLite catalog")

if page == "Overview":
	render_dashboard()
elif page == "Books":
	render_books()
elif page == "Members":
	render_members()
elif page == "Circulation":
	render_circulation()
else:
	render_reports()
