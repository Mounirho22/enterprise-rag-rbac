import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
DATABASE_URL = "sqlite:///threat_intel.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


class ThreatReport(Base):
    __tablename__ = "threat_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_log: Mapped[str] = mapped_column(String(4000), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="Low")
    ai_analysis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Threat Intelligence Dashboard",
    description="Full-stack cybersecurity dashboard powered by an offline LLM (Ollama).",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    raw_log: str


class ThreatReportOut(BaseModel):
    id: int
    raw_log: str
    severity: str
    ai_analysis: str
    timestamp: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Ollama caller helper
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"


def _call_ollama(raw_log: str) -> tuple[str, str]:
    """Call the local Ollama LLM to analyze a security log.

    Returns (severity, analysis_text).
    """
    prompt = f"""You are an expert cybersecurity analyst. Analyze the following security log.

Provide your response in exactly two sections separated by "---SEVERITY---":

1. A concise threat analysis (2-4 sentences describing what happened and the risk).
2. A single severity word: Low, Medium, High, or Critical.

Security log:
{raw_log}"""

    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama communication failed: {str(e)}",
        )

    # Parse the response
    if "---SEVERITY---" in text:
        parts = text.split("---SEVERITY---", 1)
        analysis = parts[0].strip()
        severity_raw = parts[1].strip().split("\n")[0].strip().title()
    else:
        # Fallback: use entire response as analysis, try to extract severity
        analysis = text
        severity_raw = text

    # Normalize severity — try exact match first, then regex scan
    valid_severities = {"Low", "Medium", "High", "Critical"}
    if severity_raw in valid_severities:
        severity = severity_raw
    else:
        match = re.search(r"\b(Critical|High|Medium|Low)\b", severity_raw, re.IGNORECASE)
        severity = match.group(1).title() if match else "Low"

    return severity, analysis


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/analyze", response_model=ThreatReportOut)
def analyze_log(body: AnalyzeRequest):
    """Analyze a raw security log via Ollama and persist the result."""
    if not body.raw_log.strip():
        raise HTTPException(status_code=400, detail="raw_log must not be empty")

    severity, analysis = _call_ollama(body.raw_log)

    report = ThreatReport(
        raw_log=body.raw_log.strip(),
        severity=severity,
        ai_analysis=analysis,
        timestamp=datetime.now(timezone.utc),
    )

    with Session(engine) as session:
        session.add(report)
        session.commit()
        session.refresh(report)
        result = ThreatReportOut.model_validate(report)

    return result


@app.get("/api/reports", response_model=list[ThreatReportOut])
def list_reports():
    """Return every threat report ordered newest-first."""
    with Session(engine) as session:
        reports = (
            session.query(ThreatReport)
            .order_by(ThreatReport.timestamp.desc())
            .all()
        )
        return [
            ThreatReportOut(
                id=r.id,
                raw_log=r.raw_log,
                severity=r.severity,
                ai_analysis=r.ai_analysis,
                timestamp=r.timestamp,
            )
            for r in reports
        ]


# ---------------------------------------------------------------------------
# Static frontend (must be last so API routes take priority)
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
