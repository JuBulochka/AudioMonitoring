"""FastAPI-сервис ML-анализа: health-check и анализ аудиофайла."""
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

analyzer: Analyzer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загружает ML-модели при старте приложения."""
    global analyzer
    log.info("=== ML Service starting — loading models ===")
    analyzer = Analyzer()
    try:
        analyzer.load()
        log.info("=== Models loaded successfully ===")
    except Exception as e:
        log.error("Failed to load models: %s", e)
    yield
    log.info("=== ML Service shutting down ===")


app = FastAPI(
    title="PumpJack ML Audio Analysis",
    version="1.0.0",
    lifespan=lifespan,
)



class AnalyzeRequest(BaseModel):
    file_path: str


class AnalyzeResponse(BaseModel):
    is_anomaly:    bool
    anomaly_pct:   int
    raw_score:     float
    class_scores:  dict[str, float]
    yamnet_groups: dict[str, float]
    yamnet_top5:   list[tuple[str, float]]



@app.get("/health")
def health():
    """Показывает, готов ли сервис принимать анализ аудио."""
    return {
        "status": "ok" if (analyzer and analyzer.ready) else "loading",
        "model_ready": analyzer.ready if analyzer else False,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """Запускает анализ файла и возвращает нормализованные оценки классов."""
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
