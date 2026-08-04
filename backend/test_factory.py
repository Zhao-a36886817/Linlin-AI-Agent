import asyncio

import app.providers.adapters
from app.providers.factory import ProviderFactory


async def main() -> None:
    provider = ProviderFactory.create("ollama")

    try:
        print("Provider:", type(provider).__name__)
        print("Healthy:", await provider.health())

        models = await provider.list_models()

        print("Models:")

        for model in models:
            print("-", model.get("name", "unknown"))
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())