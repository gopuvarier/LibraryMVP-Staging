import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Jigyasa - Staging (Google Sheets)", layout="wide")

st.title("📚 Jigyasa — Staging (Google Sheets Backend)")

# Load service account info from Streamlit secrets
# You must add your service account JSON to Streamlit Secrets under "gcp_service_account"
try:
    sa_info = st.secrets["gcp_service_account"]
except Exception as e:
    st.error("Service account credentials not found in Streamlit secrets. Please add them under 'gcp_service_account'.")
    st.stop()

creds = Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
gc = gspread.authorize(creds)

# Replace with your sheet URL (staging user provided)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1wo5bLQGrxUCSHVWNkjJ7K_6dYKjZxxGYHuWusR5XQY8/edit?usp=sharing"

# Expected sheet/tab names
BOOKS_SHEET = "Books"
STUDENTS_SHEET = "Students"
TX_SHEET = "Transactions"


@st.experimental_memo(ttl=30)
def open_sheet():
    return gc.open_by_url(SHEET_URL)

def read_sheet(sheet_name):
    sh = open_sheet()
    try:
        ws = sh.worksheet(sheet_name)
    except Exception as e:
        st.error(f"Could not open sheet '{sheet_name}'. Check tab name and sharing.")
        st.stop()
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    return df, ws

def append_transaction(student_id, book_id, borrow_date, due_date):
    df_tx, ws_tx = read_sheet(TX_SHEET)
    # compute next id
    if df_tx.empty:
        next_id = 1
    else:
        max_id = pd.to_numeric(df_tx["id"], errors="coerce").max()
        next_id = int(max_id) + 1
    row = [next_id, int(student_id), int(book_id), borrow_date, due_date, ""]
    ws_tx.append_row(row, value_input_option="USER_ENTERED")
    return next_id

def update_book_available(book_id, delta):
    df_books, ws_books = read_sheet(BOOKS_SHEET)
    # find row index (1-based including header)
    match = df_books[df_books["id"] == int(book_id)]
    if match.empty:
        st.error("Book id not found")
        return False
    idx = match.index[0] + 2  # +2 for header and 0-index
    # find column number for available_copies
    headers = ws_books.row_values(1)
    try:
        col_idx = headers.index("available_copies") + 1
    except ValueError:
        st.error("Column 'available_copies' not found in Books sheet")
        return False
    current = int(match.iloc[0]["available_copies"])
    new_val = current + int(delta)
    if new_val < 0:
        st.error("Not enough copies available")
        return False
    ws_books.update_cell(idx, col_idx, new_val)
    return True

def update_transaction_return(tx_id, return_date):
    df_tx, ws_tx = read_sheet(TX_SHEET)
    match = df_tx[df_tx["id"] == int(tx_id)]
    if match.empty:
        st.error("Transaction not found")
        return False
    idx = match.index[0] + 2
    headers = ws_tx.row_values(1)
    try:
        col_idx = headers.index("return_date") + 1
    except ValueError:
        st.error("Column 'return_date' not found in Transactions sheet")
        return False
    ws_tx.update_cell(idx, col_idx, return_date)
    return True

# ---------- UI: Issue Book with dynamic search ----------
st.header("Issue a Book (type to search)")

# Book search
book_query = st.text_input("Book: Start typing title (min 1 char)", key="book_query")
books_df, _ = read_sheet(BOOKS_SHEET)
books_df["title_lower"] = books_df["title"].astype(str).str.lower()
book_matches = pd.DataFrame()
selected_book_id = None
selected_book_title = None
if book_query and len(book_query.strip()) >= 1:
    q = book_query.strip().lower()
    book_matches = books_df[books_df["title_lower"].str.contains(q, na=False)]
    # only available copies
    book_matches = book_matches[book_matches["available_copies"].astype(int) > 0]
    if not book_matches.empty:
        selected_book = st.selectbox("Select matching book", book_matches["title"].tolist(), key="book_select")
        if selected_book:
            selected_book_row = book_matches[book_matches["title"] == selected_book].iloc[0]
            selected_book_id = int(selected_book_row["id"])
            selected_book_title = selected_book_row["title"]

# Student search
student_query = st.text_input("Student: Start typing name (min 1 char)", key="student_query")
students_df, _ = read_sheet(STUDENTS_SHEET)
students_df["name_lower"] = students_df["name"].astype(str).str.lower()
student_matches = pd.DataFrame()
selected_student_id = None
selected_student_name = None
if student_query and len(student_query.strip()) >= 1:
    sq = student_query.strip().lower()
    student_matches = students_df[students_df["name_lower"].str.contains(sq, na=False)]
    if not student_matches.empty:
        selected_student = st.selectbox("Select matching student", student_matches["name"].tolist(), key="student_select")
        if selected_student:
            selected_student_row = student_matches[student_matches["name"] == selected_student].iloc[0]
            selected_student_id = int(selected_student_row["id"])
            selected_student_name = selected_student_row["name"]

# Lend action
if st.button("📖 Lend Book"):
    if not selected_book_id or not selected_student_id:
        st.error("Please select both a book and a student from the suggestions.")
    else:
        borrow_date = datetime.now().strftime("%Y-%m-%d")
        due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        # append transaction and update book count
        append_transaction(selected_student_id, selected_book_id, borrow_date, due_date)
        ok = update_book_available(selected_book_id, -1)
        if ok:
            st.success(f"Lent '{selected_book_title}' to {selected_student_name} — due {due_date}")
        # clear cached sheet reads
        open_sheet.clear()
        st.experimental_rerun()

st.markdown("---")
# ---------- UI: Transaction Log with inline Return ----------
st.header("Transaction Log (latest first)")

tx_df, tx_ws = read_sheet(TX_SHEET)
# Ensure correct dtypes
if not tx_df.empty:
    tx_df["id"] = pd.to_numeric(tx_df["id"], errors="coerce").astype('Int64')
    tx_df["book_id"] = pd.to_numeric(tx_df["book_id"], errors="coerce").astype('Int64')
    tx_df["student_id"] = pd.to_numeric(tx_df["student_id"], errors="coerce").astype('Int64')
    # Join to display names
    books_df, _ = read_sheet(BOOKS_SHEET)
    students_df, _ = read_sheet(STUDENTS_SHEET)
    merged = tx_df.merge(books_df[["id","title"]].rename(columns={"id":"book_id","title":"book_title"}), on="book_id", how="left")
    merged = merged.merge(students_df[["id","name"]].rename(columns={"id":"student_id","name":"student_name"}), on="student_id", how="left")
    merged = merged.sort_values("borrow_date", ascending=False).reset_index(drop=True)
    # Display with return buttons
    for _, row in merged.iterrows():
        cols = st.columns([8,2])
        with cols[0]:
            st.write(f"📗 **{row['book_title']}** → **{row['student_name']}** | Borrowed: {row['borrow_date']} | Due: {row['due_date']} | Returned: {row['return_date'] or '❌'}")
        with cols[1]:
            if pd.isna(row["return_date"]) or row["return_date"] == "":
                if st.button("Return", key=f"ret_{int(row['id'])}"):
                    # Confirm via a simple yes/no dialog (Streamlit doesn't have native modal; emulate)
                    if st.confirm(f"Mark transaction {int(row['id'])} as returned?"):
                        ok = update_transaction_return(int(row['id']), datetime.now().strftime("%Y-%m-%d"))
                        if ok:
                            # increase book count
                            update_book_available(int(row['book_id']), 1)
                            open_sheet.clear()
                            st.success("Return recorded.")
                            st.experimental_rerun()
else:
    st.info("No transactions yet.")

st.markdown("---")
# Quick debug / admin view (collapsible)
with st.expander("Admin: Raw Sheets (for debugging)"):
    st.subheader("Books")
    bdf, _ = read_sheet(BOOKS_SHEET)
    st.dataframe(bdf)
    st.subheader("Students")
    sdf, _ = read_sheet(STUDENTS_SHEET)
    st.dataframe(sdf)
    st.subheader("Transactions")
    tdf, _ = read_sheet(TX_SHEET)
    st.dataframe(tdf)
