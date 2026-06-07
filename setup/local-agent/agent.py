"""Custom tool-calling loop over Ollama's OpenAI-compatible endpoint (Phase 1b)."""
import json
import os

import registry

SYSTEM_PROMPT = (
    "You are FamilyVault's assistant. Use the tools to search the photo library, "
    "create projects, and build timelines. Build the full ordered list of asset_ids "
    "and call set_timeline once. When the task is done, reply with a short summary."
)


def run_loop(client, user_message: str, model: str, max_iters: int = 10):
    """Run the agent loop. Returns (final_text, transcript)."""
    schemas = registry.openai_schemas()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    for _ in range(max_iters):
        resp = client.chat.completions.create(model=model, messages=messages, tools=schemas)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return (msg.content or "", messages)
        messages.append({"role": "assistant", "content": msg.content,
                         "tool_calls": [
                             {"id": tc.id, "type": "function",
                              "function": {"name": tc.function.name,
                                           "arguments": tc.function.arguments}}
                             for tc in tool_calls]})
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                result = registry.dispatch(tc.function.name, args)
            except Exception as e:  # surface tool errors back to the model
                result = {"error": str(e)}
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, default=str)})
    return ("Stopped: reached the maximum number of steps.", messages)


def main():
    import sys
    from openai import OpenAI

    model = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1")
    client = OpenAI(base_url=base_url, api_key="ollama")
    user_message = " ".join(sys.argv[1:]) or input("Request: ")
    answer, _ = run_loop(client, user_message, model=model)
    print(answer)


if __name__ == "__main__":
    main()
