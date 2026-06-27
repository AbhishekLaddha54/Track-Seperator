# Track Separator MVP (Local-First)

A local-first desktop-like web app for singers and music creators.

## Stack
- React frontend (Vite)
- FastAPI backend
- Open-source local DSP libraries (`librosa`, `scipy`, `soundfile`)
- Local filesystem storage (no database)
- No paid APIs

## Modes
1. Quick Karaoke Mode
- Uses local center-channel reduction to create instrumental output
- UI shows only instrumental output (`accompaniment.wav`)

2. Studio Mode
- Uses local open-source DSP steps (HPSS + frequency filtering) for 4-stem output
- UI shows vocals, drums, bass, and other when 4-stem is selected

## Project Structure
- `backend/` FastAPI API and local separation runner
- `frontend/` React UI

## Prerequisites
- Python 3.10+
- Node.js 18+
- No cloud or paid API dependencies

## Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
## Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
