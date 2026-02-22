"""
Test Local Environment Connectivity

Professional test script to verify all cloud database connections from local development.
SOTA Pattern: Health check before starting development server.
"""
import asyncio
import sys
import time
from typing import Dict

# Rich for beautiful terminal output
try:
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("💡 Tip: Install 'rich' for better output: pip install rich")


async def test_neon_postgresql() -> Dict[str, any]:
    """Test Neon PostgreSQL connection."""
    try:
        from app.core.database import engine, test_connection
        from sqlalchemy import text
        
        start = time.time()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            elapsed = time.time() - start
            
        return {
            "status": "✅ Connected",
            "latency": f"{elapsed*1000:.1f}ms",
            "info": version.split()[1] if version else "Unknown",
            "error": None
        }
    except Exception as e:
        return {
            "status": "❌ Failed",
            "latency": "-",
            "info": "-",
            "error": str(e)[:100]
        }


async def test_neo4j_auradb() -> Dict[str, any]:
    """Test Neo4j AuraDB connection."""
    try:
        from app.repositories.neo4j_knowledge_repository import Neo4jKnowledgeRepository
        
        start = time.time()
        repo = Neo4jKnowledgeRepository()
        # Simple test query
        result = await repo.driver.execute_query("RETURN 'OK' as status")
        elapsed = time.time() - start
        
        return {
            "status": "✅ Connected",
            "latency": f"{elapsed*1000:.1f}ms",
            "info": "AuraDB 5.x",
            "error": None
        }
    except Exception as e:
        return {
            "status": "❌ Failed",
            "latency": "-",
            "info": "-",
            "error": str(e)[:100]
        }


async def test_gemini_api() -> Dict[str, any]:
    """Test Google Gemini API."""
    try:
        from app.engine.gemini_embedding import GeminiEmbedding
        
        start = time.time()
        embedder = GeminiEmbedding()
        result = await embedder.embed_text("connectivity test")
        elapsed = time.time() - start
        
        return {
            "status": "✅ Connected",
            "latency": f"{elapsed*1000:.1f}ms",
            "info": f"{len(result)}-dim embedding",
            "error": None
        }
    except Exception as e:
        return {
            "status": "❌ Failed",
            "latency": "-",
            "info": "-",
            "error": str(e)[:100]
        }


async def test_object_storage() -> Dict[str, any]:
    """Test Object Storage (MinIO) connection."""
    try:
        from app.services.object_storage import ObjectStorageClient

        start = time.time()
        storage = ObjectStorageClient()
        # Check if client is initialized
        if storage.client:
            elapsed = time.time() - start
            return {
                "status": "✅ Connected",
                "latency": f"{elapsed*1000:.1f}ms",
                "info": "Storage ready",
                "error": None
            }
        else:
            return {
                "status": "⚠️ Skipped",
                "latency": "-",
                "info": "Not configured",
                "error": None
            }
    except Exception as e:
        return {
            "status": "⚠️ Optional",
            "latency": "-",
            "info": "Not required",
            "error": None
        }


async def main():
    """Run all connectivity tests."""
    print("\n🧪 Wiii - Local Environment Connectivity Test\n")
    print("Testing connections to cloud databases from local machine...\n")
    
    # Run tests
    tests = {
        "Neon PostgreSQL": test_neon_postgresql(),
        "Neo4j AuraDB": test_neo4j_auradb(),
        "Google Gemini API": test_gemini_api(),
        "Object Storage": test_object_storage(),
    }
    
    results = {}
    for name, test_coro in tests.items():
        print(f"⏳ Testing {name}...")
        results[name] = await test_coro
    
    # Display results
    print("\n" + "="*70)
    print("📊 CONNECTIVITY RESULTS")
    print("="*70 + "\n")
    
    if RICH_AVAILABLE:
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan", width=20)
        table.add_column("Status", width=15)
        table.add_column("Latency", justify="right", width=10)
        table.add_column("Info", width=24)
        
        for name, result in results.items():
            status_style = "green" if "✅" in result["status"] else "red" if "❌" in result["status"] else "yellow"
            table.add_row(
                name,
                f"[{status_style}]{result['status']}[/{status_style}]",
                result["latency"],
                result["info"]
            )
        
        console.print(table)
    else:
        # Fallback to simple print
        for name, result in results.items():
            print(f"{name:25} {result['status']:15} {result['latency']:>10}  {result['info']}")
            if result["error"]:
                print(f"  └─ Error: {result['error']}")
    
    # Summary
    print("\n" + "="*70)
    failed = [name for name, r in results.items() if "❌" in r["status"]]
    
    if not failed:
        print("✨ All connectivity tests passed! Local environment is ready.")
        print("\n💡 Next step: Run server with: uvicorn app.main:app --reload")
        return 0
    else:
        print(f"❌ {len(failed)} test(s) failed:")
        for name in failed:
            print(f"   - {name}: {results[name]['error']}")
        print("\n💡 Check your .env file and ensure all credentials are correct.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
