import { Link } from "react-router-dom";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UploadFile } from "@/types/receipt";

interface UploadSummaryProps {
  files: UploadFile[];
  onRetry: (failedFiles: File[]) => void;
  onUploadMore: () => void;
}

export default function UploadSummary({
  files,
  onRetry,
  onUploadMore,
}: UploadSummaryProps) {
  const total = files.length;
  const successCount = files.filter((f) => f.status === "success").length;
  const failedFiles = files.filter((f) => f.status === "failed");
  const allSucceeded = successCount === total;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div
        className={cn(
          "flex items-start gap-3 rounded-lg border p-4",
          allSucceeded
            ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950"
            : "border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950",
        )}
      >
        {allSucceeded ? (
          <CheckCircle2
            className="mt-0.5 size-5 shrink-0 text-green-600"
            aria-hidden="true"
          />
        ) : (
          <AlertTriangle
            className="mt-0.5 size-5 shrink-0 text-yellow-600"
            aria-hidden="true"
          />
        )}
        <div>
          <p className="text-sm font-medium">
            {successCount} of {total} receipt{total === 1 ? "" : "s"} uploaded
          </p>
          {allSucceeded ? (
            <p className="text-muted-foreground mt-0.5 text-sm">
              All receipts uploaded successfully. They will be processed
              shortly.
            </p>
          ) : (
            <p className="text-muted-foreground mt-0.5 text-sm">
              {failedFiles.length} file{failedFiles.length === 1 ? "" : "s"}{" "}
              failed to upload. You can retry the failed uploads.
            </p>
          )}
        </div>
      </div>

      {/* Failed file details */}
      {failedFiles.length > 0 && (
        <ul className="space-y-2" aria-label="Failed uploads">
          {failedFiles.map((uploadFile, index) => (
            <li
              key={`${uploadFile.file.name}-${index}`}
              className="border-destructive/20 bg-destructive/5 flex items-start gap-2 rounded-md border p-3"
            >
              <span className="text-destructive text-sm font-medium">
                {uploadFile.file.name}
              </span>
              {uploadFile.error && (
                <span className="text-destructive/80 text-sm">
                  — {uploadFile.error}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        {failedFiles.length > 0 && (
          <Button
            type="button"
            variant="destructive"
            onClick={() => onRetry(failedFiles.map((f) => f.file))}
          >
            Retry Failed
          </Button>
        )}
        <Button type="button" variant="outline" onClick={onUploadMore}>
          Upload More
        </Button>
        <Button asChild variant="default">
          <Link to="/receipts">View Receipts</Link>
        </Button>
      </div>
    </div>
  );
}
