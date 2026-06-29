import asyncio
import httpx
import os
from dotenv import load_dotenv

# Load env
load_dotenv("backend/.env")

VAULT_API_BASE_URL = os.getenv("VAULT_API_BASE_URL")
VAULT_EMAIL = os.getenv("VAULT_EMAIL")
VAULT_PASSWORD = os.getenv("VAULT_PASSWORD")
RESOURCE_ID = "6a424076f3d9416dab1866a4"

async def main():
    print(f"Connecting to: {VAULT_API_BASE_URL}")
    print(f"Using email: {VAULT_EMAIL}")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # 1. Login
        login_url = f"{VAULT_API_BASE_URL.rstrip('/')}/auth/login"
        payload = {"email": VAULT_EMAIL, "password": VAULT_PASSWORD}
        resp = await client.post(login_url, json=payload)
        print("Login Status:", resp.status_code)
        data = resp.json()
        
        token = None
        if isinstance(data, dict):
            token = (
                data.get("token")
                or data.get("access_token")
                or (data.get("data", {}) or {}).get("token")
                or (data.get("data", {}) or {}).get("access_token")
            )
        if not token:
            token = data if isinstance(data, str) else None
            
        if not token:
            print("Failed to get token. Response body:")
            print(data)
            return
            
        print("Got token:", token[:10] + "..." if token else "None")
        
        # Headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 2. Get Resource Details
        detail_url = f"{VAULT_API_BASE_URL.rstrip('/')}/vault_resources/{RESOURCE_ID}"
        print(f"GET {detail_url}")
        resp = await client.get(detail_url, headers=headers)
        print("Detail Status:", resp.status_code)
        try:
            print("Detail Data:", resp.json())
        except Exception:
            print("Detail Data (text):", resp.text[:500])
            
        # 3. Try download URL
        download_url = f"{VAULT_API_BASE_URL.rstrip('/')}/vault_resources/{RESOURCE_ID}/download"
        print(f"GET {download_url}")
        resp = await client.get(download_url, headers=headers)
        print("Download endpoint Status:", resp.status_code)
        try:
            resp_json = resp.json()
            print("Download endpoint Data:", resp_json)
        except Exception:
            resp_json = None
            print("Download endpoint Data (text):", resp.text[:500])

        if resp.status_code == 400 and resp_json and resp_json.get("error", {}).get("code") == "INVALID_OPERATION":
            print("Detected pending upload status. Trying to update upload_status to 'completed'...")
            status_url = f"{VAULT_API_BASE_URL.rstrip('/')}/vault_resources/{RESOURCE_ID}/upload_status"
            status_payload = {"upload_status": "completed"}
            status_resp = await client.post(status_url, json=status_payload, headers=headers)
            print("Status Update Response code:", status_resp.status_code)
            print("Status Update Response body:", status_resp.json())
            
            print("Retrying download...")
            resp = await client.get(download_url, headers=headers)
            print("Retried Download Status:", resp.status_code)
            if resp.status_code == 200:
                print("Download retried successfully! Got", len(resp.content), "bytes.")
            else:
                try:
                    print("Retried Download response:", resp.json())
                except Exception:
                    print("Retried Download response text:", resp.text[:500])


        # 4. Try download URL with trailing slash
        download_url_slash = f"{VAULT_API_BASE_URL.rstrip('/')}/vault_resources/{RESOURCE_ID}/download/"
        print(f"GET {download_url_slash}")
        resp = await client.get(download_url_slash, headers=headers)
        print("Download endpoint Status (with slash):", resp.status_code)
        try:
            print("Download endpoint Data (with slash):", resp.json())
        except Exception:
            print("Download endpoint Data (text with slash):", resp.text[:500])

        # 5. Try download URL WITHOUT Content-Type header
        headers_no_ct = {
            "Authorization": f"Bearer {token}"
        }
        print(f"GET {download_url} (no Content-Type)")
        resp = await client.get(download_url, headers=headers_no_ct)
        print("Download endpoint Status (no Content-Type):", resp.status_code)
        try:
            print("Download endpoint Data (no Content-Type):", resp.json())
        except Exception:
            print("Download endpoint (no Content-Type) text:", resp.text[:500])

if __name__ == "__main__":
    asyncio.run(main())
