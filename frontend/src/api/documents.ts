import client from './client';
import type { Document } from '@/types';

export async function uploadDocument(
  poId: string,
  file: File,
  documentType: string
): Promise<Document> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);
  const { data } = await client.post(
    `/api/v1/purchase-orders/${poId}/documents`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export async function getDocument(id: string): Promise<Document> {
  const { data } = await client.get(`/api/v1/documents/${id}`);
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await client.delete(`/api/v1/documents/${id}`);
}

export function getPreviewUrl(id: string): string {
  return `/api/v1/documents/${id}/preview`;
}

export function getDownloadUrl(id: string): string {
  return `/api/v1/documents/${id}/download`;
}

export async function rotateDocument(
  id: string,
  angle: number
): Promise<Document> {
  const { data } = await client.post(`/api/v1/documents/${id}/rotate`, {
    angle,
  });
  return data;
}
