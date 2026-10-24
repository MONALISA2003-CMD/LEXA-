# LEXA API provider keys for Render

**Important:** For this integration, leave external execution disabled. You do not need any provider key to run the main CI suite. The mock-only tests do not use real provider credits or keys.

If you decide to store a provider key in Render for a later, separately approved phase, add it only to the **private Render environment for the LEXA API service**. Never put keys in GitHub source, the frontend/Vercel environment, a `NEXT_PUBLIC_` variable, screenshots, or a chat message. Add only the provider you plan to use first; you do not need all six.

| Render environment-variable name | Official place to create/get it | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio: https://aistudio.google.com/app/apikey | Create/manage a Gemini API key. Google now recommends restricting keys to the Gemini API; review Google's key-type migration notes before production use: https://ai.google.dev/gemini-api/docs/api-key |
| `GROQ_API_KEY` | GroqCloud API Keys: https://console.groq.com/keys | Create a project API key. Check the account's current model access and rate limits: https://console.groq.com/docs/quickstart |
| `CEREBRAS_API_KEY` | Cerebras Cloud: https://cloud.cerebras.ai/ | Sign in and create an inference API key in the console. Confirm model access and account credits/limits: https://github.com/Cerebras/cerebras-cloud-sdk-python |
| `OPENROUTER_API_KEY` | OpenRouter keys: https://openrouter.ai/settings/keys | Check the model's actual cost and set a hard key spend limit if available. A “free” model label is not a guarantee of unlimited quota: https://openrouter.ai/docs/api/api-reference/api-keys/create-keys |
| `HUGGINGFACE_API_KEY` | Hugging Face token settings: https://huggingface.co/settings/tokens | Create a fine-grained token with **Make calls to Inference Providers** permission: https://huggingface.co/docs/inference-providers/en/index |
| `OPENAI_API_KEY` | OpenAI API keys: https://platform.openai.com/api-keys | Create a server-side API key and check API billing and project limits first: https://developers.openai.com/api/docs/quickstart |

## Keep these LEXA safety settings disabled during integration

Set or preserve these values in the Render API service environment:

```dotenv
LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=false
LEXA_AI_ALLOWED_PROVIDERS=
LEXA_AI_ALLOWED_MODELS=
LEXA_AI_PAID_PROVIDERS_ENABLED=false
LEXA_AI_AGGREGATES_EXTERNAL_ENABLED=false
LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED=false
```

Leave `LEXA_AI_MODEL_REGISTRY_JSON` empty unless/until an administrator has reviewed the exact provider/model IDs, pricing, data handling, and permissions. The same is true of any allowlist. A provider key by itself does not authorize routing. Do not enable external execution merely to test the build; the public assistant remains closed until trusted input classification/redaction and full CI/privacy review are complete.

For Render: open the LEXA API web service → **Environment** → **Add Environment Variable**, enter the exact name and the secret value, then save. Do not paste the secret into GitHub. If a key was ever committed or shared publicly, revoke it at the provider and create a replacement.
