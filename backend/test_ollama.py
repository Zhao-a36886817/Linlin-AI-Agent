import asyncio

from app.providers.adapters.ollama import OllamaProvider


async def main():
    provider = OllamaProvider()

    response = await provider.chat(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "請用一句話介紹你自己。"}],
    )

    print()

    print("Provider")
    print(response["provider"])

    print()

    print("Model")
    print(response["model"])

    print()

    print("Thinking")
    print(response["thinking"])

    print()

    print("Answer")
    print(response["content"])

    print()

    print("Usage")
    print(response["usage"])


if __name__ == "__main__":
    asyncio.run(main())
