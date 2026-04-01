import { Clock, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { UploadFile, UploadFileStatus } from "@/types/receipt";

interface UploadProgressProps {
  files: UploadFile[];
}

const statusConfig: Record<
  UploadFileStatus,
  { icon: typeof Clock; color: string; barColor: string; label: string }
> = {
  pending: {
    icon: Clock,
    color: "text-muted-foreground",
    barColor: "bg-muted-foreground/40",
    label: "Pending",
  },
  uploading: {
    icon: Loader2,
    color: "text-blue-500",
    barColor: "bg-blue-500",
    label: "Uploading",
  },
  success: {
    icon: CheckCircle2,
    color: "text-green-600",
    barColor: "bg-green-600",
    label: "Uploaded",
  },
  failed: {
    icon: XCircle,
    color: "text-destructive",
    barColor: "bg-destructive",
    label: "Failed",
  },
};

function formatFileSize(bytes: number): string {
  if (bytes >= 1_000_000) {
    return `${(bytes / 1_000_000).toFixed(1)} MB`;
  }
  return `${Math.round(bytes / 1_000)} KB`;
}

function truncateFilename(name: string, maxLength = 30): string {
  if (name.length <= maxLength) return name;

  const ext = name.lastIndexOf(".");
  if (ext === -1) return name.slice(0, maxLength - 3) + "...";

  const extension = name.slice(ext);
  const stem = name.slice(0, ext);
  const available = maxLength - extension.length - 3;
  if (available <= 0) return name.slice(0, maxLength - 3) + "...";

  return stem.slice(0, available) + "..." + extension;
}

export default function UploadProgress({ files }: UploadProgressProps) {
  if (files.length === 0) return null;

  return (
    <ul className="space-y-3" aria-label="Upload progress">
      {files.map((uploadFile, index) => {
        const config = statusConfig[uploadFile.status];
        const Icon = config.icon;

        return (
          <li
            key={`${uploadFile.file.name}-${index}`}
            className="bg-card rounded-lg border p-3"
          >
            <div className="flex items-center gap-3">
              <Icon
                className={cn(
                  "size-5 shrink-0",
                  config.color,
                  uploadFile.status === "uploading" && "animate-spin",
                )}
                aria-hidden="true"
              />

              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className="truncate text-sm font-medium"
                    title={uploadFile.file.name}
                  >
                    {truncateFilename(uploadFile.file.name)}
                  </span>
                  <span className="text-muted-foreground shrink-0 text-xs">
                    {formatFileSize(uploadFile.file.size)}
                  </span>
                </div>

                {/* Progress bar */}
                <div
                  className="bg-muted mt-1.5 h-1.5 w-full overflow-hidden rounded-full"
                  role="progressbar"
                  aria-valuenow={uploadFile.progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${uploadFile.file.name}: ${config.label} ${uploadFile.progress}%`}
                >
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-300",
                      config.barColor,
                    )}
                    style={{ width: `${uploadFile.progress}%` }}
                  />
                </div>

                {/* Error message */}
                {uploadFile.status === "failed" && uploadFile.error && (
                  <p className="text-destructive mt-1 text-xs">
                    {uploadFile.error}
                  </p>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
