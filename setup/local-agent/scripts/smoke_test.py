"""Go/no-go: verify the local model emits a correct tool call and measure speed."""
import json
import time
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
}]


def main():
    start = time.time()
    resp = client.chat.completions.create(
        model="qwen3:14b",
        messages=[{"role": "user", "content": "What's the weather in Miami? Use the tool."}],
        tools=TOOLS,
    )
    elapsed = time.time() - start
    msg = resp.choices[0].message
    calls = msg.tool_calls or []
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Tool calls: {len(calls)}")
    assert calls, "FAIL: model did not emit a tool call"
    call = calls[0]
    assert call.function.name == "get_weather", f"FAIL: wrong tool {call.function.name}"
    args = json.loads(call.function.arguments)
    assert args.get("city", "").lower() == "miami", f"FAIL: wrong args {args}"
    print("PASS: model emits correct tool call")


if __name__ == "__main__":
    main()
