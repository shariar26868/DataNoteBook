"use server";

import { cookies } from "next/headers";

async function getCookieHeader(): Promise<Record<string, string>> {
  try {
    const cookieStore = await cookies();
    const cookieHeader = cookieStore.toString();
    return cookieHeader ? { Cookie: cookieHeader } : {};
  } catch {
    return {};
  }
}

export async function fetchStorageLocationsAction(token: string | null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const res = await fetch("https://qual-be.hcloud.q2labs.ai/storage_locations/?minimal=true", {
      headers: {
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...cookieHeaders,
      },
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch storage locations: ${res.statusText}`);
    }
    const data = await res.json();
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function createProjectAction(name: string, storageLocation: string, token: string | null = null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const res = await fetch("http://127.0.0.1:8000/api/project", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...cookieHeaders,
      },
      body: JSON.stringify({
        name,
        storage_location: storageLocation,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.message || "Failed to create project");
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function createFolderAction(name: string, projectId: string, token: string | null = null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const res = await fetch("http://127.0.0.1:8000/api/folder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...cookieHeaders,
      },
      body: JSON.stringify({
        name,
        project_id: projectId,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.message || "Failed to create folder");
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function registerFileAction(payload: any, token: string | null = null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const res = await fetch("http://127.0.0.1:8000/api/file", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...cookieHeaders,
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      const errorDetail = data?.detail;
      let errorMsg = data?.message;
      if (!errorMsg && errorDetail) {
        if (Array.isArray(errorDetail)) {
          errorMsg = errorDetail.map((err: any) => `${err.loc ? err.loc.join('.') : 'field'}: ${err.msg || 'error'}`).join(', ');
        } else {
          errorMsg = typeof errorDetail === 'object' ? JSON.stringify(errorDetail) : String(errorDetail);
        }
      }
      if (!errorMsg) {
        errorMsg = typeof data === 'object' ? JSON.stringify(data) : String(data);
      }
      throw new Error(errorMsg || "Failed to register file");
    }
    return { success: true, data };
  } catch (err: any) {
    console.error("registerFileAction error:", err);
    return { success: false, error: err.message };
  }
}

export async function confirmFileUploadAction(fileId: string, payload: any = {}, token: string | null = null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const res = await fetch(`http://127.0.0.1:8000/api/file/${fileId}/upload_status`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...cookieHeaders,
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      const errorDetail = data?.detail;
      let errorMsg = data?.message;
      if (!errorMsg && errorDetail) {
        if (Array.isArray(errorDetail)) {
          errorMsg = errorDetail.map((err: any) => `${err.loc ? err.loc.join('.') : 'field'}: ${err.msg || 'error'}`).join(', ');
        } else {
          errorMsg = typeof errorDetail === 'object' ? JSON.stringify(errorDetail) : String(errorDetail);
        }
      }
      if (!errorMsg) {
        errorMsg = typeof data === 'object' ? JSON.stringify(data) : String(data);
      }
      throw new Error(errorMsg || "Failed to confirm file upload");
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function analyzeFileAction(fileId: string, token: string | null = null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const res = await fetch(`http://127.0.0.1:8000/api/file/${fileId}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {}), 
        ...cookieHeaders,
      },
    });
    
    // Propagate backend session cookie to client browser
    const setCookie = res.headers.get("set-cookie");
    if (setCookie) {
      const match = setCookie.match(/session_id=([^;]+)/);
      if (match) {
        const sessionId = match[1];
        try {
          const cookieStore = await cookies();
          cookieStore.set("session_id", sessionId, {
            httpOnly: true,
            sameSite: "lax",
            path: "/",
          });
        } catch (cookieErr) {
          console.error("Failed to set session_id cookie in Next.js store:", cookieErr);
        }
      }
    }

    const data = await res.json();
    console.log('Analyze response status:', res.status);
    console.log('Analyze response data:', data);
    if (!res.ok) {
      const errorDetail = data?.detail;
      let errorMsg = data?.message;
      if (!errorMsg && errorDetail) {
        if (Array.isArray(errorDetail)) {
          errorMsg = errorDetail.map((err: any) => `${err.loc ? err.loc.join('.') : 'field'}: ${err.msg || 'error'}`).join(', ');
        } else {
          errorMsg = typeof errorDetail === 'object' ? JSON.stringify(errorDetail) : String(errorDetail);
        }
      }
      if (!errorMsg) {
        errorMsg = typeof data === 'object' ? JSON.stringify(data) : String(data);
      }
      throw new Error(errorMsg || "Failed to analyze file");
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function fetchProjectsAction(token: string | null = null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const res = await fetch("http://127.0.0.1:8000/api/project", {
      headers: {
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...cookieHeaders,
      },
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.message || "Failed to fetch projects");
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function fetchProjectResourcesAction(projectId: string, parentId: string | null = null, token: string | null = null) {
  try {
    const cookieHeaders = await getCookieHeader();
    const query = parentId ? `?parent_id=${parentId}` : "";
    const res = await fetch(`http://127.0.0.1:8000/api/project/${projectId}/resources${query}`, {
      headers: {
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...cookieHeaders,
      },
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.message || "Failed to fetch project resources");
    }
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}
