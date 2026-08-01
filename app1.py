import json
import requests
from ollama import Client

MODEL = "qwen3:4b-instruct"
OLLAMA_HOST = "http://127.0.0.1:11500"
MAX_CONTENT_CHARS = 6000
NUM_CTX = 8192

URL_1 = "http://en.wikipedia.org/wiki/Installation_computer_programs"
URL_2 = "http://wikitest.com/wiki/10979"

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


def fetch_and_summarize(url, stage_label):
    """
    Isolated conversation: fetch a single URL and produce a summary.
    Returns the summary string, or None on failure.
    """

    print(f"\n{'='*60}")
    print(f"STAGE: {stage_label}")
    print(f"{'='*60}")

    messages = [
        {
            "role": "user",
            "content": (
                f"Fetch the following URL and produce a detailed summary of its content.\n\n"
                f"URL: {url}\n\n"
                f"Your summary should cover:\n"
                f"- The main topic of the page\n"
                f"- Key facts and claims made\n"
                f"- Any notable details\n\n"
                f"If the fetch fails, report the error."
            )
        }
    ]

    # First call — expect a tool call
    response = client.chat(
        model=MODEL,
        messages=messages,
        tools=tools,
        options={"num_ctx": NUM_CTX}
    )

    print(f"\n[TOOL REQUEST] {response.message}")
    messages.append(response.message)

    if not response.message.tool_calls:
        print("[WARNING] Model did not request a tool.")
        return response.message.content

    # Execute the tool calls
    for tool_call in response.message.tool_calls:
        if tool_call.function.name != "fetch_url":
            continue

        fetched_url = tool_call.function.arguments["url"]
        result = fetch_url(fetched_url)

        print(f"\n[FETCH RESULT]")
        print(json.dumps(result, indent=2)[:2000])

        messages.append(
            {
                "role": "tool",
                "tool_name": "fetch_url",
                "content": json.dumps(result, ensure_ascii=False)
            }
        )

    # Second call — produce the summary
    summary_response = client.chat(
        model=MODEL,
        messages=messages,
        options={"num_ctx": NUM_CTX}
    )

    summary = summary_response.message.content

    print(f"\n[SUMMARY]\n{summary}")

    return summary


# ---------------- Stage 1: Summarize URL 1 ----------------

summary_1 = fetch_and_summarize(URL_1, f"Summarizing URL 1: {URL_1}")

# ---------------- Stage 2: Summarize URL 2 ----------------

summary_2 = fetch_and_summarize(URL_2, f"Summarizing URL 2: {URL_2}")

# ---------------- Stage 3: Compare the summaries ----------------

print(f"\n{'='*60}")
print("STAGE: Comparing summaries")
print(f"{'='*60}")

compare_messages = [
    {
        "role": "user",
        "content": (
            f"You previously fetched and summarized two webpages separately.\n"
            f"The summaries below were produced by you — they are NOT the original page text.\n\n"
            f"---\n"
            f"YOUR SUMMARY OF URL 1 ({URL_1}):\n"
            f"{summary_1}\n\n"
            f"---\n"
            f"YOUR SUMMARY OF URL 2 ({URL_2}):\n"
            f"{summary_2}\n\n"
            f"---\n\n"
            f"Based on your summaries:\n"
            f"- Compare the main topics of the two pages.\n"
            f"- Point out any factual differences between them.\n"
            f"- Note anything that appears in one summary but not the other.\n"
            f"- Mention if either fetch returned an error.\n\n"
            f"Remember: you are comparing your own summaries, not the original full text."
        )
    }
]

final = client.chat(
    model=MODEL,
    messages=compare_messages,
    options={"num_ctx": NUM_CTX}
)

print(f"\n{'='*60}")
print("FINAL COMPARISON")
print(f"{'='*60}")
print(final.message.content)
