import asyncio

from app.providers.adapters.ollama import OllamaProvider


async def main():
    provider = OllamaProvider()

    print("Streaming...\n")

    async for chunk in provider.stream(
        model="llama3.2:3b",
        messages=[
            {
                "role": "user",
                "content": "請用一句話介紹 Linlin Agent。",
            }
        ],
    ):
        print(chunk)

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())