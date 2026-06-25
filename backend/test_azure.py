"""
Azure OpenAI Connection Diagnostic Script
Run: python test_azure.py
"""
import asyncio
from openai import AsyncOpenAI

AZURE_OPENAI_ENDPOINT = "https://q2labs-resource.cognitiveservices.azure.com/openai/v1"
AZURE_OPENAI_API_KEY = "4Tjhq25kb2NgfToWccOfUAYzjQGBxoqJFuYls7eeWUtEIIpHPtsFJQQJ99CEAC5T7U2XJ3w3AAAAACOGnPEI"

# Common model/deployment names to try
MODELS_TO_TRY = [
    "gpt-4.5",
    "gpt-4.5-preview",
    "gpt-4.5-preview-2025-02-27",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4",
    "gpt-4-turbo",
]

client = AsyncOpenAI(
    base_url=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
)

async def test_model(model_name: str) -> bool:
    try:
        response = await client.chat.completions.create(
            model=model_name,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hello"}],
        )
        print(f"  SUCCESS  -> model='{model_name}'  | Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        err_str = str(e)
        if "DeploymentNotFound" in err_str or "404" in err_str:
            print(f"  NOT FOUND -> model='{model_name}'")
        elif "401" in err_str or "Unauthorized" in err_str:
            print(f"  AUTH ERROR -> model='{model_name}' -- API key problem")
        elif "429" in err_str:
            print(f"  RATE LIMIT -> model='{model_name}'")
        else:
            print(f"  ERROR -> model='{model_name}' | {err_str[:120]}")
        return False


async def list_models():
    print("\nTrying to list available models...")
    try:
        models = await client.models.list()
        print("  Available models:")
        for m in models.data:
            print(f"    - {m.id}")
    except Exception as e:
        print(f"  Could not list models: {e}")


async def main():
    print("=" * 60)
    print("  Azure OpenAI Diagnostic Tool")
    print(f"  Endpoint: {AZURE_OPENAI_ENDPOINT}")
    print("=" * 60)

    await list_models()

    print("\nTesting model names one by one...\n")
    success = False
    for model in MODELS_TO_TRY:
        ok = await test_model(model)
        if ok:
            success = True
            break

    print("\n" + "=" * 60)
    if not success:
        print("NONE of the common model names worked.")
        print("  -> Check Azure Portal -> your resource -> Model Deployments")
        print("  -> Copy the exact Deployment Name and update OPENAI_MODEL in .env")
    print("=" * 60)


asyncio.run(main())
