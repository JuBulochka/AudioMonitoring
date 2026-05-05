"""
ML Audio Analysis Microservice — FastAPI.

Endpoints:
  GET  /health       — liveness check
  POST /analyze      — analyze audio file, return class scores
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from analyzer import Analyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("ml_service")

# ── Глобальный экземпляр анализатора ──────────────────────
analyzer: Analyzer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML models before first request, clean up on shutdown."""
    global analyzer
    log.info("=== ML Service starting — loading models ===")
    analyzer = Analyzer()
    try:
        analyzer.load()
        log.info("=== Models loaded successfully ===")
    except Exception as e:
        log.error("Failed to load models: %s", e)
        # Service starts but /analyze will return 503
    yield
    log.info("=== ML Service shutting down ===")


app = FastAPI(
    title="PumpJack ML Audio Analysis",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Schemas ───────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    file_path: str          # absolute path inside container, e.g. /app/media/audio/...


class AnalyzeResponse(BaseModel):
    is_anomaly:    bool
    anomaly_pct:   int
    raw_score:     float
    class_scores:  dict[str, float]
    yamnet_groups: dict[str, float]
    yamnet_top5:   list[tuple[str, float]]


# ── Endpoints ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok" if (analyzer and analyzer.ready) else "loading",
        "model_ready": analyzer.ready if analyzer else False,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    if not analyzer or not analyzer.ready:
        raise HTTPException(status_code=503, detail="Models are still loading, try again shortly")

    try:
        result = analyzer.analyze(req.file_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("Analysis failed for %s", req.file_path)
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

    return result
