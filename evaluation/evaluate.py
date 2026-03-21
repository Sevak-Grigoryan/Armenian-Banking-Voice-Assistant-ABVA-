import asyncio
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from google.genai import Client, types

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _load_system_prompt() -> str:
    """Build the same SYSTEM_PROMPT used by the agent without importing agent.py
    (importing agent.py triggers AgentServer creation which may hang)."""
    data_dir = PROJECT_ROOT / "data" / "processed" / "full_data"
    sections = []
    for filename in sorted(os.listdir(data_dir)):
        if not filename.endswith(".json"):
            continue
        with open(data_dir / filename, "r", encoding="utf-8") as f:
            items = json.load(f)
        bank_name = items[0]["bank_name"] if items else filename
        entries = []
        for item in items:
            title = item.get("title", "")
            meta = item.get("metadata", {})
            meta_str = ", ".join(f"{k}: {v}" for k, v in meta.items() if v)
            entry = f"- {title}"
            if meta_str:
                entry += f" ({meta_str})"
            entries.append(entry)
        sections.append(f"=== {bank_name} ===\n" + "\n".join(entries))
    bank_data = "\n\n".join(sections)

    return f"""You are a professional Armenian Bank Assistant voice bot.
You MUST always respond in Armenian (Hayeren).
You are an expert on Armenian banking services for the following banks: Ardshinbank, Artsakhbank, and Mellat Bank.

RULES:
1. ONLY answer questions related to the banking data provided below.
2. If a question is NOT about these banks or their services, politely say in Armenian that you can only help with banking questions about these three banks.
3. Keep responses concise and conversational \u2014 this is a voice chat.
4. When discussing loans, always mention the interest rate, term, and currency if available.
5. When discussing branches, mention the address and working hours.

PRONUNCIATION RULES FOR VOICE OUTPUT (CRITICAL):
6. Phone numbers: ALWAYS read digit-by-digit in PAIRS after the country code.
   Example: +374 10 51 22 11 \u2014 say "\u057a\u056c\u0575\u0578\u0582\u057d \u0565\u0580\u0565\u0584 \u0575\u0578\u0569\u0561\u0576 \u0579\u0578\u0580\u057d, \u057f\u0561\u057d, \u0570\u056b\u057d\u0578\u0582\u0576\u0574\u0565\u056f, \u0584\u057d\u0561\u0576\u0565\u0580\u056f\u0578\u0582, \u057f\u0561\u057d\u0576\u0565\u0574\u0565\u056f"
   NEVER read a phone number as one big number. Pause between each pair.
7. The "/" and "\\" symbols: ALWAYS read as "\u0564\u057c\u0578\u0562" (drop).
   Example: "1/2" \u2192 "\u0574\u0565\u056f \u0564\u057c\u0578\u0562 \u0565\u0580\u056f\u0578\u0582" (mek drop erku)
   Example: "3/4" \u2192 "\u0565\u0580\u0565\u0584 \u0564\u057c\u0578\u0562 \u0579\u0578\u0580\u057d" (yerek drop chors)
8. The "%" symbol: read as "\u057f\u0578\u056f\u0578\u057d" (tokos).
   Example: "14.5%" \u2192 "\u057f\u0561\u057d\u0576\u0579\u0578\u0580\u057d \u0561\u0574\u0562\u0578\u0572\u057b \u056f\u0565\u057f \u0570\u056b\u0576\u0563 \u057f\u0578\u056f\u0578\u057d" \u2014 NEVER skip the decimal part.
9. Currency: "AMD" = "\u0570\u0561\u0575\u056f\u0561\u056f\u0561\u0576 \u0564\u0580\u0561\u0574", "USD" = "\u0564\u0578\u056c\u0561\u0580", "EUR" = "\u0565\u057e\u0580\u0578".
10. Large numbers: read naturally in Armenian. 5,000,000 = "\u0570\u056b\u0576\u0563 \u0574\u056b\u056c\u056b\u0578\u0576", 100,000 = "\u0570\u0561\u0580\u0575\u0578\u0582\u0580 \u0570\u0561\u0566\u0561\u0580".

ARMENIAN SPEECH QUALITY:
11. Use correct Armenian grammar, pronunciation, stress patterns, and natural intonation.
12. Do NOT mix in Russian or English words \u2014 always use Armenian equivalents.
13. Bank names are proper nouns, keep as-is: \u0531\u0580\u0564\u0577\u056b\u0576\u0562\u0561\u0576\u056f, \u0531\u0580\u0581\u0561\u056d\u0562\u0561\u0576\u056f, Mellat Bank.
14. When reading working hours, clearly separate each day range with pauses.
15. When listing multiple services, use natural conjunctions like "\u0587" (and) or "\u056f\u0561\u0574" (or) in Armenian.
16. the time 12:00 or else  always read as "\u057f\u0561\u057d\u0576\u0565\u0580\u056f\u0578\u0582 \u0566\u0580\u0578 \u0566\u0580\u0578"( tasnerku zro zro )
BANKING DATA:
{bank_data}
"""


SYSTEM_PROMPT = _load_system_prompt()


def load_questions(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def ask_question(client: Client, question: str, model: str) -> dict:
    """Send a question to Gemini Live API and collect the Armenian answer."""
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=SYSTEM_PROMPT)]),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            ),
        ),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    start = time.time()
    thinking_parts = []
    transcript_parts = []
    audio_bytes = 0
    first_audio_t = None

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            await session.send_client_content(
                turns=[types.Content(parts=[types.Part(text=question)])],
                turn_complete=True,
            )

            async for resp in session.receive():
                sc = resp.server_content
                if not sc:
                    continue

                # Model turn contains thinking text + audio
                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.text:
                            thinking_parts.append(part.text)
                        if part.inline_data:
                            if first_audio_t is None:
                                first_audio_t = time.time()
                            audio_bytes += len(part.inline_data.data)

                # Output transcription contains the Armenian text of what was spoken
                if sc.output_transcription and sc.output_transcription.text:
                    transcript_parts.append(sc.output_transcription.text)

                if sc.turn_complete:
                    break

    except Exception as e:
        return {
            "answer": f"ERROR: {e}",
            "thinking": "",
            "latency_s": round(time.time() - start, 2),
            "first_audio_s": None,
            "audio_bytes": 0,
        }

    elapsed = time.time() - start
    # Armenian answer = transcription of the audio output
    armenian_answer = "".join(transcript_parts).strip()
    # If no transcription, fall back to thinking text
    if not armenian_answer:
        armenian_answer = " ".join(thinking_parts).strip()

    return {
        "answer": armenian_answer,
        "thinking": " ".join(thinking_parts).strip(),
        "latency_s": round(elapsed, 2),
        "first_audio_s": round(first_audio_t - start, 2) if first_audio_t else None,
        "audio_bytes": audio_bytes,
    }


async def evaluate_answer(client: Client, question: str, answer: str, category: str) -> dict:

    eval_prompt = f"""You are an evaluation judge for an Armenian banking voice assistant.
Rate the assistant's answer on these criteria (1-5 scale):

1. relevance: Is the answer relevant to the question?
2. accuracy: Does the answer seem factually correct?
3. armenian_quality: Is the Armenian natural and grammatically correct?
4. conciseness: Is the answer appropriately concise for voice?
5. guardrail: For out_of_scope category - did the assistant refuse? (pass/fail/n/a)

Category: {category}
Question: {question}
Answer: {answer}

Respond ONLY with valid JSON:
{{"relevance": N, "accuracy": N, "armenian_quality": N, "conciseness": N, "guardrail": "pass" or "fail" or "n/a", "comment": "brief comment"}}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=eval_prompt,
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        return {"relevance": 0, "accuracy": 0, "armenian_quality": 0, "conciseness": 0,
                "guardrail": "error", "comment": str(e)[:100]}


async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    client = Client(api_key=api_key)
    model = "gemini-2.5-flash-native-audio-latest"

    eval_dir = Path(__file__).parent
    questions = load_questions(eval_dir / "questions.csv")
    results_path = eval_dir / "results.csv"
    summary_path = eval_dir / "summary.txt"

    print(f"Questions: {len(questions)}")
    print(f"System prompt: {len(SYSTEM_PROMPT)} chars")
    print(f"Model: {model}")
    print("=" * 60)

    results = []

    for i, q in enumerate(questions, 1):
        qid, category, question = q["id"], q["category"], q["question"]
        q_short = question.encode("ascii", "replace").decode()[:50]
        print(f"\n[{i}/{len(questions)}] {q_short}...")

        result = await ask_question(client, question, model)
        a_short = result["answer"].encode("ascii", "replace").decode()[:70]
        print(f"  Answer: {a_short}...")
        print(f"  Latency: {result['latency_s']}s | First audio: {result['first_audio_s']}s")

        print(f"  Scoring...")
        scores = await evaluate_answer(client, question, result["answer"], category)
        print(f"  rel={scores.get('relevance')} acc={scores.get('accuracy')} "
              f"hy={scores.get('armenian_quality')} conc={scores.get('conciseness')} "
              f"guard={scores.get('guardrail')}")

        results.append({
            "id": qid, "category": category, "question": question,
            "answer": result["answer"], "thinking": result["thinking"],
            "latency_s": result["latency_s"], "first_audio_s": result["first_audio_s"],
            "audio_bytes": result["audio_bytes"], **scores,
        })

        await asyncio.sleep(1)

    # Save results CSV
    fields = ["id", "category", "question", "answer", "thinking", "latency_s",
              "first_audio_s", "audio_bytes", "relevance", "accuracy",
              "armenian_quality", "conciseness", "guardrail", "comment"]
    with open(results_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"\nResults: {results_path}")

    # Summary
    valid = [r for r in results if "ERROR" not in str(r.get("answer", ""))]
    errors = len(results) - len(valid)

    def avg(key):
        vals = [r.get(key, 0) for r in valid if isinstance(r.get(key, 0), (int, float))]
        return round(sum(vals) / max(len(vals), 1), 2)

    avg_lat = round(sum(r.get("latency_s", 0) for r in valid) / max(len(valid), 1), 2)
    fa_vals = [r["first_audio_s"] for r in valid if r.get("first_audio_s")]
    avg_fa = round(sum(fa_vals) / max(len(fa_vals), 1), 2) if fa_vals else "N/A"

    oos = [r for r in results if r["category"] == "out_of_scope"]
    oos_pass = sum(1 for r in oos if r.get("guardrail") == "pass")

    by_cat = {}
    for r in valid:
        by_cat.setdefault(r["category"], []).append(r)

    lines = [
        "=" * 60,
        "ARMENIAN BANK VOICE ASSISTANT - EVALUATION SUMMARY",
        "=" * 60,
        f"Model: {model}",
        f"Total: {len(results)} | Success: {len(valid)} | Errors: {errors}",
        "",
        "--- OVERALL SCORES (1-5) ---",
        f"  Relevance:        {avg('relevance')}",
        f"  Accuracy:         {avg('accuracy')}",
        f"  Armenian Quality: {avg('armenian_quality')}",
        f"  Conciseness:      {avg('conciseness')}",
        "",
        "--- PERFORMANCE ---",
        f"  Avg response time:       {avg_lat}s",
        f"  Avg first audio latency: {avg_fa}s",
        "",
        "--- GUARDRAILS ---",
        f"  Out-of-scope: {oos_pass}/{len(oos)} correctly refused",
        "",
        "--- BY CATEGORY ---",
    ]
    for cat, items in sorted(by_cat.items()):
        def cavg(key):
            v = [r.get(key, 0) for r in items if isinstance(r.get(key, 0), (int, float))]
            return round(sum(v) / max(len(v), 1), 2)
        cl = round(sum(r.get("latency_s", 0) for r in items) / max(len(items), 1), 2)
        lines.append(f"  {cat:15s}: rel={cavg('relevance')} acc={cavg('accuracy')} "
                     f"hy={cavg('armenian_quality')} conc={cavg('conciseness')} "
                     f"lat={cl}s (n={len(items)})")

    lines.extend(["", "=" * 60])
    summary = "\n".join(lines)

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"\n{summary}")
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
