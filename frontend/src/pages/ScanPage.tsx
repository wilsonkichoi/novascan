import UploadArea from "@/components/UploadArea";
import UploadProgress from "@/components/UploadProgress";
import UploadSummary from "@/components/UploadSummary";
import { useUpload } from "@/hooks/useUpload";

export default function ScanPage() {
  const { files, phase, startUpload, retry, reset } = useUpload();

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-4">
      <h1 className="text-2xl font-bold tracking-tight">Scan Receipts</h1>

      {phase === "idle" && (
        <UploadArea onFilesSelected={startUpload} />
      )}

      {phase === "uploading" && (
        <UploadProgress files={files} />
      )}

      {phase === "complete" && (
        <>
          <UploadProgress files={files} />
          <UploadSummary files={files} onRetry={retry} onUploadMore={reset} />
        </>
      )}
    </main>
  );
}
