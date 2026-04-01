/** Status of a file during the upload process */
export type UploadFileStatus = "pending" | "uploading" | "success" | "failed";

/** A file being tracked through the upload flow */
export interface UploadFile {
  file: File;
  status: UploadFileStatus;
  progress: number;
  receiptId?: string;
  error?: string;
}
