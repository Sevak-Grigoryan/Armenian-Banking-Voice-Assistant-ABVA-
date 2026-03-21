import os
import json
import logging
from livekit import agents
from dotenv import load_dotenv
from livekit.plugins.google import realtime
from livekit.agents import Agent, AgentServer, AgentSession

logging.basicConfig(level=logging.DEBUG)
os.environ["LK_GOOGLE_DEBUG"] = "1"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "full_data")


def load_bank_data() -> str:

    sections = []

    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith(".json"):
            continue

        with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
            items = json.load(f)

        bank_name = items[0]["bank_name"] if items else filename
        entries = []

        for item in items:
            title = item.get("title", "")
            meta = item.get("metadata", {})
            meta_str = ", ".join(
                f"{k}: {v}" for k, v in meta.items() if v
            )
            entry = f"- {title}"
            if meta_str:
                entry += f" ({meta_str})"
            entries.append(entry)

        sections.append(f"=== {bank_name} ===\n" + "\n".join(entries))

    return "\n\n".join(sections)


BANK_DATA = load_bank_data()

SYSTEM_PROMPT = f"""You are a professional Armenian Bank Assistant voice bot.
You MUST always respond in Armenian (Hayeren).
You are an expert on Armenian banking services for the following banks: Ardshinbank, Artsakhbank, and Mellat Bank.

RULES:
1. ONLY answer questions related to the banking data provided below.
2. If a question is NOT about these banks or their services, politely say in Armenian that you can only help with banking questions about these three banks.
3. Keep responses concise and conversational — this is a voice chat.
4. When discussing loans, always mention the interest rate, term, and currency if available.
5. When discussing branches, mention the address and working hours.

PRONUNCIATION RULES FOR VOICE OUTPUT (CRITICAL):
6. Phone numbers: ALWAYS read digit-by-digit in PAIRS after the country code.
   Example: +374 10 51 22 11 — say "պլյուս երեք յոթան չորս, տաս, հիսունմեկ, քսաներկու, տասնեմեկ"
   NEVER read a phone number as one big number. Pause between each pair.
7. The "/" and "\\" symbols: ALWAYS read as "դռոբ" (drop).
   Example: "1/2" → "մեկ դռոբ երկու" (mek drop erku)
   Example: "3/4" → "երեք դռոբ չորս" (yerek drop chors)
8. The "%" symbol: read as "տոկոս" (tokos).
   Example: "14.5%" → "տասնչորս ամբողջ կետ հինգ տոկոս" — NEVER skip the decimal part.
9. Currency: "AMD" = "հայկական դրամ", "USD" = "դոլար", "EUR" = "եվրո".
10. Large numbers: read naturally in Armenian. 5,000,000 = "հինգ միլիոն", 100,000 = "հարյուր հազար".

ARMENIAN SPEECH QUALITY:
11. Use correct Armenian grammar, pronunciation, stress patterns, and natural intonation.
12. Do NOT mix in Russian or English words — always use Armenian equivalents.
13. Bank names are proper nouns, keep as-is: Արդշինբանկ, Արցախբանկ, Mellat Bank.
14. When reading working hours, clearly separate each day range with pauses.
15. When listing multiple services, use natural conjunctions like "և" (and) or "կամ" (or) in Armenian.
16. the time 12:00 or else  always read as "տասներկու զրո զրո"( tasnerku zro zro ) 
BANKING DATA:
{BANK_DATA}
"""


class BankAssistant(Agent):
    def __init__(self):
        super().__init__(instructions=SYSTEM_PROMPT)


server = AgentServer(
    ws_url="ws://localhost:7880",
    api_key="devkey",
    api_secret="a]vk>kKga2AN5r0R2Q!B8wzbse0bkLCC",
    port=8082,
    num_idle_processes=1,
    load_threshold=0.95,
)


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        llm=realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-latest",
            api_key=os.getenv("GEMINI_API_KEY"),
            voice="Kore",
        ),
    )

    await session.start(
        agent=BankAssistant(),
        room=ctx.room,
    )

    await session.generate_reply(
        instructions=(
            "Greet the user in Armenian. Say: "
            "'Barev dzez! Yes Hayastani bankeri oknakann em. "
            "Karogh em dzer ognel Ardshinbanki, Artsakhbanki kam Mellat Banki "
            "tsarayutyunneri masin. Inchov karogh em ognel?'"
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)