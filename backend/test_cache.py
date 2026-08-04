from app.providers.cache import provider_cache

print(provider_cache.has("ollama"))

provider_cache.set("ollama", object())

print(provider_cache.has("ollama"))

print(provider_cache.get("ollama"))
