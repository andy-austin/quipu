"""Tests for hands.tools.file_tools — file upload, parsing, and chunking."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from hands.tools.file_tools import (
    chunk_text,
    list_files,
    parse_csv,
    parse_document,
    upload_file,
)


def _mock_pool(mock_conn):
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)
    return mock_pool


class TestParseCsv:
    def test_parse_csv_basic(self):
        content = "name,age\nAlice,30\nBob,25"
        result = parse_csv(content)
        assert len(result) == 2
        assert result[0] == {"name": "Alice", "age": "30"}
        assert result[1] == {"name": "Bob", "age": "25"}

    def test_parse_csv_empty(self):
        result = parse_csv("name,age\n")
        assert result == []


class TestChunkText:
    def test_short_text_single_chunk(self):
        result = chunk_text("hello world", chunk_size=100)
        assert result == ["hello world"]

    def test_long_text_multiple_chunks(self):
        text = "a" * 500
        result = chunk_text(text, chunk_size=200, overlap=50)
        assert len(result) > 1
        assert all(len(c) <= 200 for c in result)
        # Verify overlap: end of first chunk overlaps with start of second
        assert result[0][-50:] == result[1][:50]

    def test_exact_chunk_size(self):
        text = "a" * 200
        result = chunk_text(text, chunk_size=200)
        assert len(result) == 1


class TestUploadFile:
    async def test_upload_file(self):
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": "file-1", "created_at": ts})
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.file_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await upload_file("user-1", "data.csv", "name,age\nAlice,30", "text/csv")

        assert result["id"] == "file-1"
        assert result["filename"] == "data.csv"
        assert result["content_type"] == "text/csv"
        assert result["size_bytes"] > 0

    async def test_upload_truncates_long_content(self):
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": "file-2", "created_at": ts})
        mock_pool = _mock_pool(mock_conn)

        long_content = "x" * 100_000

        with patch("hands.tools.file_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await upload_file("user-1", "big.txt", long_content)

        assert result["id"] == "file-2"
        # Verify truncated text was stored
        stored_text = mock_conn.fetchrow.call_args[0][5]
        assert len(stored_text) == 50_000


class TestParseDocument:
    async def test_parse_text_file(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "filename": "notes.txt",
                "content_type": "text/plain",
                "text_content": "Hello world " * 500,
            }
        )
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.file_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await parse_document("user-1", "file-1")

        assert result["format"] == "text"
        assert result["chunks"] > 1

    async def test_parse_csv_file(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "filename": "data.csv",
                "content_type": "text/csv",
                "text_content": "name,age\nAlice,30\nBob,25",
            }
        )
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.file_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await parse_document("user-1", "file-1")

        assert result["format"] == "csv"
        assert result["rows"] == 2
        assert result["data"][0]["name"] == "Alice"

    async def test_parse_not_found(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.file_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await parse_document("user-1", "nonexistent")

        assert result == {"error": "File not found"}


class TestListFiles:
    async def test_list_files(self):
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "f1",
                    "filename": "a.txt",
                    "content_type": "text/plain",
                    "size_bytes": 100,
                    "created_at": ts,
                },
            ]
        )
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.file_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await list_files("user-1")

        assert len(result["files"]) == 1
        assert result["files"][0]["filename"] == "a.txt"

    async def test_list_files_empty(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.file_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await list_files("user-1")

        assert result == {"files": []}
