pip install -r requirements.txt
cp .env.example .env          # add your GEMINI_API_KEY
uvicorn app.main:app --reload

curl -s localhost:8000/extract -H 'content-type: application/json' \
  -d '{"text":"Reach Dr. Amina Rahman, CTO at Bengal Robotics, amina@bengalrobotics.bd"}'

  ### What I built
- /extract endpoint: raw text -> validated Contact (Pydantic) via Gemini
- Retry layer keyed on HTTP status codes, not SDK exception class names
- Two timeout layers: inner SDK (ms!) + outer asyncio.wait_for (seconds)
- Self-correcting validation retry (feed the error back, retry once)

### The three things that surprised me
1. (e.g. Gemini timeout is in MILLISECONDS, not seconds — easy to set 30ms by accident)
2. (e.g. Gemini has no RateLimitError class — you inspect .code instead)
3. (your own observation here)

### Real retry sequence I captured
(paste the uvicorn log lines from the 429 here)
