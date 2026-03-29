"use client";

import { useId, type ReactNode } from "react";
import {
  Cpu,
  Network,
  RotateCcw,
  Shield,
  Sparkles,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

export const defaultConfig = {
  num_rounds: 50,
  local_epochs: 5,
  learning_rate: 0.001,
  batch_size: 64,
  fedprox_mu: 0.01,
  class_weight_multiplier: 1.0,
  dp_epsilon: 8.0,
  dp_delta: 1e-5,
  dp_max_grad_norm: 1.0,
  use_he: false,
  min_clients_per_round: 3,
  round_timeout_seconds: 300,
  min_quorum_ratio: 0.5,
  sequence_length: 24,
  lstm_hidden_size: 128,
  lstm_num_layers: 2,
};

export type JobConfig = typeof defaultConfig;

interface CreateJobDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  config: JobConfig;
  onConfigChange: (config: JobConfig) => void;
  onCreate: () => void;
  creating: boolean;
}

function parseNum(raw: string, fallback: number): number {
  const n = Number.parseFloat(raw);
  return Number.isFinite(n) ? n : fallback;
}

function parseIntSafe(raw: string, fallback: number): number {
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

function Field({
  id,
  label,
  hint,
  children,
  className,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label htmlFor={id} className="text-foreground">
        {label}
      </Label>
      {children}
      {hint ? (
        <p className="text-muted-foreground text-xs leading-relaxed">{hint}</p>
      ) : null}
    </div>
  );
}

export function CreateJobDialog({
  open,
  onOpenChange,
  config,
  onConfigChange,
  onCreate,
  creating,
}: CreateJobDialogProps) {
  const uid = useId();

  const field = (name: string) => `${uid}-${name}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "flex max-h-[min(90vh,720px)] flex-col gap-0 overflow-hidden p-0",
          "sm:max-w-2xl"
        )}
      >
        <div className="space-y-3 px-6 pt-6 pr-14">
          <DialogHeader className="space-y-2 text-left">
            <div className="space-y-1.5">
              <DialogTitle className="text-xl font-semibold tracking-tight">
                New training job
              </DialogTitle>
              <DialogDescription className="text-sm leading-relaxed">
                Configure federated training for critical-event prediction. Input
                size is inferred automatically from each hospital&apos;s prepared
                data.
              </DialogDescription>
            </div>
          </DialogHeader>
        </div>

        <Tabs
          defaultValue="training"
          className="flex min-h-0 flex-1 flex-col gap-0 px-6"
        >
          <TabsList
            variant="line"
            className="mb-1 h-auto w-full flex-wrap justify-start gap-0 p-0 sm:flex-nowrap"
          >
            <TabsTrigger value="training" className="gap-1.5 px-3 py-2">
              <Cpu className="size-4 shrink-0 opacity-70" aria-hidden />
              Training
            </TabsTrigger>
            <TabsTrigger value="privacy" className="gap-1.5 px-3 py-2">
              <Shield className="size-4 shrink-0 opacity-70" aria-hidden />
              Privacy
            </TabsTrigger>
            <TabsTrigger value="orchestration" className="gap-1.5 px-3 py-2">
              <Network className="size-4 shrink-0 opacity-70" aria-hidden />
              Orchestration
            </TabsTrigger>
            <TabsTrigger value="model" className="gap-1.5 px-3 py-2">
              <Sparkles className="size-4 shrink-0 opacity-70" aria-hidden />
              Model
            </TabsTrigger>
          </TabsList>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain py-4">
            <TabsContent value="training" className="mt-0 space-y-4">
              <p className="text-muted-foreground text-sm">
                How many rounds to run, how long each site trains locally, and
                FedProx options.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  id={field("rounds")}
                  label="Communication rounds"
                  hint="How many times the shared model is updated across all sites."
                >
                  <Input
                    id={field("rounds")}
                    type="number"
                    min={1}
                    inputMode="numeric"
                    value={config.num_rounds}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        num_rounds: Math.max(
                          1,
                          parseIntSafe(e.target.value, config.num_rounds)
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("epochs")}
                  label="Local epochs"
                  hint="Training steps on each site, every round."
                >
                  <Input
                    id={field("epochs")}
                    type="number"
                    min={1}
                    inputMode="numeric"
                    value={config.local_epochs}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        local_epochs: Math.max(
                          1,
                          parseIntSafe(e.target.value, config.local_epochs)
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("lr")}
                  label="Learning rate"
                  hint="Step size for local training (typical range 0.0001–0.01)."
                >
                  <Input
                    id={field("lr")}
                    type="number"
                    step="0.0001"
                    min={0}
                    inputMode="decimal"
                    value={config.learning_rate}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        learning_rate: Math.max(
                          0,
                          parseNum(e.target.value, config.learning_rate)
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("batch")}
                  label="Batch size"
                  hint="Samples per training step on each site."
                >
                  <Input
                    id={field("batch")}
                    type="number"
                    min={1}
                    inputMode="numeric"
                    value={config.batch_size}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        batch_size: Math.max(
                          1,
                          parseIntSafe(e.target.value, config.batch_size)
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("mu")}
                  label="FedProx μ (proximal term)"
                  hint="How much each site stays close to the shared model. Use 0 for standard averaging."
                >
                  <Input
                    id={field("mu")}
                    type="number"
                    step="0.001"
                    min={0}
                    inputMode="decimal"
                    value={config.fedprox_mu}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        fedprox_mu: Math.max(
                          0,
                          parseNum(e.target.value, config.fedprox_mu)
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("cw")}
                  label="Class weight multiplier"
                  hint="Loss weight on the positive class: higher values increase recall, lower values increase precision."
                >
                  <Input
                    id={field("cw")}
                    type="number"
                    step="0.1"
                    min={0.1}
                    inputMode="decimal"
                    value={config.class_weight_multiplier}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        class_weight_multiplier: Math.max(
                          0.1,
                          parseNum(
                            e.target.value,
                            config.class_weight_multiplier
                          )
                        ),
                      })
                    }
                  />
                </Field>
              </div>
            </TabsContent>

            <TabsContent value="privacy" className="mt-0 space-y-4">
              <p className="text-muted-foreground text-sm">
                Add privacy noise to shared updates; optionally aggregate updates
                while they stay encrypted.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  id={field("eps")}
                  label="DP ε (epsilon)"
                  hint="Privacy budget ε per round. Lower ε: stronger privacy, usually lower utility."
                >
                  <Input
                    id={field("eps")}
                    type="number"
                    step="0.1"
                    min={0}
                    inputMode="decimal"
                    value={config.dp_epsilon}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        dp_epsilon: Math.max(
                          0,
                          parseNum(e.target.value, config.dp_epsilon)
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("delta")}
                  label="DP δ (delta)"
                  hint="Privacy parameter δ (often 0.00001)."
                >
                  <Input
                    id={field("delta")}
                    type="number"
                    step="0.00001"
                    min={0}
                    inputMode="decimal"
                    value={config.dp_delta}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        dp_delta: Math.max(
                          0,
                          parseNum(e.target.value, config.dp_delta)
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("clip")}
                  label="DP max gradient norm"
                  hint="Gradients are limited to this size before privacy noise is applied."
                  className="sm:col-span-2"
                >
                  <Input
                    id={field("clip")}
                    type="number"
                    step="0.1"
                    min={0}
                    inputMode="decimal"
                    value={config.dp_max_grad_norm}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        dp_max_grad_norm: Math.max(
                          0,
                          parseNum(e.target.value, config.dp_max_grad_norm)
                        ),
                      })
                    }
                  />
                </Field>
              </div>
              <div className="bg-muted/40 flex items-center justify-between gap-4 rounded-lg border p-4">
                <div className="min-w-0 space-y-1">
                  <Label htmlFor={field("he")} className="text-base">
                    Homomorphic encryption
                  </Label>
                  <p className="text-muted-foreground text-xs leading-relaxed">
                    Combine model updates without decrypting them first. Rounds
                    take longer when this is on.
                  </p>
                </div>
                <Switch
                  id={field("he")}
                  checked={config.use_he}
                  onCheckedChange={(checked) =>
                    onConfigChange({ ...config, use_he: checked })
                  }
                />
              </div>
            </TabsContent>

            <TabsContent value="orchestration" className="mt-0 space-y-4">
              <p className="text-muted-foreground text-sm">
                Minimum participants, round wait time, and quorum threshold.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  id={field("minc")}
                  label="Minimum clients per round"
                  hint="Minimum clients that must join a round for it to run."
                >
                  <Input
                    id={field("minc")}
                    type="number"
                    min={1}
                    inputMode="numeric"
                    value={config.min_clients_per_round}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        min_clients_per_round: Math.max(
                          1,
                          parseIntSafe(
                            e.target.value,
                            config.min_clients_per_round
                          )
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("timeout")}
                  label="Round timeout (seconds)"
                  hint="How long to wait for sites. If time runs out, results merge if enough sites responded; otherwise the round is skipped."
                >
                  <Input
                    id={field("timeout")}
                    type="number"
                    step={30}
                    min={30}
                    inputMode="numeric"
                    value={config.round_timeout_seconds}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        round_timeout_seconds: Math.max(
                          30,
                          parseIntSafe(
                            e.target.value,
                            config.round_timeout_seconds
                          )
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("quorum")}
                  label="Minimum quorum ratio"
                  hint="If a round times out, minimum share of sites that must have responded to still combine updates (0.5 = half)."
                  className="sm:col-span-2"
                >
                  <Input
                    id={field("quorum")}
                    type="number"
                    step="0.05"
                    min={0.1}
                    max={1}
                    inputMode="decimal"
                    value={config.min_quorum_ratio}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        min_quorum_ratio: Math.min(
                          1,
                          Math.max(
                            0.1,
                            parseNum(e.target.value, config.min_quorum_ratio)
                          )
                        ),
                      })
                    }
                  />
                </Field>
              </div>
            </TabsContent>

            <TabsContent value="model" className="mt-0 space-y-4">
              <p className="text-muted-foreground text-sm">
                LSTM model size and how many time steps each sample includes. Use
                the same sequence length as in your data preparation.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  id={field("hidden")}
                  label="LSTM hidden size"
                  hint="Hidden state width per LSTM layer."
                >
                  <Input
                    id={field("hidden")}
                    type="number"
                    min={1}
                    inputMode="numeric"
                    value={config.lstm_hidden_size}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        lstm_hidden_size: Math.max(
                          1,
                          parseIntSafe(
                            e.target.value,
                            config.lstm_hidden_size
                          )
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("layers")}
                  label="LSTM layers"
                  hint="Stacked LSTM depth (1–8)."
                >
                  <Input
                    id={field("layers")}
                    type="number"
                    min={1}
                    max={8}
                    inputMode="numeric"
                    value={config.lstm_num_layers}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        lstm_num_layers: Math.min(
                          8,
                          Math.max(
                            1,
                            parseIntSafe(
                              e.target.value,
                              config.lstm_num_layers
                            )
                          )
                        ),
                      })
                    }
                  />
                </Field>
                <Field
                  id={field("seq")}
                  label="Sequence length (timesteps)"
                  hint="Time steps per sample; must match your prepared data (often 24)."
                  className="sm:col-span-2"
                >
                  <Input
                    id={field("seq")}
                    type="number"
                    min={1}
                    inputMode="numeric"
                    value={config.sequence_length}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        sequence_length: Math.max(
                          1,
                          parseIntSafe(e.target.value, config.sequence_length)
                        ),
                      })
                    }
                  />
                </Field>
              </div>
            </TabsContent>
          </div>
        </Tabs>

        <Separator />

        <DialogFooter className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={() => onConfigChange({ ...defaultConfig })}
          >
            <RotateCcw className="size-3.5" aria-hidden />
            Reset defaults
          </Button>
          <div className="flex w-full gap-2 sm:w-auto sm:justify-end sm:gap-3">
            <Button
              type="button"
              variant="outline"
              className="flex-1 sm:flex-initial"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="flex-1 sm:flex-initial"
              onClick={onCreate}
              disabled={creating}
            >
              {creating ? "Creating…" : "Create job"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
