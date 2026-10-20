"""
Text chunking strategies for RAG.

Strategies:
- Sentence-based: split by sentences, group into chunks of target size
- Character-based: split by character count with overlap
- Token-based: split by token count (approximate using whitespace)

All chunking is deterministic — no randomness.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    """A text chunk with metadata."""
    text: str
    index: int
    start_char: int = 0
    end_char: int = 0
    page: Optional[int] = None
    metadata: dict = field(default_factory=dict)
    char_count: int = 0
    token_estimate: int = 0


class SentenceChunker:
    """Split text by sentences and group into chunks."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, page: Optional[int] = None) -> list[Chunk]:
        sentences = self._split_sentences(text)
        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_len = 0
        idx = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current_len + sentence_len > self.chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk).strip()
                chunks.append(Chunk(
                    text=chunk_text,
                    index=idx,
                    start_char=0,
                    end_char=len(chunk_text),
                    page=page,
                    char_count=len(chunk_text),
                    token_estimate=len(chunk_text.split()),
                ))
                idx += 1
                # Keep overlap from last sentence
                if self.overlap > 0:
                    overlap_text = current_chunk[-1]
                    current_chunk = [overlap_text]
                    current_len = len(overlap_text)
                else:
                    current_chunk = []
                    current_len = 0
            current_chunk.append(sentence)
            current_len += sentence_len

        if current_chunk:
            chunk_text = " ".join(current_chunk).strip()
            chunks.append(Chunk(
                text=chunk_text,
                index=idx,
                start_char=0,
                end_char=len(chunk_text),
                page=page,
                char_count=len(chunk_text),
                token_estimate=len(chunk_text.split()),
            ))

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences using regex."""
        # Split on sentence-ending punctuation
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]


class CharacterChunker:
    """Split text by character count with overlap."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, page: Optional[int] = None) -> list[Chunk]:
        chunks: list[Chunk] = []
        idx = 0
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    text=chunk_text,
                    index=idx,
                    start_char=start,
                    end_char=min(end, len(text)),
                    page=page,
                    char_count=len(chunk_text),
                    token_estimate=len(chunk_text.split()),
                ))
                idx += 1
            start += self.chunk_size - self.overlap

        return chunks


class TokenChunker:
    """Split text by approximate token count (whitespace-based)."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, page: Optional[int] = None) -> list[Chunk]:
        tokens = text.split()
        chunks: list[Chunk] = []
        idx = 0
        start = 0

        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = " ".join(chunk_tokens)
            if chunk_text.strip():
                chunks.append(Chunk(
                    text=chunk_text,
                    index=idx,
                    start_char=start,
                    end_char=end,
                    page=page,
                    char_count=len(chunk_text),
                    token_estimate=len(chunk_tokens),
                ))
                idx += 1
            start += self.chunk_size - self.overlap

        return chunks


class SemanticChunker:
    """
    Smart chunker that tries to split at logical boundaries.

    Rules:
1. Split on double newlines first (paragraphs)
2. Split on single newlines
3. Split on sentences within paragraphs
4. Merge sentences into target-sized chunks

This produces the highest-quality chunks for document search.
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.sentence_chunker = SentenceChunker(chunk_size, overlap)

    def chunk(self, text: str, page: Optional[int] = None) -> list[Chunk]:
        paragraphs = re.split(r'\n\s*\n', text.strip())
        chunks: list[Chunk] = []
        idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Try to chunk by sentences first
            sentences = self.sentence_chunker._split_sentences(para)
            if not sentences:
                sentences = [para]

            current_chunk: list[str] = []
            current_len = 0

            for sentence in sentences:
                s_len = len(sentence)
                if current_len + s_len > self.chunk_size and current_chunk:
                    chunk_text = " ".join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(Chunk(
                            text=chunk_text,
                            index=idx,
                            start_char=0,
                            end_char=len(chunk_text),
                            page=page,
                            char_count=len(chunk_text),
                            token_estimate=len(chunk_text.split()),
                        ))
                        idx += 1
                    if self.overlap > 0 and current_chunk:
                        current_chunk = [current_chunk[-1]]
                        current_len = len(current_chunk[-1])
                    else:
                        current_chunk = []
                        current_len = 0
                current_chunk.append(sentence)
                current_len += s_len

            if current_chunk:
                chunk_text = " ".join(current_chunk).strip()
                if chunk_text:
                    chunks.append(Chunk(
                        text=chunk_text,
                        index=idx,
                        start_char=0,
                        end_char=len(chunk_text),
                        page=page,
                        char_count=len(chunk_text),
                        token_estimate=len(chunk_text.split()),
                    ))
                    idx += 1

        return chunks


class ChunkerFactory:
    """Factory to create chunkers by name."""

    STRATEGIES = {
        "sentence": SentenceChunker,
        "character": CharacterChunker,
        "token": TokenChunker,
        "semantic": SemanticChunker,
    }

    @classmethod
    def create(cls, strategy: str = "semantic", chunk_size: int = 512, overlap: int = 50) -> Chunk:
        if strategy not in cls.STRATEGIES:
            raise ValueError(f"Unknown chunking strategy: {strategy}. Available: {list(cls.STRATEGIES.keys())}")
        return cls.STRATEGIES[strategy](chunk_size, overlap)