# Dynamic cloud providers

P27 activates cloud model APIs through the existing Provider Runtime and
Credential Store. Linlin does not embed API keys, base URLs, or model IDs.

## Connect flow

1. The operator enters a display name, provider API base URL, and exactly one
   credential source: a one-time API key or an existing environment variable.
2. The operator explicitly consents to contacting that endpoint.
3. The backend validates the URL. Remote endpoints require HTTPS; loopback HTTP
   remains available for locally operated compatible gateways.
4. The backend detects the protocol from the key/hostname, unless the operator
   selected a provider kind explicitly.
5. Linlin creates a temporary adapter and calls the provider model-list API.
   Failed endpoint validation does not create a provider configuration. Some
   providers, including NVIDIA, expose a public model catalog, so listing models
   alone does not prove that a credential can run every listed model.
6. A submitted key is stored through Credential Store. The provider JSON stores
   only an opaque credential reference, endpoint, kind, and non-secret metadata.
7. The verified adapter is registered dynamically in `ProviderManager` as
   `cloud:<provider UUID>` and discovered models become selectable in Chat.

## Supported protocols

- OpenAI-compatible chat completions and SSE: OpenAI, OpenRouter, Groq,
  DeepSeek, Mistral, and custom compatible gateways.
- Anthropic Messages and Messages SSE.
- Gemini generateContent and StreamGenerateContent SSE.

All adapters normalize chat, streaming, tools metadata, completion status, and
usage into the existing `BaseProvider` contract. Provider adapters never execute
tools directly.

## Credential behavior

- Linlin prefers the operating system keyring when an available backend exists.
- If the OS vault is unavailable, the API reports that credentials are
  session-only; it never silently stores plaintext credentials in provider JSON.
- API keys use `SecretStr` at request validation, are not returned by any API,
  are not placed in URLs, and are not included in provider error bodies.
- Deleting a provider unregisters and closes its adapter, deletes its provider
  configuration, and removes the stored credential.

## NVIDIA hosted inference

`https://integrate.api.nvidia.com/v1` requires a Hosted Inference key obtained
from `https://build.nvidia.com/settings/api-keys`. These keys begin with
`nvapi-`; an NGC personal key is a different credential and is rejected before
the provider configuration is stored. NVIDIA `401` and `403` responses are
reported as credential or model-permission failures without forwarding the
provider response body, which may contain sensitive details.

## Explicit cloud boundary

Cloud model discovery occurs only during the consented connect/refresh actions.
Ordinary model listing reads the resulting in-memory discovery cache and does
not silently contact configured cloud endpoints. Chat displays a cloud-transfer
notice before the operator sends a message.

## Cost classification

Dynamic cloud providers default to `UNKNOWN`. Linlin does not claim that any
cloud API is permanently free; billing and data-handling terms remain those of
the operator-selected provider.
