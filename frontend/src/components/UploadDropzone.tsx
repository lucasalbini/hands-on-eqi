"use client";

import { useRef, useState } from "react";

import { ApiError, uploadContract } from "@/lib/api";

const ACCEPTED_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

interface UploadDropzoneProps {
  onUploaded: (id: string) => void;
}

export function UploadDropzone({ onUploaded }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function handleFile(file: File) {
    setError(null);
    if (!ACCEPTED_TYPES.has(file.type)) {
      setError("Tipo de arquivo não suportado. Envie um PDF ou DOCX.");
      return;
    }
    setUploading(true);
    try {
      const created = await uploadContract(file);
      onUploaded(created.id);
    } catch (err) {
      if (err instanceof ApiError && typeof err.detail === "string") {
        setError(err.detail);
      } else {
        setError("Falha no envio. Tente novamente.");
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) void handleFile(file);
        }}
        className={`w-full rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          dragging
            ? "border-blue-500 bg-blue-50"
            : "border-neutral-300 hover:border-neutral-400"
        } ${uploading ? "cursor-wait opacity-60" : "cursor-pointer"}`}
      >
        <p className="font-medium">
          {uploading ? "Enviando..." : "Arraste um contrato aqui ou clique para selecionar"}
        </p>
        <p className="mt-1 text-sm text-neutral-500">PDF ou DOCX, até 20 MB</p>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        aria-label="Selecionar contrato"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = "";
        }}
      />
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
