import json
import requests
from ollama import Client

MODEL = "qwen3:4b-instruct"
OLLAMA_HOST = "http://127.0.0.1:11500"
MAX_CONTENT_CHARS = 15000

client = Client(host=OLLAMA_HOST)


def fetch_url(url):
    print(f"\n[FETCH] {url}")

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        content = response.text

        print(f"[STATUS] {response.status_code}")
        print(f"[SIZE] {len(content):,} bytes")

        # Keep the prompt size manageable
        if len(content) > MAX_CONTENT_CHARS:
            print(f"[TRUNCATED] {len(content):,} -> {MAX_CONTENT_CHARS:,} characters")
            content = (
                content[:MAX_CONTENT_CHARS]
                + "\n\n...[CONTENT TRUNCATED BY CLIENT]..."
            )

        return {
            "url": url,
            "status_code": response.status_code,
            "content_length": len(response.text),
            "content": content
        }

    except Exception as e:
        return {
            "url": url,
            "status_code": None,
            "error": str(e)
        }


tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch the contents of a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Complete URL to fetch."
                    }
                },
                "required": ["url"],
                "additionalProperties": False
            }
        }
    }
]


messages = [
    {
        "role": "user",
        "content": """
Compare these two webpages.

You MUST fetch BOTH URLs before answering.

1. http://en.wikipedia.org/wiki/Installation_computer_programs
2. http://wikitest.com/wiki/10979

After fetching both pages:

- Summarize each webpage separately.
- Compare their main topics.
- Point out any factual differences.
- Mention if either page returned an error.
"""
    }
]


# ---------------- First model call ----------------

response = client.chat(
    model=MODEL,
    messages=messages,
    tools=tools
)

print("\n========== TOOL REQUEST ==========")
print(response.message)

messages.append(response.message)


# ---------------- Execute tools ----------------

if response.message.tool_calls:

    for i, tool_call in enumerate(response.message.tool_calls, start=1):

        if tool_call.function.name != "fetch_url":
            continue

        url = tool_call.function.arguments["url"]

        result = fetch_url(url)

        print(f"\n========== FETCH RESULT #{i} ==========")
        print(json.dumps(result, indent=2)[:2000])
        print("=======================================")

        messages.append(
            {
                "role": "tool",
                "tool_name": "fetch_url",
                "content": json.dumps(result, ensure_ascii=False)
            }
        )

    print("\n========== SENDING BACK TO MODEL ==========")
    print(f"Conversation contains {len(messages)} messages.")
    print("===========================================")

    # ---------------- Second model call ----------------

    final = client.chat(
        model=MODEL,
        messages=messages
    )

    print("\n========== FINAL ANSWER ==========")
    print(final.message.content)

else:

    print("\nModel did not request any tools.")
    print(response.message.content)
