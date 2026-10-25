"""Magic-link delivery.

``send_magic_link`` picks the transport named by ``MAIL_TRANSPORT``:

| Value | Module | Variables |
| --- | --- | --- |
| ``console`` | ``console`` | — (development only; refused when ``REFLEX_ENV_MODE=prod``) |
| ``smtp`` | ``smtp`` | ``SMTP_HOST``, ``SMTP_PORT``, ``SMTP_SECURITY``, ``SMTP_USERNAME``, ``SMTP_PASSWORD``, ``MAIL_FROM`` |
| ``mailgun`` | ``mailgun`` | ``MAILGUN_API_KEY``, ``MAILGUN_DOMAIN``, ``MAILGUN_API_URL``, ``MAIL_FROM`` |
| ``graph`` | ``graph`` | ``GRAPH_TENANT_ID``, ``GRAPH_CLIENT_ID``, ``GRAPH_CLIENT_SECRET``, ``GRAPH_SENDER`` |

All credentials are read from the environment by the backend process and
never reach a Reflex state.
"""
