import { registerFileAction, confirmFileUploadAction } from "@/lib/actions/project.action";

const axiosInstance = {
  get: async (url: string) => {
    const res = await fetch(url);
    const data = await res.json();
    return { data };
  },
  post: async (url: string, body: any, config: any = {}) => {
    const res = await fetch(url, {
      method: "POST",
      headers: config.headers || {},
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return { data };
  }
};

interface PresignedUrlPayload {
  file_name: string;
  content_type?: string;
}

// Add progress callback type
export type ProgressCallback = (progress: number) => void;

export const generatePresignedUrl = async (payload: PresignedUrlPayload) => {
  try {
    const response = await axiosInstance.post(`/files/presigned-url`, payload, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  } catch (error: any) {
    return error?.response?.data || { success: false, error };
  }
};

// Enhanced upload function with progress tracking
export const uploadFileToPresignedUrlWithProgress = async (
  presignedUrl: string, 
  file: File, 
  onProgress?: ProgressCallback
) => {
    console.log(presignedUrl,file,onProgress,'onprogress')
  try {
    const CHUNK_SIZE = 4 * 1024 * 1024; // 4MB chunks for large files
    
    // For small files (< 100MB), use simple upload with progress
    if (file.size < 100 * 1024 * 1024) {
      return await uploadSmallFileWithProgress(presignedUrl, file, onProgress);
    }
    
    // For large files, use chunked upload
    return await uploadLargeFileInChunks(presignedUrl, file, CHUNK_SIZE, onProgress);
  } catch (error) {
    return { success: false, error };
  }
};

// Simple upload with progress for smaller files
const uploadSmallFileWithProgress = async (
  presignedUrl: string,
  file: File,
  onProgress?: ProgressCallback
) => {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        const percentComplete = (event.loaded / event.total) * 100;
        onProgress(percentComplete);
      }
    });
    
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({ success: true });
      } else {
        resolve({ success: false, error: `Upload failed with status: ${xhr.status}` });
      }
    });
    
    xhr.addEventListener('error', () => {
      resolve({ success: false, error: 'Upload failed' });
    });
    
    xhr.open('PUT', presignedUrl);
    xhr.setRequestHeader('x-ms-blob-type', 'BlockBlob');
    xhr.setRequestHeader('Content-Type', file.type);
    xhr.send(file);
  });
};

// Chunked upload for large files
const uploadLargeFileInChunks = async (
  presignedUrl: string,
  file: File,
  chunkSize: number,
  onProgress?: ProgressCallback
) => {
  const totalChunks = Math.ceil(file.size / chunkSize);
  let uploadedBytes = 0;
  
  // Generate block IDs for Azure Blob Storage
  const blockIds: string[] = [];
  
  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize;
    const end = Math.min(start + chunkSize, file.size);
    const chunk = file.slice(start, end);
    
    // Create block ID (must be base64 encoded and same length)
    const blockId = btoa(String(i).padStart(6, '0'));
    blockIds.push(blockId);
    
    // Upload chunk
    const chunkUrl = `${presignedUrl}&comp=block&blockid=${encodeURIComponent(blockId)}`;
    
    try {
      const response = await fetch(chunkUrl, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/octet-stream',
        },
        body: chunk,
      });
      
      if (!response.ok) {
        throw new Error(`Chunk ${i} upload failed with status: ${response.status}`);
      }
      
      uploadedBytes += chunk.size;
      
      if (onProgress) {
        const percentComplete = (uploadedBytes / file.size) * 100;
        onProgress(percentComplete);
      }
    } catch (error) {
      return { success: false, error: `Failed to upload chunk ${i}: ${error}` };
    }
  }
  
  // Commit the blocks
  const commitUrl = `${presignedUrl}&comp=blocklist`;
  const blockListXml = `<?xml version="1.0" encoding="utf-8"?>
    <BlockList>
      ${blockIds.map(id => `<Latest>${id}</Latest>`).join('')}
    </BlockList>`;
  
  try {
    const commitResponse = await fetch(commitUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/xml',
      },
      body: blockListXml,
    });
    
    if (!commitResponse.ok) {
      throw new Error(`Failed to commit blocks with status: ${commitResponse.status}`);
    }
    
    return { success: true };
  } catch (error) {
    return { success: false, error: `Failed to commit blocks: ${error}` };
  }
};

// Keep the original function for backward compatibility
export const uploadFileToPresignedUrl = async (presignedUrl: string, file: File) => {
  return await uploadFileToPresignedUrlWithProgress(presignedUrl, file);
};

const downloadFileFromPresignedUrl = async (url=null, filename='') => {
  if (!url) {
    console.error('No presigned URL provided for download');
    return;
  }
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`File download failed with status: ${response.status}`);
    }
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename || ''; // Let the server suggest the filename
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
    return { success: true };
  } catch (error) {
    console.error('Error downloading file:', error);
  }
}

export const downloadFileById = async (fileId: string) => {
  try {
    const response = await axiosInstance.get(`/vault_resources/${fileId}/download`);
    if (!response.data.success) {
      console.error('Failed to get presigned download URL');
      return response.data;
    }
    return await downloadFileFromPresignedUrl(response?.data?.data?.presigned_url, response?.data?.data?.blob_name.split('/').pop());
  } catch (error: any) {
    return error?.response?.data || { success: false, error };
  }
}

export const getFileUrlById = async (fileId: string) => {
  try {
    const response = await axiosInstance.get(`/files/${fileId}/presigned-download`);
    return response.data;
  } catch (error: any) {
    return error?.response?.data || { success: false, error };
  }
};

export const confirmUpload = async (fileId: string, payload: any = {}) => {
  try {
    const response = await axiosInstance.post(`/vault_resources/${fileId}/upload_status`, payload);
    return response.data;
  } catch (error: any) {
    return error?.response?.data || { success: false, error };
  }
};

export const uploadFile = async (file: File) => {
  try {
    // generate presigned URL
    const presignedUrlResponse = await generatePresignedUrl({
      file_name: file.name,
      content_type: file.type
    });

    if (!presignedUrlResponse.success) {
      console.error('Failed to generate presigned URL');
      return presignedUrlResponse;
    }

    const loc = presignedUrlResponse.data.pre_signed_url;
    const file_id = presignedUrlResponse.data.file_id;

    const fileUploadResponse: any = await uploadFileToPresignedUrl(loc, file);
    if (!fileUploadResponse?.success) {
      console.error('Failed to upload file');
      return fileUploadResponse;
    }

    // confirm upload
    const confirmUploadResponse = await confirmUpload(file_id);
    if (!confirmUploadResponse?.success) {
      console.error('Failed to confirm file upload');
      return confirmUploadResponse;
    }

    console.log('File uploaded successfully');
    return confirmUploadResponse;
  } catch (error) {
    return { success: false, error };
  }
};

export const uploadFileToApi = async (file: File, projectId: string, folderId: string, token?: string | null) => {
  try {
    const dotIdx = file.name.lastIndexOf('.');
    const ext = dotIdx !== -1 ? file.name.substring(dotIdx) : ".csv";
    const payload = {
      name: file.name,
      type: "file",
      size: file.size,
      extension: ext,
      mime_type: file.type || "text/csv",
      project_id: projectId,
      parent_folder_id: folderId,
    };
    console.log("Registering file with payload:", payload);
    const result = await registerFileAction(payload, token);
    if (!result.success) {
      console.error("File registration failed:", result.error);
      throw new Error(result.error || "Failed to register file");
    }
    if (!result.data || !result.data.success) {
      console.error("File registration failed on server:", result.data);
      throw new Error(result.data?.message || "Failed to register file on server");
    }
    console.log("File registered successfully. Response:", result.data);

    const presignedUrl = result.data.data.presigned_url;
    const fileId = result.data.data.id;
    console.log(`Uploading file content to presigned URL: ${presignedUrl}`);
    const uploadRes: any = await uploadFileToPresignedUrl(presignedUrl, file);
    if (!uploadRes?.success) {
      console.error("Upload to storage failed:", uploadRes?.error);
      throw new Error(uploadRes?.error || "Failed to upload file to storage");
    }
    console.log("File uploaded successfully to storage.");

    console.log(`Confirming file upload status for ID: ${fileId}`);
    const confirmRes = await confirmFileUploadAction(fileId, {
      upload_status: "completed"
    }, token);
    if (!confirmRes.success) {
      console.error("Confirming upload status failed:", confirmRes.error);
      throw new Error(confirmRes.error || "Failed to confirm file upload status");
    }
    console.log("Upload status confirmed. Response:", confirmRes.data);

    return { success: true, data: confirmRes.data.data || result.data.data };
  } catch (error: any) {
    console.error("Error during file upload flow:", error);
    return { success: false, error: error.message || error };
  }
};
