import { useState } from "react";
import { Loader2, ToggleLeft, ToggleRight, Trophy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { usePipelineResults } from "@/hooks/useCategories";
import type { PipelineResult } from "@/api/categories";

interface PipelineComparisonProps {
  receiptId: string;
}

const PIPELINE_LABELS: Record<string, string> = {
  "ocr-ai": "OCR + AI",
  "ai-multimodal": "AI Multimodal",
};

function formatConfidence(value: number | null): string {
  if (value == null) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function PipelineComparison({
  receiptId,
}: PipelineComparisonProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data, isLoading, error } = usePipelineResults(receiptId, isExpanded);

  return (
    <div className="rounded-lg border">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-controls="pipeline-comparison-panel"
        className={cn(
          "flex w-full items-center justify-between p-4 text-left text-sm font-semibold",
          "hover:bg-accent/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          "uppercase tracking-wide text-muted-foreground",
        )}
      >
        <span>Pipeline Comparison</span>
        {isExpanded ? (
          <ToggleRight className="size-5 text-primary" />
        ) : (
          <ToggleLeft className="size-5" />
        )}
      </button>

      {isExpanded && (
        <div id="pipeline-comparison-panel" className="border-t px-4 pb-4">
          {isLoading && (
            <div className="flex items-center justify-center py-6" role="status">
              <Loader2 className="text-muted-foreground size-5 animate-spin" />
              <span className="sr-only">Loading pipeline results</span>
            </div>
          )}

          {error && (
            <p className="py-4 text-center text-sm text-destructive">
              Failed to load pipeline results.
            </p>
          )}

          {data && (
            <div className="space-y-4 pt-3">
              {/* Winner badge */}
              {data.rankingWinner && (
                <div className="flex items-center gap-2">
                  <Trophy className="size-4 text-yellow-500" />
                  <span className="text-sm font-medium">
                    Winner:{" "}
                    {PIPELINE_LABELS[data.rankingWinner] ?? data.rankingWinner}
                  </span>
                  {data.usedFallback && (
                    <Badge variant="outline" className="text-xs">
                      Fallback used
                    </Badge>
                  )}
                </div>
              )}

              {/* Side-by-side results */}
              <div className="grid gap-4 sm:grid-cols-2">
                {(["ocr-ai", "ai-multimodal"] as const).map((pipelineType) => {
                  const result = data.results[pipelineType];
                  const isWinner = data.rankingWinner === pipelineType;
                  return (
                    <PipelineCard
                      key={pipelineType}
                      pipelineType={pipelineType}
                      result={result ?? null}
                      isWinner={isWinner}
                    />
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --- Pipeline result card ---

interface PipelineCardProps {
  pipelineType: string;
  result: PipelineResult | null;
  isWinner: boolean;
}

function PipelineCard({ pipelineType, result, isWinner }: PipelineCardProps) {
  const label = PIPELINE_LABELS[pipelineType] ?? pipelineType;

  if (!result) {
    return (
      <div className="rounded-md border border-dashed p-4">
        <h3 className="mb-2 text-sm font-semibold">{label}</h3>
        <p className="text-muted-foreground text-sm">No results available</p>
      </div>
    );
  }

  const extracted = result.extractedData;

  return (
    <div
      className={cn(
        "rounded-md border p-4",
        isWinner && "border-yellow-300 bg-yellow-50/50",
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">{label}</h3>
        {isWinner && (
          <Badge
            variant="outline"
            className="border-yellow-300 bg-yellow-100 text-yellow-800 text-xs"
          >
            Winner
          </Badge>
        )}
      </div>

      <dl className="space-y-1.5 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Confidence</dt>
          <dd className="font-medium">{formatConfidence(result.confidence)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Ranking Score</dt>
          <dd className="font-medium">
            {formatConfidence(result.rankingScore)}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Processing Time</dt>
          <dd className="font-medium">
            {formatDuration(result.processingTimeMs)}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Model</dt>
          <dd className="max-w-[60%] truncate font-mono text-xs">
            {result.modelId}
          </dd>
        </div>

        {/* Extracted data summary */}
        {extracted && (
          <>
            <div className="my-2 border-t" />
            {extracted.merchant?.name && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Merchant</dt>
                <dd className="max-w-[60%] truncate">
                  {extracted.merchant.name}
                </dd>
              </div>
            )}
            {extracted.total != null && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Total</dt>
                <dd className="font-medium">
                  {new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: "USD",
                  }).format(extracted.total)}
                </dd>
              </div>
            )}
            {extracted.category && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Category</dt>
                <dd>{extracted.category}</dd>
              </div>
            )}
            {extracted.lineItems && extracted.lineItems.length > 0 && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Line Items</dt>
                <dd>{extracted.lineItems.length}</dd>
              </div>
            )}
          </>
        )}
      </dl>
    </div>
  );
}
