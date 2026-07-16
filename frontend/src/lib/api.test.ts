import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  getContractStatus,
  listContracts,
  patchFields,
  uploadContract,
} from "./api";

function mockFetchOnce(status: number, body: unknown) {
  const response = new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("uploadContract", () => {
  it("envia multipart com o arquivo e parseia o 202", async () => {
    const spy = mockFetchOnce(202, { id: "abc-123", status: "processing" });
    const file = new File(["%PDF-1.4"], "contrato.pdf", { type: "application/pdf" });

    const created = await uploadContract(file);

    expect(created).toEqual({ id: "abc-123", status: "processing" });
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/contracts");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBe(file);
  });

  it("lança ApiError com status e detail em erro 400", async () => {
    mockFetchOnce(400, { detail: "Tipo de arquivo não suportado" });
    const file = new File(["x"], "nota.txt", { type: "text/plain" });

    const error = await uploadContract(file).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(400);
    expect((error as ApiError).detail).toBe("Tipo de arquivo não suportado");
  });
});

describe("listContracts", () => {
  it("parseia o array de contratos", async () => {
    const item = {
      id: "abc",
      original_filename: "c.pdf",
      status: "completed",
      current_stage: null,
      contract_type: "Cloud",
      created_at: "2026-07-16T12:00:00Z",
    };
    mockFetchOnce(200, [item]);

    await expect(listContracts()).resolves.toEqual([item]);
  });
});

describe("getContractStatus", () => {
  it("monta a URL com o id", async () => {
    const spy = mockFetchOnce(200, {
      id: "abc",
      status: "processing",
      current_stage: "extract",
      error_message: null,
    });

    const status = await getContractStatus("abc");

    expect(spy.mock.calls[0][0]).toBe("/api/v1/contracts/abc/status");
    expect(status.current_stage).toBe("extract");
  });
});

describe("patchFields", () => {
  it("envia PATCH JSON com o mapa de correções", async () => {
    const spy = mockFetchOnce(200, { id: "abc" });

    await patchFields("abc", { "provider.cnpj": "11.222.333/0001-81", issue_date: null });

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/contracts/abc/fields");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      fields: { "provider.cnpj": "11.222.333/0001-81", issue_date: null },
    });
  });

  it("preserva o detail estruturado de um 422", async () => {
    const detail = [{ loc: ["fields", "provider.cnpj"], msg: "dígito verificador inválido" }];
    mockFetchOnce(422, { detail });

    const error = await patchFields("abc", { "provider.cnpj": "bad" }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(422);
    expect((error as ApiError).detail).toEqual(detail);
  });
});
