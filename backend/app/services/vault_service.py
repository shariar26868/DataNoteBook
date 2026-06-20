"""
Azure Vault API client for DataNotebook.
Replaces AWS S3 with client's vault-managed Azure Blob Storage.

Flow: Login → Create Project → Create Folder → Create File → PUT to Azure presigned URL
"""

import httpx
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class VaultClient:
    """Singleton client for the Azure Vault API."""

    def __init__(self):
        self._token: Optional[str] = None
        self._base_url = settings.VAULT_API_BASE_URL.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)

    @property
    def _headers(self) -> dict:
        """Auth headers with Bearer token."""
        if not self._token:
            raise RuntimeError("VaultClient not authenticated. Call login() first.")
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def login(self) -> str:
        """
        Authenticate with the Vault API.
        Returns the Bearer token and caches it.
        """
        url = f"{self._base_url}/auth/login"
        payload = {
            "email": settings.VAULT_EMAIL,
            "password": settings.VAULT_PASSWORD,
        }
        logger.info(f"[Vault] Logging in as {settings.VAULT_EMAIL}...")

        resp = await self._client.post(url, json=payload)
        if resp.status_code != 200:
            logger.error(f"[Vault] Login failed ({resp.status_code}): {resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()

        # Try common token field locations
        if isinstance(data, dict):
            token = (
                data.get("token")
                or data.get("access_token")
                or (data.get("data", {}) or {}).get("token")
                or (data.get("data", {}) or {}).get("access_token")
            )
        else:
            token = None

        if not token:
            # If token is returned as a plain string
            if isinstance(data, str):
                token = data
            else:
                raise ValueError(f"Could not extract token from login response: {data}")

        self._token = token
        logger.info("[Vault] Login successful.")
        return token

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        """Make an authenticated request, auto-login if no token, auto-retry on 401."""
        # Auto-login if not authenticated yet
        if not self._token:
            logger.info("[Vault] No token found, logging in...")
            await self.login()

        resp = await self._client.request(method, url, headers=self._headers, **kwargs)

        # Auto re-login on 401
        if resp.status_code == 401:
            logger.warning("[Vault] Token expired, re-authenticating...")
            await self.login()
            resp = await self._client.request(method, url, headers=self._headers, **kwargs)

        resp.raise_for_status()
        return resp.json()

    async def create_project(self, name: str, storage_location: str = None) -> dict:
        """
        Create a new project in the vault.
        Returns the full project data including 'id' and 'storage_location'.
        """
        url = f"{self._base_url}/projects/"
        payload = {
            "name": name,
            "storage_location": storage_location or settings.VAULT_STORAGE_LOCATION,
        }
        logger.info(f"[Vault] Creating project: {name}")
        result = await self._request("POST", url, json=payload)
        project_data = result.get("data", result)
        logger.info(f"[Vault] Project created: {project_data.get('id')}")
        return project_data

    async def create_folder(self, name: str, project_id: str) -> dict:
        """
        Create a folder under a project.
        Returns the full folder data including 'id'.
        """
        url = f"{self._base_url}/vault_resources/"
        payload = {
            "name": name,
            "type": "folder",
            "project": project_id,
        }
        logger.info(f"[Vault] Creating folder: {name} (project={project_id})")
        result = await self._request("POST", url, json=payload)
        folder_data = result.get("data", result)
        logger.info(f"[Vault] Folder created: {folder_data.get('id')}")
        return folder_data

    async def create_file(
        self,
        name: str,
        size: int,
        extension: str,
        mime_type: str,
        project_id: str,
        parent_folder_id: str,
    ) -> dict:
        """
        Register a file in the vault (under a folder).
        Returns file data including 'presigned_url', 'blob_name', and 'id'.
        """
        url = f"{self._base_url}/vault_resources/"
        payload = {
            "name": name,
            "type": "file",
            "size": size,
            "extension": extension,
            "mime_type": mime_type,
            "project": project_id,
            "parent": parent_folder_id,
        }
        logger.info(f"[Vault] Creating file entry: {name} (folder={parent_folder_id})")
        result = await self._request("POST", url, json=payload)
        file_data = result.get("data", result)
        logger.info(f"[Vault] File registered: {file_data.get('id')} → blob={file_data.get('blob_name')}")
        return file_data

    async def upload_to_azure(
        self,
        presigned_url: str,
        file_bytes: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """
        Upload raw bytes to Azure Blob Storage using the presigned (SAS) URL.
        Uses PUT with x-ms-blob-type header as required by Azure.
        """
        headers = {
            "x-ms-blob-type": "BlockBlob",
            "Content-Type": content_type,
        }
        logger.info(f"[Vault] Uploading {len(file_bytes)} bytes to Azure...")
        resp = await self._client.put(presigned_url, content=file_bytes, headers=headers)
        resp.raise_for_status()
        logger.info("[Vault] Azure upload complete.")

    async def upload_file_complete(
        self,
        filename: str,
        file_bytes: bytes,
        project_id: str,
        folder_id: str,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """
        Full upload flow:
        1. Create file entry in vault → get presigned_url
        2. PUT bytes to Azure

        Returns the file data dict from the vault API.
        """
        import os

        name = os.path.basename(filename)
        ext = os.path.splitext(name)[1].lstrip(".") if "." in name else ""
        size = len(file_bytes)

        # Create file entry in vault
        file_data = await self.create_file(
            name=name,
            size=size,
            extension=ext,
            mime_type=content_type,
            project_id=project_id,
            parent_folder_id=folder_id,
        )

        # Upload actual bytes to Azure
        presigned_url = file_data.get("presigned_url")
        if presigned_url:
            await self.upload_to_azure(presigned_url, file_bytes, content_type)
        else:
            logger.warning("[Vault] No presigned_url in file response — skipping Azure upload")

        return file_data

    # --- New Notebook Migration Methods ---

    async def list_resources(self, parent_id: Optional[str] = None, project_id: Optional[str] = None, limit: int = 1000) -> list:
        """
        Get List of Vault Resources.
        """
        url = f"{self._base_url}/vault_resources/"
        params = {"limit": limit}
        if parent_id:
            params["parent"] = parent_id
        if project_id:
            params["project"] = project_id
        
        logger.info(f"[Vault] Listing resources for parent={parent_id} project={project_id} (limit={limit})")
        result = await self._request("GET", url, params=params)
        return result.get("data", [])

    async def list_projects(self, limit: int = 1000) -> list:
        """
        List all projects in the vault.
        """
        url = f"{self._base_url}/projects/"
        logger.info(f"[Vault] Listing projects (limit={limit})")
        result = await self._request("GET", url, params={"limit": limit})
        return result.get("data", result)

    async def get_resource(self, resource_id: str) -> dict:
        """
        Get Detail of a Vault Resource.
        Assuming endpoint: GET /vault_resources/{id}
        """
        url = f"{self._base_url}/vault_resources/{resource_id}"
        logger.info(f"[Vault] Fetching resource detail for id={resource_id}")
        result = await self._request("GET", url)
        return result.get("data", result)

    async def download_resource(self, resource_id: str) -> bytes:
        """
        Download a Vault Resource.
        Assuming endpoint: GET /vault_resources/{id}/download
        Which returns a presigned URL in data -> download_url
        """
        url = f"{self._base_url}/vault_resources/{resource_id}/download"
        logger.info(f"[Vault] Getting download URL for resource_id={resource_id}")
        result = await self._request("GET", url)
        data = result.get("data", result)
        download_url = data.get("download_url") or data.get("url") or data.get("presigned_url")

        if not download_url:
            raise ValueError(f"Could not find download URL in response: {data}")

        # Fetch the actual bytes
        resp = await self._client.get(download_url)
        resp.raise_for_status()
        return resp.content

    async def delete_resource(self, resource_id: str) -> dict:
        """
        Delete a Vault Resource.
        Assuming endpoint: DELETE /vault_resources/{id}
        """
        url = f"{self._base_url}/vault_resources/{resource_id}"
        logger.info(f"[Vault] Deleting resource id={resource_id}")
        result = await self._request("DELETE", url)
        return result.get("data", result)

    async def rename_resource(self, resource_id: str, new_name: str) -> dict:
        """
        Rename a Vault Resource using POST Move.
        Assuming endpoint: POST /vault_resources/{id}/move
        """
        url = f"{self._base_url}/vault_resources/{resource_id}/move"
        payload = {"name": new_name}
        logger.info(f"[Vault] Renaming resource id={resource_id} to '{new_name}'")
        result = await self._request("POST", url, json=payload)
        return result.get("data", result)

    async def update_upload_status(self, resource_id: str, payload: dict) -> dict:
        """
        Confirm file upload status in Vault.
        """
        url = f"{self._base_url}/vault_resources/{resource_id}/upload_status"
        logger.info(f"[Vault] Updating upload status for id={resource_id}")
        result = await self._request("POST", url, json=payload)
        return result.get("data", result)

    async def setup_global_notebooks_storage(self) -> tuple[str, str]:
        """
        Create or retrieve a global project + folder for notebooks.
        Returns (project_id, folder_id).
        """
        if not self._token:
            await self.login()

        # Check if project already exists
        projects = await self.list_projects()
        project_id = None
        for p in projects:
            if p.get("name") == "DataNotebook - Global":
                project_id = p.get("id")
                break

        if not project_id:
            try:
                project_data = await self.create_project(name="DataNotebook - Global")
                project_id = project_data["id"]
            except httpx.HTTPStatusError as e:
                # Fallback / retry in case of a race condition
                if e.response.status_code == 400 and "ALREADY_EXISTS" in e.response.text:
                    projects = await self.list_projects()
                    for p in projects:
                        if p.get("name") == "DataNotebook - Global":
                            project_id = p.get("id")
                            break
                if not project_id:
                    raise

        # Check if folder already exists in the project
        resources = await self.list_resources(project_id=project_id)
        folder_id = None
        for r in resources:
            if r.get("type") == "folder" and r.get("name") == "notebooks":
                folder_id = r.get("id")
                break

        if not folder_id:
            try:
                folder_data = await self.create_folder(name="notebooks", project_id=project_id)
                folder_id = folder_data["id"]
            except httpx.HTTPStatusError as e:
                # Fallback / retry in case of a race condition
                if e.response.status_code == 400 and "ALREADY_EXISTS" in e.response.text:
                    resources = await self.list_resources(project_id=project_id)
                    for r in resources:
                        if r.get("type") == "folder" and r.get("name") == "notebooks":
                            folder_id = r.get("id")
                            break
                if not folder_id:
                    raise

        return project_id, folder_id

    async def setup_session_storage(self, session_name: str) -> tuple[str, str]:
        """
        Create or retrieve a project + folder for a new notebook session.
        Returns (project_id, folder_id).
        """
        # Ensure we're logged in
        if not self._token:
            await self.login()

        # Check if project already exists
        target_project_name = f"DataNotebook - {session_name}"
        projects = await self.list_projects()
        project_id = None
        for p in projects:
            if p.get("name") == target_project_name:
                project_id = p.get("id")
                break

        if not project_id:
            try:
                project_data = await self.create_project(name=target_project_name)
                project_id = project_data["id"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400 and "ALREADY_EXISTS" in e.response.text:
                    projects = await self.list_projects()
                    for p in projects:
                        if p.get("name") == target_project_name:
                            project_id = p.get("id")
                            break
                if not project_id:
                    raise

        # Check if folder already exists in the project
        resources = await self.list_resources(project_id=project_id)
        folder_id = None
        for r in resources:
            if r.get("type") == "folder" and r.get("name") == session_name:
                folder_id = r.get("id")
                break

        if not folder_id:
            try:
                folder_data = await self.create_folder(name=session_name, project_id=project_id)
                folder_id = folder_data["id"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400 and "ALREADY_EXISTS" in e.response.text:
                    resources = await self.list_resources(project_id=project_id)
                    for r in resources:
                        if r.get("type") == "folder" and r.get("name") == session_name:
                            folder_id = r.get("id")
                            break
                if not folder_id:
                    raise

        return project_id, folder_id

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# ── Module-level singleton ──
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get or create the global VaultClient singleton."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client
