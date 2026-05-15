import { clsx } from "clsx";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

export function MessageBubble({
  role,
  content,
  streaming = false,
}: MessageBubbleProps) {
  return (
    <div className={clsx("flex", role === "user" ? "justify-end" : "justify-start")}>
      <div
        className={clsx(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          role === "user"
            ? "bg-blue-900 text-white rounded-br-sm"
            : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-sm"
        )}
      >
        <p className="whitespace-pre-wrap">{content}</p>
        {streaming && (
          <span className="inline-block w-2 h-3.5 bg-current ml-0.5 align-middle animate-pulse rounded-sm" />
        )}
      </div>
    </div>
  );
}
