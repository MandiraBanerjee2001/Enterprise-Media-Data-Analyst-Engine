"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         AGENTIC TEXT-TO-SQL DATA ANALYST WITH SELF-CORRECTION LOOP          ║
║                                                                              ║
║  Stack  : Streamlit · SQLite (Chinook) · Google Gemini 2.5 Flash            ║
║           LangChain · python-dotenv                                          ║
║  Author : Senior AI Engineer                                                 ║
║                                                                              ║
║  SETUP  :                                                                    ║
║    1. pip install streamlit langchain-google-genai langchain-core            ║
║                  python-dotenv pandas                                        ║
║    2. Download Chinook database:                                             ║
║       https://github.com/lerocha/chinook-database/releases/download/        ║
║       ChinookVersion_1.4.5/Chinook_Sqlite.sqlite                            ║
║    3. Place Chinook_Sqlite.sqlite in the SAME folder as this app.py          ║
║    4. Create a .env file in the SAME folder:                                 ║
║         GOOGLE_API_KEY=your-gemini-api-key-here                             ║
║    5. streamlit run app.py                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

PROJECT FOLDER STRUCTURE (required)
─────────────────────────────────────
  your-project/
  ├── app.py                   ← this file
  ├── .env                     ← GOOGLE_API_KEY=AIza...
  └── Chinook_Sqlite.sqlite    ← downloaded Chinook database

CHINOOK DATABASE TABLES
────────────────────────
  Artist, Album, Track, Genre, MediaType,
  Invoice, InvoiceLine, Customer, Employee,
  Playlist, PlaylistTrack
"""

# ─────────────────────────────────────────────────────────────────────────────
# STANDARD LIBRARY
# ─────────────────────────────────────────────────────────────────────────────
import os
import re
import sqlite3
import textwrap

# ─────────────────────────────────────────────────────────────────────────────
# THIRD-PARTY  (pip install streamlit langchain-google-genai langchain-core
#               python-dotenv pandas)
# ─────────────────────────────────────────────────────────────────────────────
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS — edit DB_PATH here if you rename the database file
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH                = "Chinook_Sqlite.sqlite"   # must sit next to app.py
MAX_CORRECTION_ATTEMPTS = 3                         # self-repair retry ceiling
APP_TITLE              = "🎵 Chinook SQL Analyst"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 – DATABASE HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

def verify_database() -> tuple[bool, str]:
    """
    Confirm that Chinook_Sqlite.sqlite exists and is a readable SQLite file.

    Returns
    ───────
    (ok: bool, message: str)
      ok      – True if database is ready to use
      message – Human-readable status or error description
    """
    if not os.path.exists(DB_PATH):
        return False, (
            f"**Database file `{DB_PATH}` not found.**\n\n"
            "Please download it from:\n"
            "https://github.com/lerocha/chinook-database/releases/download/"
            "ChinookVersion_1.4.5/Chinook_Sqlite.sqlite\n\n"
            f"Then place it in the **same folder as `app.py`**."
        )
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        conn.close()
        return True, "ok"
    except sqlite3.DatabaseError as exc:
        return False, (
            f"File `{DB_PATH}` exists but cannot be read as a SQLite database.\n\n"
            f"Error: `{exc}`\n\n"
            "Re-download the file and try again."
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 – DATABASE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def get_schema() -> str:
    """
    Introspect the database and return a structured schema string covering
    every user table, its columns, data types, and foreign-key relationships.

    This string is injected verbatim into every LLM prompt so the model
    always knows exactly what tables and columns it can reference.

    Returns
    ───────
    str  Multi-line schema ready for inclusion in a prompt.
    """
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # ── Fetch all user-defined tables (skip sqlite_sequence etc.) ────────────
    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name;"
    )
    tables = [row[0] for row in cur.fetchall()]

    schema_parts = []
    for table in tables:
        # Column definitions
        cur.execute(f"PRAGMA table_info({table});")
        columns = cur.fetchall()
        # PRAGMA row: (cid, name, type, notnull, dflt_value, pk)
        col_defs = ", ".join(f"{col[1]} {col[2]}" for col in columns)

        # Foreign key relationships
        cur.execute(f"PRAGMA foreign_key_list({table});")
        fk_rows = cur.fetchall()
        # PRAGMA row: (id, seq, table, from, to, ...)
        fk_parts = [f"{fk[3]} → {fk[2]}.{fk[4]}" for fk in fk_rows]
        fk_str   = f"  [FK: {', '.join(fk_parts)}]" if fk_parts else ""

        schema_parts.append(f"  {table}({col_defs}){fk_str}")

    conn.close()

    return (
        "DATABASE: Chinook Music Store (SQLite)\n"
        "TABLES:\n" + "\n".join(schema_parts)
    )


def execute_sql(query: str) -> tuple[list[dict], list[str]]:
    """
    Run a SQL query against the Chinook database and return structured results.

    Design note: sqlite3.Error is intentionally NOT caught here.
    It propagates to the self-correction loop in run_agent(), which uses it
    to build the correction prompt for the LLM.

    Parameters
    ──────────
    query : str  Raw SQL string to execute (SELECT statements only).

    Returns
    ───────
    (rows, columns)
      rows    – list[dict]  one dict per result row, keyed by column name
      columns – list[str]   ordered column name list (mirrors dict keys)

    Raises
    ──────
    sqlite3.Error  Any DB-level error bubbles up to the caller on purpose.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # enables name-based column access
    cur  = conn.cursor()

    try:
        cur.execute(query)
        raw_rows = cur.fetchall()
        if not raw_rows:
            return [], []
        columns = list(raw_rows[0].keys())
        rows    = [dict(row) for row in raw_rows]
        return rows, columns
    finally:
        conn.close()    # always release, even if sqlite3.Error is raised


def get_table_preview(table: str, limit: int = 3) -> pd.DataFrame:
    """
    Return a small preview DataFrame for the given table name.
    Used in the sidebar's "Explore Tables" section.

    Parameters
    ──────────
    table : str   Exact table name as it appears in the schema.
    limit : int   Maximum number of rows to return (default 3).

    Returns
    ───────
    pd.DataFrame  Empty DataFrame on any error (safe for display).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        df   = pd.read_sql_query(
            f"SELECT * FROM {table} LIMIT {limit};", conn
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 – PROMPT TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def build_sql_generation_prompt(user_question: str, schema: str) -> list:
    """
    Construct the message list for the initial SQL generation call.

    System message rules enforce:
      • Return ONLY bare SQL — no markdown fences, no prose.
      • Reference only tables/columns present in the schema.
      • Use explicit table aliases to prevent column ambiguity.
      • SQLite dialect only (no ILIKE, no SERIAL, no NOW()).

    Parameters
    ──────────
    user_question : str  The user's natural-language business question.
    schema        : str  Full schema string from get_schema().

    Returns
    ───────
    list[BaseMessage]  Ready to pass directly to llm.invoke().
    """
    system = SystemMessage(content=textwrap.dedent(f"""
        You are an expert SQLite data analyst working with the Chinook music store database.

        DATABASE SCHEMA
        ───────────────
        {schema}

        STRICT RULES
        ────────────
        1. Output ONLY a valid SQLite SELECT statement — nothing else whatsoever.
        2. Do NOT wrap in markdown (no ```sql, no ```, no backticks of any kind).
        3. Do NOT add any explanation, preamble, or trailing commentary.
        4. Reference ONLY tables and columns that exist in the schema above.
        5. Always use table aliases (e.g. c.CustomerId) to avoid ambiguous columns.
        6. Use SQLite syntax only: strftime() for dates, || for string concat, etc.
        7. Limit result sets to 50 rows unless the question asks for all records.
        8. If the question is unanswerable with the available schema, output:
               SELECT 'CANNOT_ANSWER' AS message;
    """).strip())

    human = HumanMessage(content=f"Business question: {user_question}")
    return [system, human]


def build_correction_prompt(
    user_question: str,
    schema: str,
    bad_sql: str,
    error_message: str,
) -> list:
    """
    Construct the message list for the self-correction call.

    Passes the failing SQL and the raw database error back to the LLM so it
    can reason about the exact mistake and rewrite the query correctly.

    Parameters
    ──────────
    user_question : str  Original user question (for context).
    schema        : str  Full schema string from get_schema().
    bad_sql       : str  The SQL query that produced an error.
    error_message : str  The raw sqlite3.Error message string.

    Returns
    ───────
    list[BaseMessage]  Ready to pass directly to llm.invoke().
    """
    system = SystemMessage(content=textwrap.dedent(f"""
        You are an expert SQLite data analyst performing self-correction on a failed query.

        DATABASE SCHEMA
        ───────────────
        {schema}

        STRICT RULES
        ────────────
        1. Output ONLY a corrected, valid SQLite SELECT statement — nothing else.
        2. Do NOT wrap in markdown or add any explanation.
        3. Reference ONLY tables and columns that exist in the schema above.
        4. Carefully study the error message and fix the EXACT problem it describes.
        5. Use table aliases to prevent column ambiguity.
    """).strip())

    human = HumanMessage(content=textwrap.dedent(f"""
        The SQL query below failed with a database error.
        Analyse the error, identify the root cause, and output a corrected SQL query.

        ── ORIGINAL QUESTION ──────────────────────────────────────────
        {user_question}

        ── FAILED SQL ─────────────────────────────────────────────────
        {bad_sql}

        ── DATABASE ERROR ─────────────────────────────────────────────
        {error_message}
    """).strip())

    return [system, human]


def build_synthesis_prompt(
    user_question: str,
    columns: list[str],
    rows: list[dict],
) -> list:
    """
    Construct the message list for the final natural-language answer synthesis.

    Formats raw query results as a plain-text table and asks the LLM to write
    a clear, executive-level business summary without mentioning SQL.

    Parameters
    ──────────
    user_question : str        Original user question.
    columns       : list[str]  Column names from the query result.
    rows          : list[dict] Result rows as dicts.

    Returns
    ───────
    list[BaseMessage]  Ready to pass directly to llm.invoke().
    """
    # Format the raw results as a readable plain-text table for the prompt
    if rows:
        header     = " | ".join(columns)
        separator  = "-+-".join("-" * max(len(c), 6) for c in columns)
        data_lines = [
            " | ".join(str(row.get(c, "")) for c in columns)
            for row in rows
        ]
        table_str = "\n".join([header, separator] + data_lines)
    else:
        table_str = "(Query returned no rows)"

    system = SystemMessage(content=textwrap.dedent("""
        You are a senior business analyst presenting data insights to an executive audience.
        Write a concise, professional, and friendly natural-language summary of the results.
        - Use bullet points for lists of items or rankings.
        - Highlight the most interesting or actionable insight first.
        - Round monetary figures to 2 decimal places where appropriate.
        - Do NOT mention SQL, databases, tables, or technical implementation details.
        - Keep the tone confident and data-driven.
    """).strip())

    human = HumanMessage(content=textwrap.dedent(f"""
        ORIGINAL QUESTION:
        {user_question}

        QUERY RESULTS:
        {table_str}

        Please provide a clear, insightful business summary of these results.
    """).strip())

    return [system, human]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 – AGENTIC SELF-CORRECTION LOOP
# ══════════════════════════════════════════════════════════════════════════════

def extract_sql(llm_response: str) -> str:
    """
    Strip any accidental markdown fencing from the LLM output and return
    only the raw SQL string.

    The model is instructed to return bare SQL, but Gemini occasionally wraps
    output in ```sql fences.  This function acts as a safety net.

    Parameters
    ──────────
    llm_response : str  Raw string from llm.invoke().content

    Returns
    ───────
    str  Clean SQL string ready to pass to execute_sql().
    """
    # Remove ```sql ... ``` or ``` ... ``` blocks (case-insensitive)
    cleaned = re.sub(r"```(?:sql)?", "", llm_response, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    return cleaned


def run_agent(
    user_question: str,
    llm: ChatGoogleGenerativeAI,
    thought_log: list[str],
) -> tuple[list[dict], list[str], str]:
    """
    The core five-step agentic pipeline with a built-in self-correction gate.

    ┌─────────────────────────────────────────────────────────────┐
    │  A → Schema Fetch                                           │
    │  B → SQL Generation          (LLM call #1)                  │
    │  C → Secure SQL Execution    (try/except sqlite3.Error)     │
    │  D → Self-Correction Gate    (LLM call #2…N on failure)     │
    │       └─ loops back to C until success or MAX_ATTEMPTS      │
    │  E → Response Synthesis      (final LLM call)               │
    └─────────────────────────────────────────────────────────────┘

    Parameters
    ──────────
    user_question : str                    Natural-language business question.
    llm           : ChatGoogleGenerativeAI Configured Gemini model instance.
    thought_log   : list[str]              Mutable list; caller reads this for UI display.
                                           Append-only inside this function.

    Returns
    ───────
    (rows, columns, summary)
      rows    – list[dict]  raw query result rows
      columns – list[str]   column names
      summary – str         LLM-written business narrative

    Raises
    ──────
    RuntimeError  If all MAX_CORRECTION_ATTEMPTS are exhausted without success.
    """

    # ── STEP A: Schema Fetch ──────────────────────────────────────────────────
    thought_log.append("---")
    thought_log.append("### 📋 Step A — Fetching Database Schema")
    schema = get_schema()
    thought_log.append(f"```\n{schema}\n```")
    thought_log.append(
        f"✅ Schema loaded — "
        f"{len([l for l in schema.splitlines() if l.strip().startswith(tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))])} "
        f"tables discovered."
    )

    # ── STEP B: Initial SQL Generation ───────────────────────────────────────
    thought_log.append("---")
    thought_log.append("### 🧠 Step B — Generating SQL Query (Attempt 1)")
    messages  = build_sql_generation_prompt(user_question, schema)
    response  = llm.invoke(messages)
    sql_query = extract_sql(response.content)
    thought_log.append(f"**Generated SQL — Attempt 1:**\n```sql\n{sql_query}\n```")

    # ── STEPS C + D: Execute with Self-Correction Loop ────────────────────────
    rows:    list[dict] = []
    columns: list[str]  = []

    for attempt in range(1, MAX_CORRECTION_ATTEMPTS + 1):

        # ── STEP C: Secure Execution ──────────────────────────────────────────
        thought_log.append("---")
        thought_log.append(f"### ⚙️ Step C — Executing SQL (Attempt {attempt})")

        try:
            rows, columns = execute_sql(sql_query)

            # ── SUCCESS ───────────────────────────────────────────────────────
            thought_log.append(
                f"✅ **Execution successful** — **{len(rows)} row(s)** returned."
            )
            break   # Exit the retry loop — move on to Step E

        except sqlite3.Error as db_err:
            # ── STEP D: Self-Correction Gate ──────────────────────────────────
            error_msg = str(db_err)
            thought_log.append(
                f"❌ **Database error on Attempt {attempt}:**\n"
                f"```\n{error_msg}\n```"
            )

            # Check if we have any correction attempts remaining
            if attempt == MAX_CORRECTION_ATTEMPTS:
                thought_log.append(
                    f"🚨 **All {MAX_CORRECTION_ATTEMPTS} attempts exhausted. "
                    "Cannot recover from this error.**"
                )
                raise RuntimeError(
                    f"Agent failed after {MAX_CORRECTION_ATTEMPTS} self-correction "
                    f"attempts. Last database error: {error_msg}"
                ) from db_err

            # Still have retries — ask LLM to analyse error and rewrite query
            next_attempt = attempt + 1
            thought_log.append("---")
            thought_log.append(
                f"### 🔄 Step D — Self-Correction: Rewriting Query (Attempt {next_attempt})"
            )
            thought_log.append(
                "Sending the failed SQL + error message back to Gemini for analysis…"
            )

            correction_messages = build_correction_prompt(
                user_question, schema, sql_query, error_msg
            )
            correction_response = llm.invoke(correction_messages)
            sql_query = extract_sql(correction_response.content)

            thought_log.append(
                f"**Corrected SQL — Attempt {next_attempt}:**\n"
                f"```sql\n{sql_query}\n```"
            )

    # ── STEP E: Natural-Language Response Synthesis ───────────────────────────
    thought_log.append("---")
    thought_log.append("### ✨ Step E — Synthesising Business Answer")
    synthesis_messages = build_synthesis_prompt(user_question, columns, rows)
    synthesis_response = llm.invoke(synthesis_messages)
    summary = synthesis_response.content
    thought_log.append("✅ Business summary generated successfully.")

    return rows, columns, summary


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 – STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

def configure_page() -> None:
    """
    Apply global Streamlit page configuration and inject custom CSS.
    Must be the very first Streamlit call in the app lifecycle.
    """
    st.set_page_config(
        page_title="Chinook SQL Analyst",
        page_icon="🎵",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
        /* ── Google Font import ── */
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');

        /* ── Global body font ── */
        html, body, [class*="css"] {
            font-family: 'Syne', sans-serif;
        }

        /* ── Hero title gradient ── */
        .hero-title {
            font-size: 2.5rem;
            font-weight: 800;
            letter-spacing: -1.5px;
            background: linear-gradient(135deg, #f97316 0%, #ec4899 50%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.2rem;
            line-height: 1.15;
        }
        .hero-sub {
            font-size: 1rem;
            color: #94a3b8;
            margin-bottom: 1.5rem;
        }

        /* ── Stat / badge pill ── */
        .badge {
            display: inline-block;
            background: rgba(249,115,22,0.12);
            color: #f97316;
            border: 1px solid rgba(249,115,22,0.3);
            border-radius: 999px;
            padding: 3px 14px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.3px;
            margin-right: 6px;
        }
        .badge-purple {
            background: rgba(139,92,246,0.12);
            color: #8b5cf6;
            border-color: rgba(139,92,246,0.3);
        }
        .badge-pink {
            background: rgba(236,72,153,0.12);
            color: #ec4899;
            border-color: rgba(236,72,153,0.3);
        }

        /* ── Summary insight card ── */
        .summary-card {
            background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%);
            border: 1px solid rgba(139,92,246,0.3);
            border-radius: 14px;
            padding: 1.5rem 1.8rem;
            color: #e0e7ff;
            font-size: 0.96rem;
            line-height: 1.75;
            margin-top: 0.5rem;
        }

        /* ── Sidebar dark theme ── */
        [data-testid="stSidebar"] {
            background: #0f0f1a;
            border-right: 1px solid #1e1e2e;
        }
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #f97316;
        }

        /* ── Thought log expander inner content ── */
        .thought-header {
            font-size: 0.78rem;
            font-family: 'DM Mono', monospace;
            color: #94a3b8;
        }

        /* ── Divider ── */
        hr {
            border-color: #1e1e2e !important;
            margin: 1.2rem 0 !important;
        }

        /* ── Dataframe header accent ── */
        [data-testid="stDataFrame"] thead tr th {
            background-color: #1e1b4b !important;
            color: #c4b5fd !important;
            font-family: 'DM Mono', monospace !important;
            font-size: 0.82rem !important;
        }

        /* ── Button accent ── */
        [data-testid="stButton"] > button[kind="primary"] {
            background: linear-gradient(135deg, #f97316, #ec4899);
            border: none;
            font-weight: 700;
            letter-spacing: 0.3px;
            padding: 0.5rem 1.8rem;
        }
        [data-testid="stButton"] > button[kind="primary"]:hover {
            opacity: 0.88;
            transform: translateY(-1px);
        }

        /* ── Sidebar sample question buttons ── */
        [data-testid="stSidebar"] [data-testid="stButton"] > button {
            background: #1a1a2e;
            border: 1px solid #2d2d44;
            color: #cbd5e1;
            font-size: 0.82rem;
            text-align: left;
            border-radius: 8px;
            transition: all 0.15s ease;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
            border-color: #f97316;
            color: #f97316;
            background: rgba(249,115,22,0.06);
        }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar() -> str | None:
    """
    Render the left sidebar containing:
      - Google API key input (with .env auto-detection)
      - Database status indicator
      - Chinook schema reference
      - Sample question shortcuts
      - Table preview explorer

    Returns
    ───────
    str | None  The Gemini API key, or None if not yet provided.
    """
    with st.sidebar:
        st.markdown("## 🔐 API Configuration")
        st.markdown("---")

        # ── Load from .env first (silent, highest priority) ──────────────────
        load_dotenv()
        env_key = os.getenv("GOOGLE_API_KEY", "").strip()

        if env_key:
            st.success("✅ `GOOGLE_API_KEY` loaded from `.env`")
            api_key = env_key
        else:
            # Manual entry fallback if .env is missing or empty
            st.markdown(
                "No `.env` file detected. Enter your "
                "**Google Gemini API key** below:"
            )
            api_key = st.text_input(
                "Gemini API Key",
                type="password",
                placeholder="AIza...",
                help=(
                    "Get your key at https://aistudio.google.com/app/apikey  "
                    "Your key is never stored — session only."
                ),
            )
            if api_key:
                st.success("✅ API key accepted for this session.")
            else:
                st.warning("⚠️ Please provide your API key to continue.")

        # ── Database Status ───────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🗄️ Database Status")
        db_ok, db_msg = verify_database()
        if db_ok:
            file_size_kb = round(os.path.getsize(DB_PATH) / 1024, 1)
            st.success(f"✅ `{DB_PATH}` ready ({file_size_kb} KB)")
        else:
            st.error(db_msg)

        # ── Chinook Schema Quick Reference ────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📐 Chinook Schema")
        st.markdown("""
| Table | Key Columns |
|---|---|
| `Artist` | ArtistId, Name |
| `Album` | AlbumId, Title, ArtistId |
| `Track` | TrackId, Name, AlbumId, UnitPrice, Milliseconds |
| `Genre` | GenreId, Name |
| `Invoice` | InvoiceId, CustomerId, Total |
| `InvoiceLine` | InvoiceId, TrackId, UnitPrice, Quantity |
| `Customer` | CustomerId, FirstName, LastName, Country |
| `Employee` | EmployeeId, FirstName, LastName, Title, ReportsTo |
| `Playlist` | PlaylistId, Name |
| `PlaylistTrack` | PlaylistId, TrackId |
| `MediaType` | MediaTypeId, Name |
        """)

        # ── Sample Question Shortcuts ─────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 💡 Sample Questions")
        st.markdown(
            "<span style='font-size:0.78rem;color:#64748b'>"
            "Click any question to auto-fill the input field.</span>",
            unsafe_allow_html=True,
        )
        samples = [
            "Who are the top 10 customers by total purchase amount?",
            "Which music genre has the most tracks?",
            "What are the top 5 best-selling artists by total revenue?",
            "List all employees and who they report to.",
            "Which country has the highest number of customers?",
            "What is the average track length in minutes per genre?",
            "Show total revenue by country, sorted highest to lowest.",
            "Which album has the most tracks?",
            "What are the most expensive tracks available?",
            "Show monthly revenue totals for all time.",
        ]
        for q in samples:
            # Using a short key to avoid Streamlit key conflicts
            btn_key = f"sample_{hash(q)}"
            if st.button(q, use_container_width=True, key=btn_key):
                st.session_state["prefill_question"] = q
                st.rerun()

        # ── Table Preview Explorer ────────────────────────────────────────────
        if db_ok:
            st.markdown("---")
            st.markdown("### 🔍 Table Preview")
            all_tables = [
                "Artist", "Album", "Track", "Genre", "MediaType",
                "Invoice", "InvoiceLine", "Customer", "Employee",
                "Playlist", "PlaylistTrack",
            ]
            selected_table = st.selectbox(
                "Peek at a table (first 3 rows):",
                options=all_tables,
                index=0,
            )
            preview_df = get_table_preview(selected_table, limit=3)
            if not preview_df.empty:
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

        return api_key if api_key else None


def render_main(api_key: str | None) -> None:
    """
    Render the main content area:
      - Hero header with badge row
      - Database readiness guard
      - Natural-language question input + Run button
      - Agent's Internal Thoughts expander (live log)
      - Query results DataFrame
      - Business insight summary card

    Parameters
    ──────────
    api_key : str | None  Gemini API key; None blocks execution with guidance.
    """

    # ── Hero Header ───────────────────────────────────────────────────────────
    st.markdown(
        '<p class="hero-title">🎵 Chinook SQL Analyst</p>'
        '<p class="hero-sub">'
        "Ask any business question in plain English — the agent writes, "
        "executes, and self-corrects SQL against the Chinook music store database."
        "</p>",
        unsafe_allow_html=True,
    )

    # Badge row
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(
        '<span class="badge">gemini-2.5-flash</span> LLM Engine',
        unsafe_allow_html=True,
    )
    col2.markdown(
        '<span class="badge badge-pink">Chinook SQLite</span> 11 Tables · 77k+ rows',
        unsafe_allow_html=True,
    )
    col3.markdown(
        '<span class="badge badge-purple">Self-Healing</span> Up to 3 retries',
        unsafe_allow_html=True,
    )
    col4.markdown(
        '<span class="badge">LangChain</span> Agentic Loop',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Database Readiness Guard ──────────────────────────────────────────────
    db_ok, db_msg = verify_database()
    if not db_ok:
        st.error(
            "### ⛔ Database Not Found\n\n" + db_msg
        )
        st.info(
            "**Quick Fix:**\n\n"
            "1. Download `Chinook_Sqlite.sqlite` from the link above.\n"
            "2. Place the file in the **same folder as `app.py`**.\n"
            "3. Refresh this page."
        )
        return

    # ── Pre-fill from sidebar shortcut ───────────────────────────────────────
    default_q = st.session_state.pop("prefill_question", "")

    # ── Question Input ────────────────────────────────────────────────────────
    user_question = st.text_input(
        "💬 Ask a business question about the Chinook music store",
        value=default_q,
        placeholder="e.g.  Who are the top 10 customers by total purchase amount?",
    )

    run_btn = st.button("🚀 Run Agent", type="primary")

    # Early exit if button not clicked or no question
    if not run_btn:
        return
    if not user_question.strip():
        st.warning("⚠️ Please type a question before running the agent.")
        return
    if not api_key:
        st.error(
            "❌ No API key found. Please provide your `GOOGLE_API_KEY` "
            "in the `.env` file or in the sidebar input."
        )
        return

    # ── Execute the Agentic Pipeline ──────────────────────────────────────────
    thought_log: list[str] = []
    rows:    list[dict] = []
    columns: list[str]  = []
    summary: str        = ""
    success: bool       = False
    error_detail: str   = ""

    with st.spinner("🤖 Agent is analysing your question…"):
        try:
            # Initialise Gemini 2.5 Flash via LangChain
            # temperature=0 → deterministic, consistent SQL generation
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0,
                google_api_key=api_key,
            )

            rows, columns, summary = run_agent(
                user_question=user_question.strip(),
                llm=llm,
                thought_log=thought_log,
            )
            success = True

        except RuntimeError as exc:
            # Self-correction loop exhausted all retries
            error_detail = str(exc)
        except Exception as exc:
            # Any other unexpected error (network, auth, etc.)
            error_detail = str(exc)

    # ── Agent's Internal Thoughts ─────────────────────────────────────────────
    # Always rendered — even on failure — so the user can see what went wrong
    with st.expander("🧠 Agent's Internal Thoughts", expanded=True):
        if thought_log:
            for thought in thought_log:
                st.markdown(thought)
        else:
            st.markdown("*(No thoughts recorded yet)*")

    st.markdown("---")

    # ── Error Display ─────────────────────────────────────────────────────────
    if not success:
        st.error(
            "### ⚠️ Agent Encountered an Unrecoverable Error\n\n"
            f"```\n{error_detail}\n```\n\n"
            "**Suggestions:**\n"
            "- Try rephrasing your question.\n"
            "- Use the sidebar schema reference to check available tables/columns.\n"
            "- Simplify the question and build up complexity gradually."
        )
        return

    # ── Results: DataFrame ────────────────────────────────────────────────────
    st.markdown("### 📊 Query Results")

    if rows:
        df = pd.DataFrame(rows, columns=columns)

        # Show the dataframe with nice formatting
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=min(400, (len(df) + 1) * 35 + 10),  # auto-size up to 400px
        )

        # Metrics row: rows returned + columns
        m1, m2, m3 = st.columns(3)
        m1.metric("Rows Returned", len(rows))
        m2.metric("Columns", len(columns))
        m3.metric("Table Width", f"{len(columns)} fields")

    else:
        st.info(
            "ℹ️ The query executed successfully but returned **no rows**.\n\n"
            "This may mean no data matches your filter criteria."
        )

    # ── Business Insight Summary Card ─────────────────────────────────────────
    st.markdown("### 💼 Business Insight")
    st.markdown(
        f'<div class="summary-card">{summary}</div>',
        unsafe_allow_html=True,
    )

    # ── Optional: Download Results as CSV ─────────────────────────────────────
    if rows:
        st.markdown("---")
        csv_data = pd.DataFrame(rows, columns=columns).to_csv(index=False)
        st.download_button(
            label="⬇️ Download Results as CSV",
            data=csv_data,
            file_name="chinook_query_results.csv",
            mime="text/csv",
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 – APPLICATION ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Application entrypoint.  Called automatically by `streamlit run app.py`.

    Execution order
    ───────────────
    1. configure_page()  — set layout, inject CSS  (must be first Streamlit call)
    2. render_sidebar()  — API key, DB info, sample questions, table preview
    3. render_main()     — hero, question input, agentic pipeline, results
    """
    # ── Step 1: Page layout & CSS ─────────────────────────────────────────────
    configure_page()

    # ── Step 2: Sidebar (returns API key or None) ─────────────────────────────
    api_key = render_sidebar()

    # ── Step 3: Main content area ─────────────────────────────────────────────
    render_main(api_key)


if __name__ == "__main__":
    main()
