"""
ML analyzer — Isolation Forest + YAMNet.
Loaded once at service startup, reused for every request.
"""
import csv
import io
import json
import logging
import os
import urllib.request

import joblib
import librosa
import numpy as np

log = logging.getLogger("ml_service")

# ── Параметры ─────────────────────────────────────────────
MODELS_DIR  = os.path.join(os.path.dirname(__file__), "ml_models")
SR_MFCC     = 22050
SR_YAMNET   = 16000
DURATION    = 5
N_MFCC      = 40

# Группы YAMNet → AudioClass (из Django models.py)
YAMNET_GROUP_TO_CLASS = {
    "стук / удар":       "knock",
    "скрип":             "squeak",
    "свист":             "whistle",
    "речь / голос":      "speech",
    "вибрация / трение": "grinding",
    "шум":               "noise",
    # "двигатель / механизм" → контекст нормы, не аномальный класс
}

RELEVANT_GROUPS = {
    "речь / голос": [
        "Speech", "Conversation", "Narration", "Male speech",
        "Female speech", "Child speech", "Shout", "Whispering",
    ],
    "стук / удар": [
        "Knock", "Tap", "Bang", "Thump", "Thud", "Slam",
        "Clunk", "Clank", "Impact", "Beat", "Pound",
    ],
    "скрип": ["Squeak", "Creak", "Screech", "Squeal"],
    "свист": ["Whistle", "Hiss", "Steam", "Whoosh", "Wind"],
    "металл": ["Metal", "Clang", "Ding", "Chink", "Tinkle", "Rattle"],
    "двигатель / механизм": [
        "Engine", "Motor", "Mechanical fan", "Pump",
        "Machine", "Gear", "Drill", "Groan",
    ],
    "шум": ["Noise", "White noise", "Pink noise", "Static", "Crackle", "Hum", "Buzz", "Rumble"],
    "вибрация / трение": ["Vibration", "Friction", "Grinding", "Scratch", "Scrape"],
}

YAMNET_CLASS_MAP_URL = (
    "https://raw.githubusercontent.com/tensorflow/models/"
    "master/research/audioset/yamnet/yamnet_class_map.csv"
)


class Analyzer:
    """Loads models once and exposes analyze()."""

    def __init__(self):
        self.anomaly_model = None
        self.scaler        = None
        self.stats         = None
        self.yamnet        = None
        self.class_names   = None
        self.group_indices = None
        self.ready         = False

    # ── Загрузка ──────────────────────────────────────────

    def load(self):
        log.info("Loading Isolation Forest...")
        self.anomaly_model = joblib.load(os.path.join(MODELS_DIR, "anomaly_model.pkl"))
        self.scaler        = joblib.load(os.path.join(MODELS_DIR, "anomaly_scaler.pkl"))
        with open(os.path.join(MODELS_DIR, "anomaly_stats.json"), encoding="utf-8") as f:
            self.stats = json.load(f)
        log.info("Isolation Forest loaded. Threshold=%.4f", self.stats["threshold"])

        log.info("Loading YAMNet from TF Hub...")
        import tensorflow_hub as hub
        import os as _os
        _os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
        _os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
        self.yamnet      = hub.load("https://tfhub.dev/google/yamnet/1")
        self.class_names = self._load_class_names()
        self.group_indices = self._build_group_indices()
        log.info("YAMNet loaded. Classes=%d", len(self.class_names))

        self.ready = True
        log.info("Analyzer ready.")

    def _load_class_names(self):
        try:
            with urllib.request.urlopen(YAMNET_CLASS_MAP_URL, timeout=10) as r:
                content = r.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            return [row["display_name"] for row in reader]
        except Exception as e:
            log.warning("Could not download YAMNet class map: %s. Using indices.", e)
            return [f"class_{i}" for i in range(521)]

    def _build_group_indices(self):
        result = {}
        for group, keywords in RELEVANT_GROUPS.items():
            result[group] = [
                i for i, name in enumerate(self.class_names)
                if any(kw.lower() in name.lower() for kw in keywords)
            ]
        return result

    # ── Признаки (Isolation Forest) ───────────────────────

    @staticmethod
    def _extract_mfcc_features(path: str) -> np.ndarray:
        y, sr = librosa.load(path, sr=SR_MFCC, duration=DURATION)
        target = SR_MFCC * DURATION
        if len(y) < target:
            y = np.pad(y, (0, target - len(y)))
        else:
            y = y[:target]

        mfcc     = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
        chroma   = librosa.feature.chroma_stft(y=y, sr=sr)
        spec_con = librosa.feature.spectral_contrast(y=y, sr=sr)
        mel      = librosa.feature.melspectrogram(y=y, sr=sr)
        zcr      = librosa.feature.zero_crossing_rate(y)
        rms      = librosa.feature.rms(y=y)

        return np.concatenate([
            np.mean(mfcc, axis=1), np.std(mfcc, axis=1),
            np.percentile(mfcc, 25, axis=1), np.percentile(mfcc, 75, axis=1),
            np.mean(chroma, axis=1),
            np.mean(spec_con, axis=1),
            np.mean(mel, axis=1)[:20],
            [np.mean(zcr), np.std(zcr)],
            [np.mean(rms), np.std(rms)],
        ]).reshape(1, -1)

    def _score_to_pct(self, score: float) -> int:
        mean = self.stats["score_mean"]
        thr  = self.stats["threshold"]
        std  = self.stats["score_std"]
        if score >= mean:
            return 0
        elif score >= thr:
            return round((mean - score) / (mean - thr) * 50)
        else:
            margin = thr - score
            scale  = abs(thr - (mean - 3 * std))
            return round(50 + min(50, margin / max(scale, 0.01) * 50))

    def _run_isolation_forest(self, path: str) -> dict:
        feat   = self._extract_mfcc_features(path)
        scaled = self.scaler.transform(feat)
        pred   = self.anomaly_model.predict(scaled)[0]
        score  = float(self.anomaly_model.score_samples(scaled)[0])
        return {
            "is_anomaly":  pred == -1,
            "anomaly_pct": self._score_to_pct(score),
            "raw_score":   round(score, 4),
            "threshold":   round(self.stats["threshold"], 4),
        }

    # ── YAMNet ────────────────────────────────────────────

    def _run_yamnet(self, path: str) -> dict:
        import tensorflow as tf
        y, _ = librosa.load(path, sr=SR_YAMNET, mono=True)
        waveform    = tf.constant(y, dtype=tf.float32)
        scores, _, _ = self.yamnet(waveform)
        mean_scores  = scores.numpy().mean(axis=0)

        top5 = [
            (self.class_names[i], round(float(mean_scores[i]), 4))
            for i in np.argsort(mean_scores)[::-1][:5]
        ]
        groups = {
            group: round(float(mean_scores[indices].max()), 4)
            for group, indices in self.group_indices.items()
            if indices
        }
        return {"top5": top5, "groups": groups}

    # ── Объединение в AudioClass scores ───────────────────

    @staticmethod
    def _compute_class_scores(anomaly_pct: int, yamnet_groups: dict) -> dict:
        """
        Combines anomaly detection + YAMNet into normalized class scores (0-1).

        Logic:
        - normal  = 1 - anomaly_factor
        - each anomaly class = (relative_yamnet_weight) * anomaly_factor
        """
        factor = anomaly_pct / 100  # 0.0 — 1.0

        yamnet_anomaly = {
            audio_cls: yamnet_groups.get(group, 0.0)
            for group, audio_cls in YAMNET_GROUP_TO_CLASS.items()
        }
        max_yamnet = max(yamnet_anomaly.values()) or 1.0

        scores = {"normal": round(max(0.0, 1.0 - factor), 4)}
        for cls, ys in yamnet_anomaly.items():
            relative       = ys / max_yamnet          # 0-1, relative dominance
            scores[cls]    = round(min(1.0, relative * factor), 4)

        scores["foreign_sounds"] = 0.0
        scores["other_anomaly"]  = 0.0
        return scores

    # ── Публичный метод ───────────────────────────────────

    def analyze(self, file_path: str) -> dict:
        if not self.ready:
            raise RuntimeError("Analyzer not loaded")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        log.info("Analyzing: %s", file_path)
        iso   = self._run_isolation_forest(file_path)
        yamnet = self._run_yamnet(file_path)
        scores = self._compute_class_scores(iso["anomaly_pct"], yamnet["groups"])

        return {
            "is_anomaly":   iso["is_anomaly"],
            "anomaly_pct":  iso["anomaly_pct"],
            "raw_score":    iso["raw_score"],
            "class_scores": scores,
            "yamnet_groups": yamnet["groups"],
            "yamnet_top5":  yamnet["top5"],
        }
