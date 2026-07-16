import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { UploadDropzone } from "./UploadDropzone";

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, uploadContract: vi.fn() };
});

const { uploadContract } = await import("@/lib/api");
const uploadMock = vi.mocked(uploadContract);

function selectFile(file: File) {
  const input = screen.getByLabelText("Selecionar contrato");
  fireEvent.change(input, { target: { files: [file] } });
}

describe("UploadDropzone", () => {
  beforeEach(() => {
    uploadMock.mockReset();
  });

  it("envia PDF válido e chama onUploaded com o id", async () => {
    uploadMock.mockResolvedValue({ id: "abc-123", status: "processing" });
    const onUploaded = vi.fn();
    render(<UploadDropzone onUploaded={onUploaded} />);

    selectFile(new File(["%PDF"], "contrato.pdf", { type: "application/pdf" }));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith("abc-123"));
    expect(uploadMock).toHaveBeenCalledOnce();
  });

  it("rejeita tipo não suportado sem chamar a API", async () => {
    const onUploaded = vi.fn();
    render(<UploadDropzone onUploaded={onUploaded} />);

    selectFile(new File(["x"], "nota.txt", { type: "text/plain" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Tipo de arquivo não suportado. Envie um PDF ou DOCX.",
    );
    expect(uploadMock).not.toHaveBeenCalled();
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it("exibe o detail de um ApiError 413", async () => {
    uploadMock.mockRejectedValue(new ApiError(413, "Arquivo acima do limite de 20 MB."));
    render(<UploadDropzone onUploaded={vi.fn()} />);

    selectFile(new File(["%PDF"], "grande.pdf", { type: "application/pdf" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Arquivo acima do limite de 20 MB.",
    );
  });
});
