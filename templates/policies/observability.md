# Observability policy

Project-specific rules live in [`project/observability.md`](project/observability.md) when the project provides one; they extend this policy and win on conflict.

For background work and integrations, expose operation, resource ID where safe, state transition, duration and error class. Distinguish retryable failure, permanent invalid input and success. A failed indexing, provider or migration step must not appear complete.

Never log secrets, tokens, credentials, private user content or access-restricted data into shared operational logs. Avoid full source paths when an ID suffices. Keep retry limits and idempotence explicit; record enough context to repair a failed job without exposing protected content. When a provider is unavailable, show a truthful unavailable state and retain the source's authority.
