# Threat Intelligence Dashboard

A full-stack cybersecurity analysis platform that combines a modern web UI, a RESTful API, a relational database, and a local offline LLM to triage and classify security logs in real time.

## Architecture Overview

```
┌─────────────────────┐      HTTP / JSON       ┌──────────────────────┐
│   Browser (UI)      │ ◄──────────────────────► │   FastAPI Server     │
│   static/index.html │                          │   main.py            │
│   Tailwind CSS      │                          │                      │
└─────────────────────┘                          │  POST /api/analyze   │
                                                 │  GET  /api/reports   │
                                                 └──────┬───────┬───────┘
                                                        │       │
                                          ┌─────────────┘       └──────────────┐
                                          ▼                                     ▼
                              ┌────────────────────┐             ┌──────────────────────┐
                              │  SQLite (via       │             │  Ollama (local)      │
                              │  SQLAlchemy ORM)   │             │  qwen2.5:3b model    │
                              │  threat_intel.db   │             │  localhost:11434      │
                              └────────────────────┘             └──────────────────────┘
```

### 1. Frontend — `static/index.html`

A single-page dark-mode dashboard built with **Tailwind CSS** (CDN). It provides:

- A **submission form** where analysts paste raw security logs.
- A live **reports table** that displays every threat report, color-coded by severity:
  - **Critical** — red
  - **High** — orange
  - **Medium** — yellow
  - **Low** — green
- Real-time stats cards showing totals per severity level.
- Auto-refresh on new submission; manual refresh button available.

### 2. Backend API — `main.py`

Built on **FastAPI** with two primary endpoints:

| Endpoint           | Method | Purpose                                                  |
|--------------------|--------|----------------------------------------------------------|
| `/api/analyze`     | POST   | Accepts `{ "raw_log": "..." }`, calls Ollama, persists result |
| `/api/reports`     | GET    | Returns all reports ordered newest-first                 |

**Analysis pipeline:**
1. Receive raw log → 2. Send to Ollama with a structured prompt (ask for threat summary + severity) → 3. Parse the LLM response → 4. Persist to SQLite → 5. Return the saved record.

### 3. Database — SQLite + SQLAlchemy

The `ThreatReport` model stores:

| Column       | Type     | Description                              |
|--------------|----------|------------------------------------------|
| `id`         | INTEGER  | Auto-increment primary key               |
| `raw_log`    | VARCHAR  | The original security log submitted      |
| `severity`   | VARCHAR  | LLM-determined severity (Low-High-Critical) |
| `ai_analysis`| TEXT     | Natural-language threat summary          |
| `timestamp`  | DATETIME | UTC timestamp of analysis                |

### 4. AI Engine — Ollama (qwen2.5:3b)

All threat analysis runs **entirely offline** on a local Ollama instance. The model receives each log with a prompt instructing it to:
1. Summarize the threat in 2-4 sentences.
2. Output a severity level: Low, Medium, High, or Critical.

No data ever leaves the machine, preserving sensitive log confidentiality.

## Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- The `qwen2.5:3b` model pulled: `ollama pull qwen2.5:3b`

### Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Start the server
uvicorn main:app --reload

# 3. Open in browser
# http://localhost:8000
```

### Usage

1. Open `http://localhost:8000` in your browser.
2. Paste a security log into the text area (e.g., a firewall alert, IDS event, or suspicious-auth log).
3. Click **Analyze Threat**.
4. The AI analysis appears in the reports table, color-coded by severity.

## Security Considerations

- **Offline AI**: All LLM inference runs locally via Ollama — no log data is transmitted externally.
- **Local SQLite**: The database is a single file (`threat_intel.db`) on disk with no network exposure.
- **Zero-trust principle**: The system treats every submitted log as potentially malicious input and uses structured prompts to constrain the LLM's output format.

## Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Frontend   | HTML5, Tailwind CSS (CDN), vanilla JS |
| Backend    | Python 3, FastAPI, Uvicorn        |
| Database   | SQLite, SQLAlchemy ORM            |
| AI         | Ollama, qwen2.5:3b                |
