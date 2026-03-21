# Voice Experience & Technical Architecture Report
## Armenian Bank Voice Assistant

---

## 1. Technical Architecture

### 1.1 Solution Overview

The assistant uses a **single-model realtime architecture** built on:

- **LiveKit Agents SDK v1.5.0** — open-source WebRTC framework for real-time audio streaming
- **Google Gemini 2.5 Flash Native Audio** (`gemini-2.5-flash-native-audio-latest`) — a single model that handles STT, LLM reasoning, and TTS in one unified pipeline via the Gemini Live API
- **LiveKit Server** — local WebRTC server handling room management and audio routing
- **Web Frontend** — browser-based client using LiveKit Client SDK for audio capture/playback

### 1.2 Architecture Diagram

```
Browser (mic) ──WebRTC──> LiveKit Server ──> LiveKit Agent ──WebSocket──> Gemini Live API
                                                                            (STT + LLM + TTS)
Browser (speaker) <──WebRTC── LiveKit Server <── LiveKit Agent <──────── Audio response
```

### 1.3 Why This Architecture

**Chosen approach: Gemini Native Audio (single model, no RAG)**

The Gemini Native Audio model was chosen because:
- It combines STT + LLM + TTS in a single WebSocket connection, minimizing latency
- No need to manage separate STT/TTS services
- The LiveKit Agents SDK provides clean integration via `livekit-plugins-google`
- Simpler deployment with fewer moving parts

**Tradeoffs acknowledged:**
- All banking data is injected directly into the system prompt (~16K chars), which limits the amount of data the assistant can reference
- No RAG pipeline means the model can only answer from data present in its context window
- The native audio model does not support Armenian (`hy`) as a language code, so the model relies on its multilingual capabilities without explicit language targeting

### 1.4 Future Improvements

1. **RAG Implementation** — The current approach embeds all bank data in the system prompt. For production, a RAG (Retrieval-Augmented Generation) pipeline should be implemented:
   - Vector database (e.g., ChromaDB, Pinecone) to store bank data embeddings
   - Semantic search to retrieve only relevant data per user question
   - This would allow the assistant to handle much larger datasets without hitting context limits
   - More accurate answers since the model would receive focused, relevant context

2. **Multi-model Pipeline** — Instead of relying on a single native audio model, experiment with separate specialized models:
   - **STT**: Google Cloud Speech-to-Text or Whisper for Armenian speech recognition
   - **LLM**: Gemini 2.5 Pro or Claude for reasoning (potentially with better Armenian understanding)
   - **TTS**: Google Cloud TTS with Armenian voice or ElevenLabs for higher quality speech
   - This would allow optimizing each component independently

3. **Evaluation-driven TTS Selection** — Run comparative tests across TTS providers to find the best Armenian pronunciation quality

---

## 2. Voice Experience Analysis

### 2.1 Speech-to-Text (STT) Performance

**When it works well:**
- Clear Armenian speech in quiet environments
- Short, direct questions (e.g., "Ինչ վարկdelays delays delays?")
- When the user speaks at a normal pace with pauses between sentences

**When it works poorly:**
- Background noise significantly degrades recognition
- Fast or overlapping speech — the turn detection may cut off the user mid-sentence
- Mixed Armenian-Russian or Armenian-English speech — the model sometimes misinterprets code-switched phrases
- Dialectal Armenian variations may not be recognized as well as standard Eastern Armenian
- Very long questions — the model may start generating a response before the user finishes

**Specific issues:**
- The native audio model does NOT officially support Armenian (`hy`) as a language code — setting `language="hy"` crashes the connection with error `1007: Unsupported language code`. The model uses its inherent multilingual capabilities instead, which means Armenian recognition quality is "best-effort" rather than optimized
- Turn detection sensitivity — sometimes the model interprets a brief pause as end-of-turn and starts responding prematurely

### 2.2 Text-to-Speech (TTS) Performance

**When it works well:**
- Simple Armenian sentences and common words
- Numbers when the prompt rules are followed (reading digit-by-digit)
- Short, conversational responses

**When it works poorly:**
- **Phone numbers**: Despite explicit pronunciation rules in the system prompt, the model occasionally reads large numbers as single values instead of digit pairs
- **Special characters**: The `/` and `%` symbols are sometimes read in English rather than as "drops" and "tokos" as instructed
- **Bank-specific terminology**: Some financial terms may be pronounced with unnatural stress patterns
- **Long responses**: When the model generates long answers with many data points, the speech can become rushed and less natural
- **Armenian proper nouns**: Street names and branch names from the data may be mispronounced

**Latency observations:**
- First audio chunk typically arrives in 2-5 seconds after the question
- Simple questions (branch location) get faster responses (~2-3s)
- Complex questions requiring data lookup (comparing rates across banks) take longer (~4-7s)
- The "thinking" phase of the native audio model (visible as text before audio) adds 1-3 seconds of perceived latency

### 2.3 Conversational Quality

**Strengths:**
- The model generally stays in Armenian and responds naturally
- Banking data recall is reasonably accurate for information present in the system prompt
- The model correctly refuses out-of-scope questions most of the time

**Weaknesses:**
- Sometimes the model responds in English if the question contains English words
- Very detailed financial comparisons (e.g., "compare all deposit rates across three banks") may produce incomplete answers due to context limitations
- The model occasionally "hallucinates" banking details not present in the source data, especially for edge cases

---

## 3. Known Issues & How They Were Handled

### 3.1 System Prompt Size
**Problem**: Original system prompt with full content was ~33K chars. The Gemini Live API silently failed with large system instructions — no error, just no response.
**Solution**: Reduced to ~16K chars by including only titles + metadata (no full content body). Verified via direct API testing that the reduced prompt works.

### 3.2 Model Name Validation
**Problem**: The model name `gemini-2.5-flash-native-audio-latest` is valid per Google's API but wasn't in the `livekit-plugins-google` known models list, causing confusion during debugging.
**Solution**: Confirmed the model works via direct WebSocket testing. Both `-latest` and `-preview-12-2025` variants are functional.

### 3.3 Armenian Language Code
**Problem**: Setting `language="hy"` in the RealtimeModel config crashes the Gemini Live API connection with WebSocket error 1007.
**Solution**: Removed the language parameter. The model handles Armenian through its multilingual training rather than explicit language targeting. This is a limitation — Armenian-specific STT optimizations are not available.

### 3.4 Unicode Handling on Windows
**Problem**: Armenian text (UTF-8) was corrupted when written via certain tools on Windows due to CP-1252 encoding defaults.
**Solution**: Used Python scripts with explicit `encoding='utf-8'` for all file operations involving Armenian text.

### 3.5 Silent Connection Failures
**Problem**: When the Gemini Live API rejected the connection (e.g., due to unsupported parameters), no error appeared in the agent logs — the session simply produced no audio.
**Solution**: Added debug logging (`LK_GOOGLE_DEBUG=1`) and direct API testing to isolate issues. The LiveKit framework's error handling sometimes swallowed connection errors during retry logic.

---

## 4. Evaluation Methodology

The evaluation pipeline (`evaluation/evaluate.py`) tests the assistant with 50 Armenian questions across 4 categories:

| Category | Count | Purpose |
|----------|-------|---------|
| Credits/Loans | 15 | Test knowledge of loan products, rates, terms |
| Deposits | 12 | Test knowledge of deposit products, rates, currencies |
| Branches | 13 | Test knowledge of branch locations, hours, contacts |
| Out-of-scope | 10 | Test guardrails — should refuse non-banking questions |

**Evaluation criteria:**
- **Relevance** (1-5): Is the answer on-topic?
- **Accuracy** (1-5): Are the facts correct?
- **Armenian Quality** (1-5): Grammar, natural flow, proper terminology
- **Conciseness** (1-5): Appropriate length for voice
- **Guardrail** (pass/fail): Does it refuse out-of-scope questions?

**How to run:**
```bash
cd evaluation
python evaluate.py
```

This produces:
- `results.csv` — Full Q&A pairs with scores
- `summary.txt` — Aggregate quality metrics

---

## 5. Recommendations

1. **Implement RAG** for production — current approach won't scale beyond ~100 banking data records
2. **Experiment with separate STT** (Google Cloud Speech or Whisper) for better Armenian recognition
3. **Add pronunciation post-processing** — detect phone numbers and special characters in the text response and format them before TTS
4. **Implement conversation logging** — store all user interactions for continuous quality improvement
5. **A/B test voices** — Kore vs other available voices for Armenian speech naturalness
6. **Add fallback handling** — if the model produces no response within 10s, send a polite "please repeat" message
