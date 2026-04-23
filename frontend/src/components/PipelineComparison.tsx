import { useState } from "react";
import { Loader2, ToggleLeft, ToggleRight, Trophy, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { usePipelineResults } from "@/hooks/useCategories";
import type { PipelineResult } from "@/api/categories";

interface PipelineComparisonProps {
  receiptId: string;
}

const PIPELINE_META: Record<
  string,
  { label: string; description: string; steps: string[] }
> = {
  "ocr-ai": {
    label: "Textract + AI Categorization",
    description:
      "Two-stage pipeline: AWS Textract performs OCR to extract raw text and fields from the image, then Amazon Nova receives only the structured text to categorize and normalize the receipt. Nova does not see the image.",
    steps: [
      "AWS Textract AnalyzeExpense reads the image and extracts text, fields, and line items",
      "Amazon Nova receives only Textract's structured OCR text (no image)",
      "Nova categorizes the receipt, assigns subcategories, and outputs structured JSON",
    ],
  },
  "ai-multimodal": {
    label: "AI Vision",
    description:
      "Single-stage pipeline: Amazon Nova directly analyzes the receipt image end-to-end without any OCR preprocessing, performing both text extraction and categorization in one pass.",
    steps: [
      "Amazon Nova receives only the raw receipt image (no OCR input)",
      "Nova performs text extraction, field identification, and categorization in a single inference",
      "Nova outputs the same structured JSON schema as the other pipeline",
    ],
  },
};

function formatPercent(value: number | null): string {
  if (value == null) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function Tooltip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex cursor-help">
      <Info className="text-muted-foreground size-3.5" />
      <span
        className={cn(
          "pointer-events-none absolute bottom-full left-1/2 z-10 mb-1.5 -translate-x-1/2",
          "w-64 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md",
          "opacity-0 transition-opacity group-hover:opacity-100",
        )}
      >
        {text}
      </span>
    </span>
  );
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
              {/* How it works summary */}
              <p className="text-xs text-muted-foreground">
                Both pipelines run in parallel on every receipt.
                Textract + AI Categorization is the primary pipeline whose
                result is used. AI Vision serves as a fallback if the primary
                fails, and for quality comparison. Ranking scores are for
                observability only and do not affect which result is displayed.
              </p>

              {/* Winner badge */}
              {data.rankingWinner && (
                <div className="flex items-center gap-2">
                  <Trophy className="size-4 text-yellow-500" />
                  <span className="text-sm font-medium">
                    Higher ranking score:{" "}
                    {PIPELINE_META[data.rankingWinner]?.label ??
                      data.rankingWinner}
                  </span>
                  {data.usedFallback && (
                    <Badge variant="outline" className="text-xs">
                      Fallback used
                    </Badge>
                  )}
                </div>
              )}

              {/* Side-by-side results */}
              <div className="grid gap-4 lg:grid-cols-2">
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
  const meta = PIPELINE_META[pipelineType] ?? {
    label: pipelineType,
    description: "",
    steps: [],
  };

  if (!result) {
    return (
      <div className="rounded-md border border-dashed p-4">
        <h3 className="mb-2 text-sm font-semibold">{meta.label}</h3>
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
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">{meta.label}</h3>
        {isWinner && (
          <Badge
            variant="outline"
            className="border-yellow-300 bg-yellow-100 text-yellow-800 text-xs"
          >
            Winner
          </Badge>
        )}
      </div>

      {/* Pipeline description */}
      <p className="mb-3 text-xs text-muted-foreground">{meta.description}</p>

      {/* Steps */}
      <ol className="mb-4 space-y-1 text-xs text-muted-foreground">
        {meta.steps.map((step, i) => (
          <li key={i} className="flex gap-2">
            <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium">
              {i + 1}
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>

      {/* Metrics */}
      <dl className="space-y-1.5 text-sm">
        <div className="flex items-center justify-between">
          <dt className="flex items-center gap-1.5 text-muted-foreground">
            Confidence
            <Tooltip
              text={
                pipelineType === "ocr-ai"
                  ? "Model-reported confidence (0-100%). Nova's self-assessed certainty based on Textract's OCR quality, data completeness, and field consistency."
                  : "Model-reported confidence (0-100%). Nova's self-assessed certainty based on image clarity, data completeness, and field consistency."
              }
            />
          </dt>
          <dd className="font-medium">{formatPercent(result.confidence)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="flex items-center gap-1.5 text-muted-foreground">
            Ranking Score
            <Tooltip text="Composite score: 40% confidence + 25% field completeness + 20% line-item-to-total consistency + 15% line item count. Used for pipeline quality comparison only." />
          </dt>
          <dd className="font-medium">{formatPercent(result.rankingScore)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Processing Time</dt>
          <dd className="font-medium">{formatDuration(result.processingTimeMs)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="flex items-center gap-1.5 text-muted-foreground">
            Cost
            <Tooltip
              text={
                pipelineType === "ocr-ai"
                  ? "Textract AnalyzeExpense ($0.01/page) + Nova Lite input ($0.06/1M tokens) and output ($0.24/1M tokens)."
                  : "Nova Lite input ($0.06/1M tokens) and output ($0.24/1M tokens). No OCR preprocessing cost."
              }
            />
          </dt>
          <dd className="font-mono text-xs font-medium">
            {result.costUsd != null ? `$${result.costUsd.toFixed(4)}` : "--"}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="flex items-center gap-1.5 text-muted-foreground">
            Model
            <Tooltip
              text={
                pipelineType === "ocr-ai"
                  ? "Nova receives only Textract's structured OCR text (no image) and performs categorization and normalization."
                  : "Nova receives only the raw image and performs both text extraction and categorization in a single pass."
              }
            />
          </dt>
          <dd className="font-mono text-xs">{result.modelId}</dd>
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
                  {formatCurrency(extracted.total)}
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
