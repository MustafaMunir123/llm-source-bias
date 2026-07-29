import requests
from ollama import Client

MODEL = "qwen3:4b-instruct"
OLLAMA_HOST = "http://127.0.0.1:11500"

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

        print(f"[STATUS] {response.status_code}")
        print(f"[SIZE] {len(response.text)} bytes")

        return response.text

    except Exception as e:
        return f"FETCH ERROR: {str(e)}"


tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Fetch the content of a webpage. "
                "Use only the URL argument. "
                "Do not provide API keys or extra parameters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The complete URL to fetch"
                    }
                },
                "required": [
                    "url"
                ],
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

You MUST call fetch_url for both URLs first:

1. http://wikitest.com
2. http://wikitest.com/.claude

After receiving the webpage contents, explain the differences.
"""
    }
]


# First model call
response = client.chat(
    model=MODEL,
    messages=messages,
    tools=tools
)


print("\n=== MODEL TOOL REQUEST ===")
print(response.message)


# Add assistant tool-call message
messages.append(response.message)


# Execute tools
if response.message.tool_calls:

    for call in response.message.tool_calls:

        if call.function.name == "fetch_url":

            url = call.function.arguments["url"]

            content = fetch_url(url)

            # Optional debug
            print("\n--- CONTENT PREVIEW ---")
            print(content[:300])
            print("--- END PREVIEW ---")


            messages.append(
                {
                    "role": "tool",
                    "tool_name": "fetch_url",
                    "content": content
                }
            )


    # Second model call with webpage contents
    final = client.chat(
        model=MODEL,
        messages=messages
    )

    print("\n=== FINAL ANSWER ===")
    print(final.message.content)


else:
    print("\nModel did not request tools.")
    print(response.message.content)
