import asyncio

import app.providers.adapters

from app.providers.manager import provider_manager


async def main():

    print(
        await provider_manager.health(
            "ollama",
        )
    )

    models = await provider_manager.list_models(
        "ollama",
    )

    for model in models:

        print(model["name"])

    await provider_manager.close()


asyncio.run(main())