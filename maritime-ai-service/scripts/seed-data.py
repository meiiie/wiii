#!/usr/bin/env python3
"""
Wiii - Test Data Seeding Script
=============================================

This script seeds the local development database with test data for:
- Sample documents (COLREGs, SOLAS references)
- Test users and chat history
- Sample knowledge graph entities

Usage:
    python scripts/seed-data.py

Environment:
    Requires .env.local to be configured with local database URLs
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add project to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

# Load environment from .env.local
from dotenv import load_dotenv

env_file = project_dir / ".env.local"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"⚠️  {env_file} not found, using default environment")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Test data
SAMPLE_DOCUMENTS = [
    {
        "title": "COLREGs Rule 15 - Crossing Situation",
        "content": """
Rule 15 - Crossing Situation

When two power-driven vessels are crossing so as to involve risk of collision, 
the vessel which has the other on her own starboard side shall keep out of the 
way and shall, if the circumstances of the case admit, avoid crossing ahead 
of the other vessel.

Key Points:
- Applies to power-driven vessels only
- Risk of collision must exist
- Give-way vessel has other vessel on starboard side
- Avoid crossing ahead if possible
        """,
        "source_type": "regulation",
        "metadata": {"regulation": "COLREGs", "rule": "15"}
    },
    {
        "title": "COLREGs Rule 13 - Overtaking",
        "content": """
Rule 13 - Overtaking

(a) Notwithstanding anything contained in the Rules of Part B, Sections I and II, 
any vessel overtaking any other shall keep out of the way of the vessel being overtaken.

(b) A vessel shall be deemed to be overtaking when coming up with another vessel 
from a direction more than 22.5 degrees abaft her beam.

Key Points:
- Overtaking vessel is always give-way vessel
- Applies in all conditions of visibility
- Overtaking status continues until finally past and clear
        """,
        "source_type": "regulation",
        "metadata": {"regulation": "COLREGs", "rule": "13"}
    },
    {
        "title": "SOLAS Chapter V - Safety of Navigation",
        "content": """
Regulation 19 - Carriage requirements for shipborne navigational systems and equipment

1. All ships shall be fitted with the following equipment:
   .1 A gyro compass
   .2 A gyro-compass heading repeater
   .3 A gyro-compass bearing repeater
   .4 A magnetic compass
   .5 Means of correcting heading and bearings to true
   .6 A pelorus or compass bearing device
   .7 Means of taking bearings over an arc of the horizon of 360°
        """,
        "source_type": "regulation",
        "metadata": {"regulation": "SOLAS", "chapter": "V", "regulation": "19"}
    },
    {
        "title": "Lights and Shapes - Power-driven vessel underway",
        "content": """
Rule 23 - Power-driven Vessels Underway

(a) A power-driven vessel underway shall exhibit:
    (i) a masthead light forward;
    (ii) a second masthead light abaft of and higher than the forward one;
    (iii) sidelights;
    (iv) a sternlight.

(b) An air-cushion vessel when operating in the non-displacement mode shall exhibit:
    (i) the lights prescribed in paragraph (a);
    (ii) an all-round flashing yellow light.
        """,
        "source_type": "regulation",
        "metadata": {"regulation": "COLREGs", "rule": "23"}
    }
]

SAMPLE_CHAT_HISTORY = [
    {
        "user_message": "Xin chào, tôi là sinh viên năm 3 ngành Hàng hải",
        "ai_response": "Chào bạn! Rất vui được gặp bạn. Tôi là Wiii, trợ lý học tập chuyên về luật và quy định hàng hải. Với tư cách là sinh viên năm 3, bạn đã học qua những môn gì rồi? Tôi có thể giúp bạn ôn tập COLREGs, SOLAS, hoặc bất kỳ chủ đề nào liên quan đến hàng hải.",
    },
    {
        "user_message": "Quy tắc 15 là gì?",
        "ai_response": """Quy tắc 15 của COLREGs quy định về **Tình huống cắt ngang (Crossing Situation)**.

**Nội dung chính:**
Khi hai tàu chạy bằng máy cắt ngang nhau và có nguy cơ va chạm, tàu nào có tàu kia ở bên mạn phải (starboard) của mình thì phải nhường đường.

**Các điểm quan trọng:**
- Chỉ áp dụng cho tàu chạy bằng máy (power-driven vessels)
- Phải có nguy cơ va chạm (risk of collision)
- Tàu nhường đường (give-way vessel) có tàu kia ở bên mạn phải
- Nếu có thể, tránh cắt ngang phía trước tàu kia

**Ví dụ thực tế:**
Nếu tàu A nhìn thấy tàu B đến từ bên phải (starboard), tàu A là tàu nhường đường và phải thay đổi hướng hoặc tốc độ để tránh va chạm.""",
    },
    {
        "user_message": "Tàu nhường đường phải làm gì?",
        "ai_response": "Theo COLREGs, tàu nhường đường (give-way vessel) phải thực hiện các hành động sau:\n\n**1. Thay đổi hướng và/hoặc tốc độ:**\n- Thực hiện sớm và đủ lớn để tàu còn lại nhận thấy rõ\n- Tránh các thay đổi nhỏ, dần dần (có thể gây hiểu lầm)\n\n**2. Tránh cắt ngang phía trước:**\n- Theo Quy tắc 15, nếu có thể, tránh cắt ngang phía trước tàu kia\n\n**3. Theo dõi liên tục:**\n- Kiểm tra xem hành động của mình có hiệu quả không\n- Sẵn sàng điều chỉnh nếu cần\n\n**4. Giảm tốc độ hoặc dừng lại:**\n- Nếu cần thiết để tránh va chạm\n\n**Lưu ý quan trọng:** Tàu nhường đường không được giả định tàu giữ đường sẽ hành động. Phải chủ động thực hiện hành động tránh va chạm.",
    }
]

TEST_USERS = [
    {
        "user_id": "test-student-001",
        "name": "Nguyễn Văn A",
        "role": "student",
        "year": 3,
        "interests": ["COLREGs", "Navigation"]
    },
    {
        "user_id": "test-teacher-001", 
        "name": "Trần Thị B",
        "role": "teacher",
        "department": "Maritime Studies"
    }
]


async def seed_postgres():
    """Seed PostgreSQL database with test data."""
    print("\n🐘 Seeding PostgreSQL...")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("⚠️  DATABASE_URL not set, skipping PostgreSQL seeding")
        return
    
    try:
        engine = create_async_engine(database_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            # Check if we can connect
            result = await session.execute(text("SELECT 1"))
            print("✅ Connected to PostgreSQL")
            
            # Create test chat sessions
            for user in TEST_USERS:
                session_id = str(uuid4())
                created_at = datetime.now() - timedelta(days=1)
                
                # Insert chat session
                await session.execute(
                    text("""
                        INSERT INTO chat_sessions (id, user_id, created_at, updated_at)
                        VALUES (:id, :user_id, :created_at, :updated_at)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": session_id,
                        "user_id": user["user_id"],
                        "created_at": created_at,
                        "updated_at": created_at
                    }
                )
                
                # Insert chat messages
                for i, chat in enumerate(SAMPLE_CHAT_HISTORY):
                    msg_time = created_at + timedelta(minutes=i*5)
                    
                    # User message
                    await session.execute(
                        text("""
                            INSERT INTO chat_messages 
                            (id, session_id, role, content, created_at, sequence)
                            VALUES (:id, :session_id, 'user', :content, :created_at, :sequence)
                            ON CONFLICT DO NOTHING
                        """),
                        {
                            "id": str(uuid4()),
                            "session_id": session_id,
                            "content": chat["user_message"],
                            "created_at": msg_time,
                            "sequence": i * 2
                        }
                    )
                    
                    # AI response
                    await session.execute(
                        text("""
                            INSERT INTO chat_messages 
                            (id, session_id, role, content, created_at, sequence)
                            VALUES (:id, :session_id, 'assistant', :content, :created_at, :sequence)
                            ON CONFLICT DO NOTHING
                        """),
                        {
                            "id": str(uuid4()),
                            "session_id": session_id,
                            "content": chat["ai_response"],
                            "created_at": msg_time + timedelta(seconds=30),
                            "sequence": i * 2 + 1
                        }
                    )
            
            await session.commit()
            print(f"✅ Seeded {len(TEST_USERS)} test users with chat history")
            
    except Exception as e:
        print(f"⚠️  PostgreSQL seeding failed: {e}")
        print("   This is OK if tables don't exist yet (run migrations first)")


async def seed_chroma():
    """Seed ChromaDB with sample documents."""
    print("\n🔍 Seeding ChromaDB...")
    
    try:
        import chromadb
        from chromadb.config import Settings
        
        chroma_host = os.getenv("CHROMA_HOST", "localhost")
        chroma_port = int(os.getenv("CHROMA_PORT", "8001"))
        
        client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        # Get or create collection
        collection = client.get_or_create_collection(
            name="maritime_knowledge",
            metadata={"description": "Maritime regulations and knowledge"}
        )
        
        # Add documents
        for i, doc in enumerate(SAMPLE_DOCUMENTS):
            collection.add(
                ids=[f"seed-doc-{i}"],
                documents=[doc["content"]],
                metadatas=[{
                    "title": doc["title"],
                    "source_type": doc["source_type"],
                    **doc["metadata"]
                }]
            )
        
        print(f"✅ Seeded {len(SAMPLE_DOCUMENTS)} documents to ChromaDB")
        
    except Exception as e:
        print(f"⚠️  ChromaDB seeding failed: {e}")


async def seed_neo4j():
    """Seed Neo4j with sample knowledge graph entities."""
    print("\n🕸️  Seeding Neo4j...")
    
    try:
        from neo4j import AsyncGraphDatabase
        
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j_secret")
        
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        
        async with driver.session() as session:
            # Create maritime concepts
            concepts = [
                {"name": "COLREGs", "type": "Regulation", "description": "International Regulations for Preventing Collisions at Sea"},
                {"name": "SOLAS", "type": "Regulation", "description": "International Convention for the Safety of Life at Sea"},
                {"name": "Rule 15", "type": "Rule", "description": "Crossing Situation"},
                {"name": "Rule 13", "type": "Rule", "description": "Overtaking"},
                {"name": "Give-way Vessel", "type": "Concept", "description": "Vessel required to take action to avoid collision"},
                {"name": "Stand-on Vessel", "type": "Concept", "description": "Vessel required to maintain course and speed"},
            ]
            
            for concept in concepts:
                await session.run(
                    """
                    MERGE (c:Concept {name: $name})
                    SET c.type = $type, c.description = $description
                    """,
                    concept
                )
            
            # Create relationships
            relationships = [
                ("Rule 15", "PART_OF", "COLREGs"),
                ("Rule 13", "PART_OF", "COLREGs"),
                ("Give-way Vessel", "DEFINED_IN", "Rule 15"),
                ("Stand-on Vessel", "DEFINED_IN", "Rule 15"),
            ]
            
            for source, rel_type, target in relationships:
                await session.run(
                    """
                    MATCH (s:Concept {name: $source})
                    MATCH (t:Concept {name: $target})
                    MERGE (s)-[r:%s]->(t)
                    """ % rel_type,
                    {"source": source, "target": target}
                )
            
            print(f"✅ Seeded {len(concepts)} concepts and {len(relationships)} relationships to Neo4j")
        
        await driver.close()
        
    except Exception as e:
        print(f"⚠️  Neo4j seeding failed: {e}")


async def main():
    """Main seeding function."""
    print("=" * 60)
    print("🌱 Wiii - Test Data Seeding")
    print("=" * 60)
    
    await seed_postgres()
    await seed_chroma()
    await seed_neo4j()
    
    print("\n" + "=" * 60)
    print("✅ Seeding complete!")
    print("=" * 60)
    print("\nTest Users:")
    for user in TEST_USERS:
        print(f"  • {user['user_id']} ({user.get('name', 'N/A')}) - {user.get('role', 'N/A')}")
    print("\nYou can now test the API with these users.")


if __name__ == "__main__":
    asyncio.run(main())
