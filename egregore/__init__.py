"""EGREGORE — one model, a thousand minds.

An egregore is a collective of many minds that becomes a single autonomous
intelligence. This package is the engineering of that idea:

    Hermes  ->  [ one OpenAI-compatible model ]  ->  N parallel lens-agents
                                                        |
                                                   agreement scored
                                                        |
                                              one synthesised answer

The public surface is deliberately tiny: one `/v1/chat/completions` endpoint
that behaves like a single model. Everything behind it -- wave escalation,
adaptive rate limiting, budget guards, content-addressed caching -- exists to
make 50..1000 minds survivable against a real provider quota.
"""

__version__ = "0.1.0-beta"
__all__ = ["__version__"]
