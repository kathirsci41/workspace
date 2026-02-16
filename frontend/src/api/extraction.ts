import client from './client';
import type { DocumentMetadata } from '@/types';

export async function getMetadata(
  documentId: string
): Promise<DocumentMetadata> {
  const { data } = await client.get(
    `/api/v1/documents/${documentId}/metadata`
  );
  return data;
}

export async function verifyMetadata(
  documentId: string,
  editedData: Record<string, unknown>
): Promise<DocumentMetadata> {
  const { data } = await client.put(
    `/api/v1/documents/${documentId}/metadata/verify`,
    { extracted_data: editedData }
  );
  return data;
}

export async function rejectMetadata(
  documentId: string
): Promise<DocumentMetadata> {
  const { data } = await client.put(
    `/api/v1/documents/${documentId}/metadata/reject`
  );
  return data;
}

export async function reExtract(documentId: string): Promise<void> {
  await client.post(`/api/v1/documents/${documentId}/re-extract`);
}

export async function getFieldTemplate(
  documentId: string
): Promise<{ document_type: string; fields: Record<string, null>; field_descriptions: Record<string, string> }> {
  const { data } = await client.get(
    `/api/v1/documents/${documentId}/metadata/template`
  );
  return data;
}

export async function createManualEntry(
  documentId: string
): Promise<DocumentMetadata> {
  const { data } = await client.post(
    `/api/v1/documents/${documentId}/metadata/manual`
  );
  return data;
}
