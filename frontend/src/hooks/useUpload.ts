import { useCallback, useRef, useState } from "react";
import type { UploadFile } from "@/types/receipt";
import {
  requestUploadUrls,
  uploadFileToS3,
  type UploadUrlReceipt,
} from "@/api/receipts";

type UploadPhase = "idle" | "uploading" | "complete";

const MAX_RETRIES = 3;
const BACKOFF_BASE_MS = 1000;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useUpload() {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const urlMapRef = useRef<Map<string, UploadUrlReceipt>>(new Map());
  const filesRef = useRef<UploadFile[]>([]);

  const updateFiles = useCallback((updater: (prev: UploadFile[]) => UploadFile[]) => {
    setFiles((prev) => {
      const next = updater(prev);
      filesRef.current = next;
      return next;
    });
  }, []);

  const updateFile = useCallback(
    (index: number, updates: Partial<UploadFile>) => {
      updateFiles((prev) =>
        prev.map((f, i) => (i === index ? { ...f, ...updates } : f)),
      );
    },
    [updateFiles],
  );

  const uploadSingleFile = useCallback(
    async (file: File, index: number): Promise<void> => {
      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        const key = `${file.name}-${file.size}`;
        let urlInfo = urlMapRef.current.get(key);

        if (!urlInfo) {
          try {
            const [receipt] = await requestUploadUrls([file]);
            urlInfo = receipt;
            urlMapRef.current.set(key, urlInfo);
          } catch (err) {
            if (attempt === MAX_RETRIES) {
              updateFile(index, {
                status: "failed",
                error:
                  err instanceof Error
                    ? err.message
                    : "Failed to get upload URL",
              });
              return;
            }
            await delay(BACKOFF_BASE_MS * 2 ** attempt);
            continue;
          }
        }

        updateFile(index, {
          status: "uploading",
          progress: 0,
          receiptId: urlInfo.receiptId,
        });

        try {
          await uploadFileToS3(urlInfo.uploadUrl, file, (pct) => {
            updateFile(index, { progress: pct });
          });
          updateFile(index, { status: "success", progress: 100 });
          return;
        } catch (err) {
          // If upload failed, the presigned URL may have expired. Clear it so
          // the next attempt fetches a fresh one.
          urlMapRef.current.delete(key);

          if (attempt === MAX_RETRIES) {
            updateFile(index, {
              status: "failed",
              progress: 0,
              error:
                err instanceof Error ? err.message : "Upload failed",
            });
            return;
          }

          await delay(BACKOFF_BASE_MS * 2 ** attempt);
        }
      }
    },
    [updateFile],
  );

  const startUpload = useCallback(
    async (selectedFiles: File[]) => {
      urlMapRef.current.clear();
      setPhase("uploading");

      const initial: UploadFile[] = selectedFiles.map((file) => ({
        file,
        status: "pending" as const,
        progress: 0,
      }));
      updateFiles(() => initial);

      // Request presigned URLs for all files at once
      try {
        const receipts = await requestUploadUrls(selectedFiles);
        for (let i = 0; i < receipts.length; i++) {
          const file = selectedFiles[i];
          const key = `${file.name}-${file.size}`;
          urlMapRef.current.set(key, receipts[i]);
        }
      } catch {
        // Bulk request failed — individual uploads will request their own URLs
      }

      // Upload all files in parallel
      await Promise.all(
        selectedFiles.map((file, index) => uploadSingleFile(file, index)),
      );

      setPhase("complete");
    },
    [uploadSingleFile, updateFiles],
  );

  const retry = useCallback(
    async (failedFiles: File[]) => {
      setPhase("uploading");

      // Reset failed files to pending and find their indices
      const failedSet = new Set(failedFiles);
      updateFiles((prev) =>
        prev.map((f) =>
          failedSet.has(f.file)
            ? { ...f, status: "pending" as const, progress: 0, error: undefined }
            : f,
        ),
      );

      // Read indices from the ref (stable after updateFiles)
      const retryEntries = filesRef.current
        .map((f, index) => ({ file: f.file, index }))
        .filter(({ file }) => failedSet.has(file));

      await Promise.all(
        retryEntries.map(({ file, index }) => uploadSingleFile(file, index)),
      );

      setPhase("complete");
    },
    [uploadSingleFile, updateFiles],
  );

  const reset = useCallback(() => {
    updateFiles(() => []);
    setPhase("idle");
    urlMapRef.current.clear();
  }, [updateFiles]);

  return { files, phase, startUpload, retry, reset };
}
