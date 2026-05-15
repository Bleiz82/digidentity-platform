import { clsx } from "clsx";

export type StreamState =
  | "idle"
  | "connecting"
  | "streaming"
  | "error"
  | "complete";

interface StreamStatusProps {
  state: StreamState;
}

const STATE_CONFIG: Record<StreamState, { dot: string; label: string }> = {
  idle:       { dot: "bg-gray-400",                    label: "In attesa" },
  connecting: { dot: "bg-yellow-400 animate-pulse",    label: "Connessione…" },
  streaming:  { dot: "bg-green-400 animate-pulse",     label: "Streaming" },
  error:      { dot: "bg-red-500",                     label: "Errore connessione" },
  complete:   { dot: "bg-green-500",                   label: "Completato" },
};

export function StreamStatus({ state }: StreamStatusProps) {
  const { dot, label } = STATE_CONFIG[state];
  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
      <span className={clsx("inline-block w-2 h-2 rounded-full", dot)} />
      <span>{label}</span>
    </div>
  );
}
