
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Jigyasa - Book Transactions", layout="wide")
st.title("📚 Jigyasa - Issue a Book")

# Connect to SQLite
conn = sqlite3.connect("library.db", check_same_thread=False)
c = conn.cursor()

def get_books_matching(query):
    df = pd.read_sql_query("SELECT id, title FROM books WHERE title LIKE ? AND available_copies > 0", conn, params=(query + '%',))
    return df

def get_students_matching(query):
    df = pd.read_sql_query("SELECT id, name FROM students WHERE name LIKE ?", conn, params=(query + '%',))
    return df

book_query = st.text_input("Start typing book title")
book_matches = get_books_matching(book_query) if book_query else pd.DataFrame()
book_title = st.selectbox("Select Book", book_matches["title"]) if not book_matches.empty else None

student_query = st.text_input("Start typing student name")
student_matches = get_students_matching(student_query) if student_query else pd.DataFrame()
student_name = st.selectbox("Select Student", student_matches["name"]) if not student_matches.empty else None

if st.button("📖 Lend Book") and book_title and student_name:
    book_id = book_matches[book_matches["title"] == book_title]["id"].values[0]
    student_id = student_matches[student_matches["name"] == student_name]["id"].values[0]
    borrow_date = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    c.execute("INSERT INTO transactions (student_id, book_id, borrow_date, due_date, return_date) VALUES (?, ?, ?, ?, NULL)",
              (student_id, book_id, borrow_date, due_date))
    c.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (book_id,))
    conn.commit()
    st.success(f"Book '{book_title}' issued to {student_name}. Due on {due_date}.")

# Show recent transactions
st.markdown("### 📄 Recent Transactions")
query = """
SELECT t.id, s.name as student_name, b.title as book_title, t.borrow_date, t.due_date, t.return_date
FROM transactions t
JOIN students s ON t.student_id = s.id
JOIN books b ON t.book_id = b.id
ORDER BY t.borrow_date DESC
LIMIT 10
"""
df = pd.read_sql_query(query, conn)
st.dataframe(df)
