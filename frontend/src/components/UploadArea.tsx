import { useCallback, useRef, useState } from "react";
import { Camera, Upload, ImagePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png"]);

interface UploadAreaProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  maxFiles?: number;
  currentFileCount?: number;
}

function validateFiles(
  files: File[],
  maxFiles: number,
  currentFileCount: number,
): { valid: File[]; errors: string[] } {
  const errors: string[] = [];
  const valid: File[] = [];
  const remaining = maxFiles - currentFileCount;

  if (files.length > remaining) {
    errors.push(
      `You can only upload ${remaining} more file${remaining === 1 ? "" : "s"} (limit: ${maxFiles}).`,
    );
    return { valid, errors };
  }

  for (const file of files) {
    if (!ACCEPTED_TYPES.has(file.type)) {
      errors.push(`"${file.name}" is not a JPEG or PNG image.`);
      continue;
    }
    if (file.size > MAX_FILE_SIZE) {
      errors.push(`"${file.name}" exceeds the 10 MB size limit.`);
      continue;
    }
    valid.push(file);
  }

  return { valid, errors };
}

export default function UploadArea({
  onFilesSelected,
  disabled = false,
  maxFiles = 10,
  currentFileCount = 0,
}: UploadAreaProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;

      const files = Array.from(fileList);
      const { valid, errors } = validateFiles(files, maxFiles, currentFileCount);
      setValidationErrors(errors);

      if (valid.length > 0) {
        onFilesSelected(valid);
      }
    },
    [maxFiles, currentFileCount, onFilesSelected],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) {
        setIsDragOver(true);
      }
    },
    [disabled],
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
    },
    [],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      if (disabled) return;
      handleFiles(e.dataTransfer.files);
    },
    [disabled, handleFiles],
  );

  return (
    <div className="space-y-4">
      {/* Drag-and-drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "flex flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed p-8 transition-colors",
          isDragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 bg-muted/50",
          disabled && "pointer-events-none opacity-50",
        )}
      >
        <ImagePlus
          className={cn(
            "size-10",
            isDragOver ? "text-primary" : "text-muted-foreground",
          )}
          aria-hidden="true"
        />

        <div className="text-center">
          <p className="text-sm font-medium">
            Drag and drop receipt images here
          </p>
          <p className="text-muted-foreground text-xs">
            JPEG or PNG, up to 10 MB each (max {maxFiles} files)
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          {/* Camera capture -- prominent on mobile */}
          <Button
            type="button"
            disabled={disabled}
            onClick={() => cameraInputRef.current?.click()}
            className="md:hidden"
          >
            <Camera className="size-4" />
            Take Photo
          </Button>

          {/* File picker */}
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="size-4" />
            Choose Files
          </Button>
        </div>
      </div>

      {/* Hidden file inputs */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        className="hidden"
        disabled={disabled}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png"
        multiple
        className="hidden"
        disabled={disabled}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <ul
          role="alert"
          className="space-y-1 rounded-md border border-destructive/50 bg-destructive/10 p-3"
        >
          {validationErrors.map((error) => (
            <li key={error} className="text-destructive text-sm">
              {error}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
