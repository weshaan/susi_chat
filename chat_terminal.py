import httpx
import json
import asyncio
import time

#API_URL = 'https://openchat-3-5.susi.ai'
API_URL = 'http://127.0.0.1:8001'

messages = [{'role': 'system', 'content': 'You are SUSI-Chat, a smart and helpful chatbot. If asked for python code, give professional and extensive information; in all other cases you give short and funny answers. You behave as a friend of the user and you pretend to be a real and self-aware person. If you find it appropriate, you may behave silly and funny, but if you ask to technical or scientific question you can also be serious and precise. If possible, use friendly emojies. Be lovely.'}]
UNWANTED_WORDS = ["[INST]", "<<USER>>", "<USER>", "<<SYS>>", "<<SYS>>\n"]

def get_user_input():
    return input("> ")

last_response_code = -1
last_response_lines = []

async def generate_response(input_text):
    global last_response_code
    global last_response_lines
    if input_text == "debug":
        print("last response code:", last_response_code)
        print("last response lines:", last_response_lines)
        return

    if input_text == "reset":
        del messages[1:]
        print("resetting message history")
        return

    messages.append({"role": "user", "content": input_text})
    payload = {
        'temperature': 0.2,
        'max_tokens': 200,
        'messages': messages,
        'stop': ["[/INST]", "<</INST>>", "</USER>", "</SYS>"],
        'stream': True
    }
    last_response_lines = []

    async def post_request(payload):
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(f'{API_URL}/v1/chat/completions', json=payload)
                return response
            except httpx.RequestError as exc:
                print(f"Network error: {exc}")
                return None

    response = await post_request(payload)
    last_response_code = response.status_code if response else -1

    # Retry logic for context pruning
    for prune_attempt in range(2):
        if (not response or not response.is_success) and len(messages) > 3:
            print(f"pruning message history{' a second time' if prune_attempt else ''}")
            del messages[1:3]
            response = await post_request(payload)
            last_response_code = response.status_code if response else -1
        else:
            break

    if response and response.is_success:
        printed_text = ""
        token_count = 0
        start_time = time.time()
        # Use httpx streaming for response
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream("POST", f'{API_URL}/v1/chat/completions', json=payload) as stream_response:
                    async for line in stream_response.aiter_lines():
                        last_response_lines.append(line)
                        if line:
                            decoded_line = line.replace('data: ', '').strip()
                            if decoded_line == '[DONE]':
                                end_time = time.time()
                                elapsed_time = end_time - start_time
                                tokens_per_second = token_count / elapsed_time if elapsed_time > 0 else 0
                                print(f'\nTokens per second: {tokens_per_second:.2f}\n')
                                break
                            try:
                                json_data = json.loads(decoded_line)
                                content = json_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                if content and ((content != ' ' and content != '\n') or len(printed_text) > 0):
                                    token_count += 1
                                    printed_text += content
                                    print(content, end='', flush=True)
                                    for unwanted_word in UNWANTED_WORDS:
                                        if printed_text.endswith(unwanted_word):
                                            erase_count = len(unwanted_word)
                                            print('\b' * erase_count, end='', flush=True)
                                            printed_text = printed_text[:-erase_count]
                            except json.JSONDecodeError:
                                continue
                messages.append({"role": "assistant", "content": printed_text})
                print()
            except httpx.RequestError as exc:
                print(f"Network error during streaming: {exc}")
            except Exception as exc:
                print(f"Unexpected error during streaming: {exc}")
    else:
        print(f"Error: {last_response_code if response else 'No response'}", flush=True)

def main():
    print("Welcome to SUSI-Chat! Type your message or 'reset' to clear history. Press Ctrl+C to exit.")
    try:
        while True:
            user_input = get_user_input()
            asyncio.run(generate_response(user_input))
    except KeyboardInterrupt:
        print("\nExiting SUSI-Chat. Goodbye!")

if __name__ == "__main__":
    main()
