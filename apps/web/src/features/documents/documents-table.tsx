"use client";

import { type ColumnDef } from "@tanstack/react-table";
import { FileText, Folder } from "lucide-react";
import { formatDate } from "@/lib/format";
import type { DocumentRow } from "@/lib/dto";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { UploadDocumentDialog } from "@/features/documents/upload-document-dialog";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const columns: ColumnDef<DocumentRow, unknown>[] = [
  {
    accessorKey: "filename",
    header: "File",
    cell: ({ row }) => (
      <a
        href={`${API_BASE}/documents/${row.original.id}/download`}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2 font-medium hover:underline"
      >
        <FileText className="size-4 text-muted-foreground" />
        {row.original.filename}
      </a>
    ),
  },
  {
    accessorKey: "content_type",
    header: "Type",
    cell: ({ row }) => <span className="text-muted-foreground">{row.original.content_type}</span>,
  },
  {
    accessorKey: "size_bytes",
    header: "Size",
    meta: { align: "right" },
    cell: ({ row }) => <span className="tabular-nums">{humanSize(row.original.size_bytes)}</span>,
  },
  {
    accessorKey: "storage_backend",
    header: "Storage",
    cell: ({ row }) => (
      <Badge variant="secondary">{row.original.storage_backend.toUpperCase()}</Badge>
    ),
  },
  {
    accessorKey: "entity_type",
    header: "Linked to",
    cell: ({ row }) =>
      row.original.entity_type ? (
        <span className="capitalize">{row.original.entity_type.replace("_", " ")}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    accessorKey: "created_at",
    header: "Uploaded",
    cell: ({ row }) => <span className="text-muted-foreground">{formatDate(row.original.created_at)}</span>,
  },
];

export function DocumentsTable({ documents }: { documents: DocumentRow[] }) {
  return (
    <DataTable
      columns={columns}
      data={documents}
      searchPlaceholder="Search documents…"
      toolbar={<UploadDocumentDialog />}
      emptyState={
        <EmptyState
          icon={<Folder className="size-8" strokeWidth={1.5} />}
          title="No documents"
          description="Upload contracts, invoices or specs and link them to any record."
          action={<UploadDocumentDialog />}
        />
      }
    />
  );
}
