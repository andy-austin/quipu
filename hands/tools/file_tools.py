"""Tools for file upload, parsing, and chunking."""

import csv
import io

from hands.logging import log
from hands.tools.db_tools import get_pool

# Maximum text content stored per file (characters)
_MAX_TEXT_LENGTH = 50_000


def parse_csv(content: str) -> list[dict]:
    """Parse CSV content into a list of dicts."""
    reader = csv.DictReader(io.StringIO(content))
    return [dict(row) for row in reader]


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: The full text to chunk.
        chunk_size: Maximum characters per chunk.
        overlap: Characters of overlap between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


async def upload_file(
    user_id: str,
    filename: str,
    content: str,
    content_type: str = "text/plain",
) -> dict:
    """Upload and store a text-based file.

    Args:
        user_id: The file owner.
        filename: Original filename.
        content: File content as text (plain text, CSV, or extracted PDF text).
        content_type: MIME type of the file.

    Returns:
        Dict with file id and metadata.
    """
    log.info("upload_file", user_id=user_id, filename=filename, content_type=content_type)
    text_content = content[:_MAX_TEXT_LENGTH]
    size_bytes = len(content.encode("utf-8"))

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO user_files (user_id, filename, content_type, size_bytes, text_content) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id, created_at",
            user_id,
            filename,
            content_type,
            size_bytes,
            text_content,
        )
    file_id = str(row["id"])
    log.info("file_uploaded", file_id=file_id, size_bytes=size_bytes)
    return {
        "id": file_id,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "created_at": row["created_at"].isoformat(),
    }


async def parse_document(
    user_id: str,
    file_id: str,
    chunk_size: int = 2000,
) -> dict:
    """Parse a stored file into text chunks for processing.

    Args:
        user_id: The file owner.
        file_id: UUID of the stored file.
        chunk_size: Characters per chunk (default 2000).

    Returns:
        Dict with filename, content_type, and text chunks.
    """
    log.info("parse_document", user_id=user_id, file_id=file_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT filename, content_type, text_content FROM user_files "
            "WHERE id = $1 AND user_id = $2",
            file_id,
            user_id,
        )
    if not row:
        return {"error": "File not found"}

    text = row["text_content"] or ""
    content_type = row["content_type"]

    # Parse CSV into structured data
    if content_type == "text/csv":
        try:
            parsed = parse_csv(text)
            return {
                "filename": row["filename"],
                "content_type": content_type,
                "format": "csv",
                "rows": len(parsed),
                "data": parsed[:100],  # Limit to first 100 rows
            }
        except Exception as e:
            log.warning("csv_parse_failed", error=str(e))

    # Default: chunk text
    chunks = chunk_text(text, chunk_size=chunk_size)
    return {
        "filename": row["filename"],
        "content_type": content_type,
        "format": "text",
        "chunks": len(chunks),
        "data": chunks,
    }


async def list_files(user_id: str, limit: int = 50) -> dict:
    """List files uploaded by a user.

    Args:
        user_id: The file owner.
        limit: Maximum files to return.

    Returns:
        Dict with list of file summaries.
    """
    log.info("list_files", user_id=user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, filename, content_type, size_bytes, created_at "
            "FROM user_files WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id,
            limit,
        )
    return {
        "files": [
            {
                "id": str(r["id"]),
                "filename": r["filename"],
                "content_type": r["content_type"],
                "size_bytes": r["size_bytes"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }
