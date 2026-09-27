# فیت‌پیمان · FitPeyman

Pact for Iran: make a weekly health pact (gym ≥30 min, daily steps, 3 logged meals), put money on each missed day,
and split the pool with everyone who kept theirs (12% service fee; leftover goes to a health charity).

## Run

```bash
docker compose up -d --build
```

- App: http://localhost:3330 (fa/en toggle, light/dark toggle, fully responsive)
- API: http://localhost:8330/docs

## Dev

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
DB_PATH=pact.db .venv/bin/uvicorn main:app --port 8330 --reload
.venv/bin/python test_settle.py          # settlement math check

cd frontend && npm install && npm run dev  # http://localhost:3330, proxies /api to :8330
```

## Layout

- `backend/main.py`: FastAPI + SQLite (stdlib), seeded demo data, weekly settlement
- `frontend/`: Next.js 16 App Router, Tailwind 4, lucide icons, self-hosted Vazirmatn/Inter
  - `lib/i18n.tsx`: fa/en dictionary (Persian UX vocabulary), RTL/LTR, Persian calendar & digits via `Intl`
  - `components/ui.tsx`: rings, sheets (native `<dialog>`), hold-to-seal, count-up

## Demo shortcuts (replace before real money)

- Single demo user, no login (add phone + OTP).
- Check-ins are self-reported (add GPS/QR gym verification, step sync from wearables).
- "Close the week" button settles on demand (make it a Friday-night job).
