"use client";

import { useRef, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSubmit: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const text = textareaRef.current?.value.trim();
    if (!text || disabled) return;
    onSubmit(text);
    if (textareaRef.current) textareaRef.current.value = "";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex gap-2 items-end">
      <textarea
        ref={textareaRef}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        placeholder="Scrivi un messaggio… (Invio per inviare, Shift+Invio per andare a capo)"
        rows={2}
        className="flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <button
        onClick={submit}
        disabled={disabled}
        className="shrink-0 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm font-medium transition-colors disabled:cursor-not-allowed"
      >
        Invia
      </button>
    </div>
  );
}
