import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import librosa
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.background import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from scipy.signal import butter, sosfiltfilt

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = BASE_DIR / "work"
INPUTS_DIR = WORK_DIR / "inputs"
OUTPUTS_DIR = WORK_DIR / "outputs"

for directory in (WORK_DIR, INPUTS_DIR, OUTPUTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Local Stem Separator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
jobs: Dict[str, Dict] = {}

def _safe_name(filename: str) -> str:
    base = Path(filename).name
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in ("-", "_"))
    return cleaned or "audio.wav"

def _ensure_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    return audio

def _normalize(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0.999:
        audio = audio / peak * 0.999
    return audio.astype(np.float32)

def _lowpass(audio: np.ndarray, sr: int, cutoff_hz: float = 220.0) -> np.ndarray:
    nyquist = sr / 2.0
    normalized_cutoff = min(0.99, cutoff_hz / nyquist)
    sos = butter(4, normalized_cutoff, btype="lowpass", output="sos")
    return sosfiltfilt(sos, audio, axis=0)

def _highpass(audio: np.ndarray, sr: int, cutoff_hz: float = 150.0) -> np.ndarray:
    nyquist = sr / 2.0
    normalized_cutoff = min(0.99, cutoff_hz / nyquist)

def _write_stem(track_dir: Path, filename: str, audio: np.ndarray, sr: int) -> None:
    sf.write(track_dir / filename, _normalize(audio), sr)


def _run_local_separation(input_path: Path, mode: str, studio_four_stem: bool) -> None:
    track_dir = OUTPUTS_DIR / input_path.stem
    track_dir.mkdir(parents=True, exist_ok=True)

    
    try:
        audio_mono, sr= librosa.load(str(input_path), sr=None, mono=False)
    except Exception as e:
        raise RuntimeError(f"Failed to load audio file: {str(e)}")
    if audio_mono.ndim==1:
        audio=np.stack([audio_mono, audio_mono], axis=1)
    else:
        audio=audio_mono.T if audio_mono.shape[0]<=2 else audio_mono
    audio = _ensure_stereo(audio)

    mono=np.mean(audio, axis=1)

    # Quick karaoke approximation: remove center content where vocals often dominate
    harmonic, percussive=librosa.effects.hpss(mono)

    if mode == "quick":
        instrumental_mono=percussive *0.85+ harmonic*0.15
        instrumental= np.stack([instrumental_mono, instrumental_mono], axis=1)
        _write_stem(track_dir, "accompaniment.wav", instrumental, sr)
        return
    # Studio Mode
    percussive_stereo=np.stack([percussive, percussive], axis=1)
    harmonic_stereo= np.stack([harmonic, harmonic], axis=1)

    if not studio_four_stem:
        vocals=harmonic_stereo
        accompaniment= percussive_stereo* 0.9 + harmonic_stereo*0.1
        _write_stem(track_dir, "vocals.wav", vocals, sr)
        _write_stem(track_dir, "accompaniment.wav", accompaniment, sr)
        return

    
    bass = _lowpass(harmonic_stereo, sr, cutoff_hz=220.0)
    vocals = _highpass(harmonic_stereo, sr, cutoff_hz=150.0)
    drums=percussive_stereo

    other = audio - vocals- drums - bass 

    _write_stem(track_dir, "vocals.wav", vocals, sr)
    _write_stem(track_dir, "drums.wav", drums, sr)
    _write_stem(track_dir, "bass.wav", bass, sr)
    _write_stem(track_dir, "other.wav", other, sr)


def _collect_stems(job_id: str, mode: str, track_base_name: str, studio_four_stem: bool) -> List[Dict[str, str]]:
    track_dir = OUTPUTS_DIR / track_base_name
    if not track_dir.exists():
        raise RuntimeError(f"Output folder not found: {track_dir}")

    stems: List[Dict[str, str]] = []

    if mode == "quick":
        instrumental = track_dir / "accompaniment.wav"
        if not instrumental.exists():
            raise RuntimeError("Expected instrumental output accompaniment.wav was not created.")
        stems.append({"label": "Instrumental", "filename": instrumental.name})
        return stems

    if studio_four_stem:
        expected = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]
        for stem_name in expected:
            stem_path = track_dir / stem_name
            if stem_path.exists():
                stems.append({"label": stem_name.replace(".wav", "").title(), "filename": stem_name})
                if not stems:
                    raise RuntimeError("No 4-stem outputs found.")
        return stems

    for stem_name in ["vocals.wav", "accompaniment.wav"]:
        stem_path = track_dir / stem_name
        if stem_path.exists():
            label = "Vocals" if stem_name == "vocals.wav" else "Instrumental"
            stems.append({"label": label, "filename": stem_name})

    if not stems:
        raise RuntimeError("No stems were found in output.")
        
    return stems


def _run_job(job_id: str) -> None:
    job = jobs[job_id]
    input_path = Path(job["input_path"])
    mode = job["mode"]
    studio_four_stem = job["studio_four_stem"]

    try:
        jobs[job_id]["status"] = "processing"
        _run_local_separation(input_path, mode, studio_four_stem)
        jobs[job_id]["logs"] = "Local separation completed."
        jobs[job_id]["error_logs"] = ""

        track_base_name = input_path.stem
        stems = _collect_stems(job_id, mode, track_base_name, studio_four_stem)
        jobs[job_id]["stems"] = stems
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
    except Exception as exc:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(exc)
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/separate")
async def separate_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(...),
    studio_four_stem: bool = Form(True),
) -> Dict[str, str]:
    if mode not in {"quick", "studio"}:
        raise HTTPException(status_code=400, detail="mode must be 'quick' or 'studio'.")

    filename = _safe_name(file.filename or "audio.wav")
    job_id = str(uuid.uuid4())
    input_name = f"{job_id}_{filename}"
    input_path = INPUTS_DIR / input_name

    with input_path.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)
        jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "mode": mode,
        "studio_four_stem": studio_four_stem,
        "original_filename": filename,
        "input_path": str(input_path),
        "stems": [],
        "error": None,
        "logs": "",
        "error_logs": "",
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }

    background_tasks.add_task(_run_job, job_id)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> Dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    response = {
        "id": job["id"],
        "status": job["status"],
        "mode": job["mode"],
        "studio_four_stem": job["studio_four_stem"],
        "stems": [
            {
                "label": stem["label"],
                "filename": stem["filename"],
                "download_url": f"/api/jobs/{job_id}/files/{stem['filename']}",
            }
            for stem in job["stems"]
        ],
        "error": job["error"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
    }

    return response


@app.get("/api/jobs/{job_id}/files/{filename}")
def download_stem(job_id: str, filename: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    input_path = Path(job["input_path"])
    output_path = OUTPUTS_DIR / input_path.stem / Path(filename).name

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(path=output_path, filename=Path(filename).name, media_type="audio/wav")
