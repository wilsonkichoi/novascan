import { getValidIdToken } from "@/lib/auth";

const API_URL = import.meta.env.VITE_API_URL ?? "";

interface UploadUrlRequest {
  files: { fileName: string; contentType: string; fileSize: number }[];
}

interface UploadUrlReceipt {
  receiptId: string;
  uploadUrl: string;
  imageKey: string;
  expiresIn: number;
}

interface UploadUrlResponse {
  receipts: UploadUrlReceipt[];
}

interface ApiError {
  error: { code: string; message: string };
}

export type { UploadUrlReceipt };

export async function requestUploadUrls(
  files: File[],
): Promise<UploadUrlReceipt[]> {
  const token = await getValidIdToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const body: UploadUrlRequest = {
    files: files.map((f) => ({
      fileName: f.name,
      contentType: f.type,
      fileSize: f.size,
    })),
  };

  const res = await fetch(`${API_URL}/api/receipts/upload-urls`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as ApiError | null;
    const message =
      errorBody?.error?.message ?? `Upload URL request failed (${res.status})`;
    throw new Error(message);
  }

  const data = (await res.json()) as UploadUrlResponse;
  return data.receipts;
}

export function uploadFileToS3(
  url: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`S3 upload failed (${xhr.status})`));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Network error during upload"));
    });

    xhr.addEventListener("abort", () => {
      reject(new Error("Upload aborted"));
    });

    xhr.send(file);
  });
}
