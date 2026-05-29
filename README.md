# 🎵 Agentic Text-to-SQL Data Analyst

> **Ask any business question in plain English. The agent writes SQL, runs it, and heals itself when it fails — automatically.**

Built with **Google Gemini 2.5 Flash · LangChain · Streamlit · SQLite (Chinook)**

---

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3%2B-1C3C3C?logo=chainlink&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Chinook-003B57?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📋 Table of Contents

- [About the Project](#-about-the-project)
- [How It Works](#-how-it-works)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Step-by-Step Setup](#-step-by-step-setup)
  - [Step 1 — Clone the Repository](#step-1--clone-the-repository)
  - [Step 2 — Create a Virtual Environment](#step-2--create-a-virtual-environment)
  - [Step 3 — Install Dependencies](#step-3--install-dependencies)
  - [Step 4 — Download the Chinook Database](#step-4--download-the-chinook-database)
  - [Step 5 — Get Your Gemini API Key](#step-5--get-your-gemini-api-key)
  - [Step 6 — Create the .env File](#step-6--create-the-env-file)
  - [Step 7 — Run the App](#step-7--run-the-app)
- [Database Schema](#-database-schema)
- [Sample Questions to Try](#-sample-questions-to-try)
- [Features](#-features)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🧠 About the Project

This project is a production-grade **Agentic AI application** that bridges the gap between natural language and structured data. A user types a business question — and the agent autonomously:

1. Reads the live database schema
2. Generates the correct SQL query
3. Executes it against a real SQLite database
4. **Self-corrects up to 3 times** if the query fails
5. Returns a clean, human-readable business insight

No SQL knowledge required. No hallucinated answers. Full transparency into every step via the **Agent's Internal Thoughts** log.

---

## ⚙️ How It Works

The agent runs a deterministic five-step pipeline on every question:

```
User Question
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  Step A  │  Schema Fetch       │  Reads live DB metadata │
│  Step B  │  SQL Generation     │  Gemini writes the SQL  │
│  Step C  │  Secure Execution   │  Runs query via SQLite  │
│  Step D  │  Self-Correction    │  Fixes errors (≤3 tries)│  ◄── The Core Innovation
│  Step E  │  Response Synthesis │  Formats business answer│
└─────────────────────────────────────────────────────────┘
      │
      ▼
DataFrame Results  +  Natural Language Summary
```

**The Self-Correction Gate (Step D):** If SQLite throws an error (bad column name, syntax mistake, wrong JOIN, etc.), the agent does **not** crash. Instead, it sends the broken SQL **plus** the raw database error back to Gemini, asking it to reason about the mistake and rewrite the query. This loop repeats up to **3 times** before gracefully surfacing a failure message.

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | [Streamlit](https://streamlit.io/) | Interactive web UI |
| **LLM** | [Google Gemini 2.5 Flash](https://aistudio.google.com/) | SQL generation & synthesis |
| **LLM Framework** | [LangChain](https://www.langchain.com/) | Message formatting & model interface |
| **Database** | [SQLite](https://www.sqlite.org/) + [Chinook](https://github.com/lerocha/chinook-database) | Real relational data store |
| **Data Display** | [Pandas](https://pandas.pydata.org/) | DataFrame rendering |
| **Config** | [python-dotenv](https://pypi.org/project/python-dotenv/) | Secure API key management |

---

## 📁 Project Structure

```
your-project/
│
├── app.py                     # Main application (all logic in one file)
├── .env                       # Your secret API key (never commit this)
├── Chinook_Sqlite.sqlite      # Chinook database file (download separately)
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

> ⚠️ **Important:** `Chinook_Sqlite.sqlite` and `.env` must be in the **same folder** as `app.py`.

---

## ✅ Prerequisites

Before you begin, make sure you have the following installed on your machine:

| Requirement | Minimum Version | Check Command |
|---|---|---|
| Python | 3.10 or higher | `python --version` |
| pip | Latest | `pip --version` |
| Git | Any | `git --version` |
| Internet connection | — | For Gemini API calls |

---

## 🚀 Step-by-Step Setup

Follow every step in order. Do not skip any step.

---

### Step 1 — Clone the Repository

Open your terminal and run:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

> Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub details.

---

### Step 2 — Create a Virtual Environment

It is strongly recommended to use a virtual environment to avoid dependency conflicts.

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

You should see `(venv)` appear at the start of your terminal prompt. This confirms the environment is active.

---

### Step 3 — Install Dependencies

With your virtual environment active, install all required packages:

```bash
pip install streamlit langchain-google-genai langchain-core python-dotenv pandas
```

Or, if a `requirements.txt` is present in the project:

```bash
pip install -r requirements.txt
```

**What gets installed:**

| Package | What it does |
|---|---|
| `streamlit` | Powers the web UI |
| `langchain-google-genai` | Connects LangChain to Gemini models |
| `langchain-core` | Message types (SystemMessage, HumanMessage) |
| `python-dotenv` | Loads your `.env` file into environment variables |
| `pandas` | Displays query results as a DataFrame table |

---

### Step 4 — Download the Chinook Database

This app uses the **Chinook** open-source database — a realistic music store dataset widely used for demos and interviews.

**Direct download link:**

👉 [Download Chinook_Sqlite.sqlite](https://github.com/lerocha/chinook-database/releases/download/ChinookVersion_1.4.5/Chinook_Sqlite.sqlite)

**After downloading:**

1. Locate the downloaded file (`Chinook_Sqlite.sqlite`)
2. Move or copy it into the **same folder as `app.py`**

Your folder should now look like this:

```
your-project/
├── app.py
├── Chinook_Sqlite.sqlite    ✅  ← placed here
└── README.md
```

> The filename must be exactly `Chinook_Sqlite.sqlite` (capital C, capital S — case-sensitive on Linux/macOS).

---

### Step 5 — Get Your Gemini API Key

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the key — it starts with `AIza...`

> **Free tier available.** Gemini 2.5 Flash has a generous free quota — no billing required for personal projects.

---

### Step 6 — Create the `.env` File

In the **same folder as `app.py`**, create a new file named exactly `.env` (note the leading dot):

**On macOS / Linux:**
```bash
touch .env
```

**On Windows (Command Prompt):**
```cmd
echo. > .env
```

Open the `.env` file in any text editor and add this single line:

```env
GOOGLE_API_KEY=AIzaSyYour_Actual_Key_Here
```

> Replace `AIzaSyYour_Actual_Key_Here` with the key you copied in Step 5.

**Final folder structure after all setup steps:**

```
your-project/
├── app.py                     ✅
├── .env                       ✅  ← contains GOOGLE_API_KEY=AIza...
├── Chinook_Sqlite.sqlite      ✅
└── README.md                  ✅
```

---

### Step 7 — Run the App

With the virtual environment still active, run:

```bash
streamlit run app.py
```

Streamlit will automatically open your browser at:

```
http://localhost:8501
```

If it does not open automatically, copy and paste that URL into your browser manually.

---

## 🗃️ Database Schema

The Chinook database represents a digital music store with 11 related tables:

```
Artist ──< Album ──< Track >── Genre
                       │
                       └──< InvoiceLine >── Invoice >── Customer
                       │
                       └──< PlaylistTrack >── Playlist

Employee (self-referencing: ReportsTo)
MediaType (referenced by Track)
```

| Table | Rows | Description |
|---|---|---|
| `Artist` | 275 | Music artists |
| `Album` | 347 | Albums linked to artists |
| `Track` | 3,503 | Songs with price, duration, genre |
| `Genre` | 25 | Music genres |
| `MediaType` | 5 | File format types |
| `Invoice` | 412 | Customer purchase headers |
| `InvoiceLine` | 2,240 | Individual line items per invoice |
| `Customer` | 59 | Customer details with country |
| `Employee` | 8 | Staff with reporting hierarchy |
| `Playlist` | 18 | Named playlists |
| `PlaylistTrack` | 8,715 | Playlist ↔ Track mappings |

**Total: ~15,600 rows across 11 tables**

---

## 💡 Sample Questions to Try

Copy any of these into the app to see the agent in action:

**Revenue & Sales**
- `Who are the top 10 customers by total purchase amount?`
- `What are the top 5 best-selling artists by total revenue?`
- `Show total revenue by country, sorted highest to lowest.`
- `Show monthly revenue totals for all time.`

**Music Catalogue**
- `Which music genre has the most tracks?`
- `Which album has the most tracks?`
- `What are the most expensive tracks available?`
- `What is the average track length in minutes per genre?`

**Customers & Employees**
- `Which country has the highest number of customers?`
- `List all employees and who they report to.`
- `Which employee is responsible for the most customers?`

---

## ✨ Features

- **Zero SQL knowledge required** — ask in plain English
- **Live schema introspection** — agent always knows the current table structure
- **Self-healing loop** — automatically retries and fixes broken SQL up to 3 times
- **Full thought transparency** — expandable "Agent's Internal Thoughts" log shows every step
- **Table explorer** — preview any table directly from the sidebar
- **CSV export** — download query results with one click
- **Secure key management** — API key loaded from `.env`, never hardcoded
- **Graceful error handling** — actionable messages when something goes wrong

---

## 🔧 Troubleshooting

**`Database file not found` error**
- Confirm `Chinook_Sqlite.sqlite` is in the same folder as `app.py`
- Check the filename spelling and capitalisation exactly: `Chinook_Sqlite.sqlite`

**`GOOGLE_API_KEY not found` warning**
- Confirm your `.env` file exists in the same folder as `app.py`
- Confirm the key name is exactly `GOOGLE_API_KEY` (no spaces, no quotes)
- Confirm the key value starts with `AIza`

**`ModuleNotFoundError` on startup**
- Confirm your virtual environment is activated (you should see `(venv)` in terminal)
- Re-run `pip install streamlit langchain-google-genai langchain-core python-dotenv pandas`

**`429 Resource Exhausted` from Gemini**
- You have hit the free-tier rate limit. Wait 60 seconds and try again.
- Consider upgrading to a paid Gemini plan for production use.

**Agent fails after 3 attempts**
- Try rephrasing your question more specifically
- Use the sidebar schema reference to check exact table and column names
- Break complex questions into simpler parts

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License.  
The Chinook database is licensed under its own open-source license — see the [Chinook repository](https://github.com/lerocha/chinook-database) for details.

---

<div align="center">
  <sub>Built with ❤️ using Google Gemini · LangChain · Streamlit · SQLite</sub>
</div>
