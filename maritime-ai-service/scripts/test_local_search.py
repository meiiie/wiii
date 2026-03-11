"""Test local search directly with the Google GenAI SDK."""

import asyncio
import os

import asyncpg
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


async def test_search():
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    query = "Dieu 15 ve tinh huong cat huong"
    print(f"Query: {query}")

    result = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    query_embedding = result.embeddings[0].values
    print(f"Embedding dim: {len(query_embedding)}")

    url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)

    row = await conn.fetchrow(
        """
        SELECT id, embedding IS NOT NULL as has_emb, array_length(embedding, 1) as emb_len
        FROM knowledge_embeddings
        LIMIT 1
        """
    )
    print(f"\nEmbedding check: has_emb={row['has_emb']}, dim={row['emb_len']}")

    print("\n--- Text Search (LIKE) ---")
    rows = await conn.fetch(
        """
        SELECT content, content_type, page_number
        FROM knowledge_embeddings
        WHERE content ILIKE '%Dieu 15%' OR content ILIKE '%cat huong%'
        LIMIT 3
        """
    )
    for result_row in rows:
        preview = result_row["content"][:100]
        print(
            f"Page {result_row['page_number']} ({result_row['content_type']}): {preview}..."
        )

    if not rows:
        print("No results from text search")
        rows = await conn.fetch(
            """
            SELECT content, content_type, page_number
            FROM knowledge_embeddings
            WHERE content ILIKE '%Dieu%'
            LIMIT 3
            """
        )
        print("\nBroader search (Dieu):")
        for result_row in rows:
            preview = result_row["content"][:100]
            print(
                f"Page {result_row['page_number']} ({result_row['content_type']}): {preview}..."
            )

    await conn.close()


asyncio.run(test_search())
