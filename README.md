# Armenian Bank Voice Assistant (ABVA) 

A voice assistant that answers questions about Armenian banks in Armenian. You talk to it through your browser — ask about loans, deposits, branches — and it talks back in Armenian.

Covers three banks: **Ardshinbank**, **Artsakhbank**, and **Mellat Bank**.

## How it works

```
You speak (Armenian) --> Browser --> LiveKit Server --> Voice Agent --> Gemini AI
                                                                         |
You hear (Armenian)  <-- Browser <-- LiveKit Server <-- Voice Agent <-----
```

The whole speech-to-text, thinking, and text-to-speech pipeline happens inside one Google Gemini model (`gemini-2.5-flash-native-audio`). No separate STT or TTS services needed.

## Quick start

You need 3 terminals running at the same time:

**Terminal 1** — LiveKit server:
```bash
./livekit-server --config config/livekit-server.yaml
```

**Terminal 2** — Voice agent:
```bash
cd src
python agent.py start
```

**Terminal 3** — Web server:
```bash
python src/token_server.py
```

Then open **http://localhost:8081** in Chrome, click Connect, and start talking in Armenian.

## Setup

### 1. Install Python packages

```bash
pip install -r requirements.txt
```

If you want to re-scrape bank data:
```bash
playwright install chromium
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env`:
```
GEMINI_API_KEY=your_key_here
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=your_secret_here
```

Get a Gemini API key at [Google AI Studio](https://aistudio.google.com/apikey).

### 3. Get LiveKit server

Download the binary for your OS from [LiveKit releases](https://github.com/livekit/livekit/releases) and put it in the project root.

## Project structure

```
├── src/
│   ├── agent.py              # Main voice agent
│   ├── token_server.py       # Serves frontend + auth tokens
│   ├── connect.py            # Alternative: generates token URL
│   ├── scrapers/             # Web scrapers for each bank
│   │   ├── common.py
│   │   ├── ardshinbank/
│   │   ├── artsakhbank/
│   │   └── mellatbank/
│   └── processing/           # Data cleaning & merging
│       ├── clean_text.py
│       ├── validators.py
│       └── merge.py
├── frontend/
│   └── index.html            # Browser UI (Armenian)
├── data/
│   ├── raw/                  # Scraped HTML pages
│   └── processed/            # Cleaned JSON data
├── evaluation/
│   ├── questions.csv         # 49 test questions in Armenian
│   ├── evaluate.py           # Evaluation pipeline
│   ├── results.csv           # Answers + scores
│   └── summary.txt           # Quality summary
├── docs/
│   └── voice_experience_report.md
├── config/
│   └── livekit-server.yaml
└── requirements.txt
```

## Evaluation

We test the assistant with 49 Armenian questions across 4 categories: credits, deposits, branches, and out-of-scope (should refuse).

Run it:
```bash
python evaluation/evaluate.py
```

Latest results:

| Metric | Score (out of 5) |
|--------|-----------------|
| Relevance | 4.67 |
| Accuracy | 4.45 |
| Armenian Quality | 4.73 |
| Conciseness | 4.47 |
| Guardrails (out-of-scope refused) | 10/10 |

## Web scraping

The banking data was scraped from bank websites. To re-scrape:

```bash
cd src
python -m scrapers.ardshinbank.branches
python -m scrapers.ardshinbank.credits
python -m scrapers.ardshinbank.deposits
python -m processing.merge
```

## Known limitations

- **Armenian is not officially supported** by Gemini's native audio model. We enforce it through the system prompt, but the model occasionally mixes in English.
- **All bank data lives in the system prompt** (~16K chars). For production, a RAG pipeline would be needed to handle larger datasets.
- The included `livekit-server.exe` is Windows-only. Download the right binary for your OS.

## Future improvements

- RAG pipeline for scalable knowledge retrieval
- Separate STT/LLM/TTS models for better Armenian support
- Conversation logging for quality monitoring
- Multi-room support for concurrent users

## Tech stack

- **Python 3.10+**
- **LiveKit Agents SDK** — real-time voice framework
- **Google Gemini 2.5 Flash Native Audio** — STT + LLM + TTS in one model
- **Playwright + BeautifulSoup** — web scraping
- **google-genai** — evaluation pipeline
