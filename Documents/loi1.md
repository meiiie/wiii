2025-12-09T19:42:44.008183864Z ==> Build successful 🎉
2025-12-09T19:42:48.487588371Z ==> Deploying...
2025-12-09T19:43:31.741429956Z ==> Running 'gunicorn app.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:10000 --timeout 300 --keep-alive 5'
2025-12-09T19:43:41.421017729Z [2025-12-09 19:43:41 +0000] [56] [INFO] Starting gunicorn 21.2.0
2025-12-09T19:43:41.421574093Z [2025-12-09 19:43:41 +0000] [56] [INFO] Listening at: http://0.0.0.0:10000 (56)
2025-12-09T19:43:41.421779898Z [2025-12-09 19:43:41 +0000] [56] [INFO] Using worker: uvicorn.workers.UvicornWorker
2025-12-09T19:43:41.511324018Z [2025-12-09 19:43:41 +0000] [58] [INFO] Booting worker with pid: 58
2025-12-09T19:43:42.213869868Z [2025-12-09 19:43:42 +0000] [58] [INFO] Started server process [58]
2025-12-09T19:43:42.213887759Z [2025-12-09 19:43:42 +0000] [58] [INFO] Waiting for application startup.
2025-12-09T19:43:42.214127225Z 2025-12-09 19:43:42,213 - app.main - INFO - Starting Maritime AI Tutor v0.1.0
2025-12-09T19:43:42.21434027Z 2025-12-09 19:43:42,214 - app.main - INFO - Environment: production
2025-12-09T19:43:42.214484744Z 2025-12-09 19:43:42,214 - app.main - INFO - Debug mode: False
2025-12-09T19:43:42.723548235Z 2025-12-09 19:43:42,723 - app.core.database - INFO - Shared database engine created (Neon): pool_size=5, max_overflow=5, pool_timeout=30s
2025-12-09T19:43:42.724195911Z 2025-12-09 19:43:42,723 - app.core.database - INFO - Shared session factory created
2025-12-09T19:43:43.246541735Z 2025-12-09 19:43:43,246 - app.repositories.chat_history_repository - INFO - Using legacy schema (chat_sessions + chat_messages)
2025-12-09T19:43:43.248037642Z 2025-12-09 19:43:43,247 - app.repositories.chat_history_repository - INFO - Chat history repository using SHARED database engine
2025-12-09T19:43:43.248047213Z 2025-12-09 19:43:43,247 - app.main - INFO - ✅ PostgreSQL connection: Available
2025-12-09T19:43:45.749008681Z 2025-12-09 19:43:45,748 - app.repositories.neo4j_knowledge_repository - INFO - Neo4j connection established to neo4j+s://7f18fe6d.databases.neo4j.io
2025-12-09T19:43:45.749036571Z 2025-12-09 19:43:45,748 - app.main - INFO - ✅ Neo4j connection: Available
2025-12-09T19:43:45.749114644Z 2025-12-09 19:43:45,748 - app.repositories.semantic_memory_repository - INFO - SemanticMemoryRepository using SHARED database engine
2025-12-09T19:43:45.75615849Z 2025-12-09 19:43:45,756 - app.main - INFO - ✅ pgvector connection: Available
2025-12-09T19:43:45.912436568Z 2025-12-09 19:43:45,912 - app.prompts.prompt_loader - INFO - PromptLoader: Looking for YAML files in /opt/render/project/src/app/prompts
2025-12-09T19:43:45.912465019Z 2025-12-09 19:43:45,912 - app.prompts.prompt_loader - INFO - PromptLoader: Directory exists: True
2025-12-09T19:43:45.912839128Z 2025-12-09 19:43:45,912 - app.prompts.prompt_loader - INFO - PromptLoader: Found YAML files: ['tutor.yaml', 'assistant.yaml']
2025-12-09T19:43:46.018775468Z 2025-12-09 19:43:46,018 - app.prompts.prompt_loader - INFO - ✅ Loaded persona for role 'student' from tutor.yaml
2025-12-09T19:43:46.117299132Z 2025-12-09 19:43:46,117 - app.prompts.prompt_loader - INFO - ✅ Loaded persona for role 'teacher' from assistant.yaml
2025-12-09T19:43:46.216545784Z 2025-12-09 19:43:46,216 - app.prompts.prompt_loader - INFO - ✅ Loaded persona for role 'admin' from assistant.yaml
2025-12-09T19:43:46.216567064Z 2025-12-09 19:43:46,216 - app.prompts.prompt_loader - INFO - PromptLoader: Loaded 3/3 persona files
2025-12-09T19:43:46.216577215Z 2025-12-09 19:43:46,216 - app.main - INFO - ✅ PromptLoader initialized (persona YAML files checked)
2025-12-09T19:43:46.216582635Z 2025-12-09 19:43:46,216 - app.main - INFO - 🚀 Maritime AI Tutor started successfully
2025-12-09T19:43:46.216726878Z [2025-12-09 19:43:46 +0000] [58] [INFO] Application startup complete.
2025-12-09T19:43:46.218188235Z 127.0.0.1:47824 - "HEAD / HTTP/1.1" 405
2025-12-09T19:43:49.793245431Z ==> Your service is live 🎉
2025-12-09T19:43:49.983282705Z ==> 
2025-12-09T19:43:50.237851193Z ==> ///////////////////////////////////////////////////////////
2025-12-09T19:43:50.428555506Z ==> 
2025-12-09T19:43:50.611581731Z ==> Available at your primary URL https://maritime-ai-chatbot.onrender.com
2025-12-09T19:43:50.794845985Z ==> 
2025-12-09T19:43:50.978081159Z ==> ///////////////////////////////////////////////////////////
2025-12-09T19:43:52.754717991Z 14.249.192.241:0 - "GET /api/v1/health HTTP/1.1" 200
2025-12-09T19:43:52.974006526Z 35.230.45.39:0 - "GET / HTTP/1.1" 200
2025-12-09T19:43:53.819169203Z 14.249.192.241:0 - "GET /api/v1/knowledge/stats HTTP/1.1" 200
2025-12-09T19:43:54.227344991Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:43:54.383778364Z 2025-12-09 19:43:54,382 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:43:54.384550483Z 2025-12-09 19:43:54,384 - app.api.v1.chat - INFO - Chat request from user test-user (role: student, auth: api_key): Luật Hàng hải Việt Nam 2015 quy định những gì về t...
2025-12-09T19:44:02.338988872Z 2025-12-09 19:44:02,338 - app.repositories.neo4j_knowledge_repository - INFO - Neo4j connection established to neo4j+s://7f18fe6d.databases.neo4j.io
2025-12-09T19:44:02.339020043Z 2025-12-09 19:44:02,338 - app.engine.tools.rag_tool - INFO - Neo4j available (reserved for Learning Graph)
2025-12-09T19:44:02.345384552Z 2025-12-09 19:44:02,345 - app.repositories.learning_profile_repository - INFO - Learning profile repository using SHARED database engine
2025-12-09T19:44:02.43449417Z 2025-12-09 19:44:02,434 - app.repositories.chat_history_repository - INFO - Chat history tables created/verified
2025-12-09T19:44:02.434549722Z 2025-12-09 19:44:02,434 - app.services.chat_service - INFO - Memory Lite (Chat History) initialized
2025-12-09T19:44:02.434686855Z 2025-12-09 19:44:02,434 - app.engine.semantic_memory.core - INFO - SemanticMemoryEngine initialized (v0.5 - Refactored)
2025-12-09T19:44:02.434755477Z 2025-12-09 19:44:02,434 - app.services.chat_service - WARNING - Failed to initialize Semantic Memory: 'SemanticMemoryEngine' object has no attribute 'is_available'
2025-12-09T19:44:02.510630725Z 2025-12-09 19:44:02,445 - app.repositories.dense_search_repository - INFO - DenseSearchRepository initialized
2025-12-09T19:44:02.510724737Z 2025-12-09 19:44:02,510 - app.repositories.dense_search_repository - INFO - Created singleton DenseSearchRepository instance
2025-12-09T19:44:02.510870651Z 2025-12-09 19:44:02,510 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search repository initialized
2025-12-09T19:44:02.510971663Z 2025-12-09 19:44:02,510 - app.engine.rrf_reranker - INFO - RRFReranker initialized with k=60
2025-12-09T19:44:02.511073446Z 2025-12-09 19:44:02,510 - app.services.hybrid_search_service - INFO - HybridSearchService initialized with weights: dense=0.5, sparse=0.5, k=60
2025-12-09T19:44:09.51852077Z 2025-12-09 19:44:09,518 - app.engine.tools.rag_tool - INFO - RAG using Google Gemini: gemini-2.5-flash
2025-12-09T19:44:11.61450484Z 2025-12-09 19:44:11,614 - app.engine.unified_agent - INFO - UnifiedAgent using Gemini: gemini-2.5-flash
2025-12-09T19:44:11.622713945Z 2025-12-09 19:44:11,622 - app.engine.unified_agent - INFO - ✅ LLM bound with 3 tools
2025-12-09T19:44:11.622763546Z 2025-12-09 19:44:11,622 - app.engine.unified_agent - INFO - ✅ PromptLoader initialized for dynamic persona
2025-12-09T19:44:11.622775237Z 2025-12-09 19:44:11,622 - app.engine.unified_agent - INFO - UnifiedAgent initialized (Manual ReAct)
2025-12-09T19:44:11.622850439Z 2025-12-09 19:44:11,622 - app.services.chat_service - INFO - ✅ Unified Agent (CHỈ THỊ SỐ 13) initialized - LLM-driven orchestration ENABLED
2025-12-09T19:44:11.622877289Z 2025-12-09 19:44:11,622 - app.services.chat_service - INFO - ✅ PromptLoader (CHỈ THỊ SỐ 16) initialized - YAML Persona Config ENABLED
2025-12-09T19:44:12.219853769Z 2025-12-09 19:44:12,219 - app.engine.memory_summarizer - INFO - MemorySummarizer initialized with Gemini Flash
2025-12-09T19:44:12.21988102Z 2025-12-09 19:44:12,219 - app.services.chat_service - INFO - ✅ MemorySummarizer (CHỈ THỊ SỐ 16) initialized - Tiered Memory ENABLED
2025-12-09T19:44:12.818718917Z 2025-12-09 19:44:12,818 - app.engine.guardian_agent - INFO - GuardianAgent: LLM initialized (gemini-2.5-flash)
2025-12-09T19:44:12.818768708Z 2025-12-09 19:44:12,818 - app.engine.guardian_agent - INFO - GuardianAgent initialized
2025-12-09T19:44:12.818813129Z 2025-12-09 19:44:12,818 - app.services.chat_service - INFO - ✅ Guardian Agent (CHỈ THỊ SỐ 21) initialized - LLM Content Moderation ENABLED
2025-12-09T19:44:12.820406769Z 2025-12-09 19:44:12,819 - app.engine.conversation_analyzer - INFO - ConversationAnalyzer initialized
2025-12-09T19:44:12.820417259Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - ✅ Conversation Analyzer (CHỈ THỊ SỐ 21) initialized - Deep Reasoning ENABLED
2025-12-09T19:44:12.820420939Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - Knowledge graph available: True
2025-12-09T19:44:12.820423429Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - Chat history available: True
2025-12-09T19:44:12.820426039Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - Learning profile (PostgreSQL/Neon) available: True
2025-12-09T19:44:12.820428659Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - PromptLoader available: True
2025-12-09T19:44:12.820431379Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - MemorySummarizer available: True
2025-12-09T19:44:12.820433899Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - Semantic memory v0.3 available: False
2025-12-09T19:44:12.820655415Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - Unified Agent (ReAct) available: True
2025-12-09T19:44:12.820660565Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - Guardian Agent (LLM) available: True
2025-12-09T19:44:12.820663215Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - Conversation Analyzer available: True
2025-12-09T19:44:12.820666015Z 2025-12-09 19:44:12,820 - app.services.chat_service - INFO - ChatService initialized with all components
2025-12-09T19:44:12.936297007Z 2025-12-09 19:44:12,936 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:44:17.854793258Z 2025-12-09 19:44:17,854 - app.services.chat_service - INFO - Processing request for user test-user with role: student
2025-12-09T19:44:17.861945886Z 2025-12-09 19:44:17,861 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:44:17.861962737Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:44:17.861966147Z                                                              ^
2025-12-09T19:44:17.861968267Z 
2025-12-09T19:44:17.861970537Z [SQL: 
2025-12-09T19:44:17.861972767Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:44:17.861975057Z                                total_sessions, total_messages, updated_at
2025-12-09T19:44:17.861977847Z                         FROM learning_profile
2025-12-09T19:44:17.861980757Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:17.861985087Z                     ]
2025-12-09T19:44:17.861989327Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:44:17.861992727Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:17.867421293Z 2025-12-09 19:44:17,867 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:17.867433203Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:44:17.867435774Z                                         ^
2025-12-09T19:44:17.867449984Z 
2025-12-09T19:44:17.867452394Z [SQL: 
2025-12-09T19:44:17.867454574Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:44:17.867458444Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:44:17.867462274Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:44:17.867467144Z                     ]
2025-12-09T19:44:17.867470924Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:44:17.867474344Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:17.885165427Z 2025-12-09 19:44:17,885 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:44:17.885183737Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:44:17.885187527Z                                                              ^
2025-12-09T19:44:17.885189967Z 
2025-12-09T19:44:17.885192348Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:44:17.885195248Z FROM chat_messages 
2025-12-09T19:44:17.885198018Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:44:17.885200158Z  LIMIT %(param_1)s]
2025-12-09T19:44:17.885203028Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:44:17.885205258Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:17.894293605Z 2025-12-09 19:44:17,894 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test-user ---
2025-12-09T19:44:17.894307586Z 2025-12-09 19:44:17,894 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:44:17.894327016Z 2025-12-09 19:44:17,894 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:44:17.894368807Z 2025-12-09 19:44:17,894 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:44:17.894421078Z 2025-12-09 19:44:17,894 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:44:17.894428259Z 2025-12-09 19:44:17,894 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:44:17.903579587Z 2025-12-09 19:44:17,903 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:44:17.903589508Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:44:17.903592568Z                                                              ^
2025-12-09T19:44:17.903594518Z 
2025-12-09T19:44:17.903596838Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:44:17.903599348Z FROM chat_messages 
2025-12-09T19:44:17.903602008Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:44:17.903604198Z  LIMIT %(param_1)s]
2025-12-09T19:44:17.903606398Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:44:17.903608508Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:17.904669165Z 2025-12-09 19:44:17,904 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:44:19.662428596Z 2025-12-09 19:44:19,662 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'Luật Hàng hải Việt Nam 2015 quy định về tàu biển'})
2025-12-09T19:44:19.663113533Z 2025-12-09 19:44:19,662 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: Luật Hàng hải Việt Nam 2015 quy định về tàu biển
2025-12-09T19:44:19.663144744Z 2025-12-09 19:44:19,663 - app.services.hybrid_search_service - INFO - Hybrid search for: Luật Hàng hải Việt Nam 2015 quy định về tàu biển
2025-12-09T19:44:19.663586415Z 2025-12-09 19:44:19,663 - app.services.hybrid_search_service - INFO - Detected rule numbers: ['2015']
2025-12-09T19:44:20.116263446Z 2025-12-09 19:44:20,116 - app.engine.gemini_embedding - INFO - Initialized Gemini client with model: models/gemini-embedding-001
2025-12-09T19:44:20.43510407Z 2025-12-09 19:44:20,434 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:44:20.524383353Z 2025-12-09 19:44:20,524 - app.repositories.dense_search_repository - INFO - Created asyncpg connection pool (min=1, max=1)
2025-12-09T19:44:21.034588523Z 2025-12-09 19:44:21,034 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:44:21.037941297Z 2025-12-09 19:44:21,037 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:44:21.038124792Z 2025-12-09 19:44:21,038 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: luật | hàng | hải | việt | nam | 2015 | quy | rule | regulation | định | tàu | vessel | ship | biển
2025-12-09T19:44:21.175787515Z 2025-12-09 19:44:21,175 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: Luật Hàng hải Việt Nam 2015 quy định về tàu biển
2025-12-09T19:44:21.177848586Z 2025-12-09 19:44:21,177 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:44:21.178492752Z 2025-12-09 19:44:21,178 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (0 in both, 0 title-boosted)
2025-12-09T19:44:21.178507032Z 2025-12-09 19:44:21,178 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:44:21.178674477Z 2025-12-09 19:44:21,178 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: 1f56d2eb-7103-4ca1-b2ed-e6962a5a2f4d
2025-12-09T19:44:21.178736508Z 2025-12-09 19:44:21,178 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: 6c08feac-72c6-4f61-bad7-01a2fce774b6
2025-12-09T19:44:21.20439658Z 2025-12-09 19:44:21,204 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:44:23.833351219Z 2025-12-09 19:44:23,833 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:44:23.939496034Z 2025-12-09 19:44:23,939 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:44:23.939631927Z 2025-12-09 19:44:23,939 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:44:27.975923424Z 2025-12-09 19:44:27,975 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:44:27.975973605Z 2025-12-09 19:44:27,975 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'Luật Hàng hải Việt Nam 2015 quy định về tàu biển'}, 'result': 'Theo quy định tại Điều 13 của Bộ luật Hàng hải Việt Nam 2015, tàu biển được định nghĩa là phương tiệ'}]
2025-12-09T19:44:27.978361945Z 2025-12-09 19:44:27,978 - app.api.v1.chat - INFO - Chat response generated in 33.594s (agent: rag)
2025-12-09T19:44:27.978645622Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:44:27.994259532Z 2025-12-09 19:44:27,994 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:44:27.994279323Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:44:27.994286463Z                                                              ^
2025-12-09T19:44:27.994289263Z 
2025-12-09T19:44:27.994293213Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:44:27.994298663Z [parameters: {'id': UUID('122182de-789f-4834-95d3-f21f5549b226'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'user', 'content': 'Luật Hàng hải Việt Nam 2015 quy định những gì về tàu biển?', 'created_at': datetime.datetime(2025, 12, 9, 19, 44, 27, 989982, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:44:27.994301393Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:28.011106854Z 2025-12-09 19:44:28,010 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:44:28.011121284Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:44:28.011124964Z                                                              ^
2025-12-09T19:44:28.011127404Z 
2025-12-09T19:44:28.011130614Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:44:28.011135894Z [parameters: {'id': UUID('c09928b5-60e2-4db4-b665-2e14f43ce0d7'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'assistant', 'content': '<thinking>\nNgười dùng đang hỏi về quy định của Luật Hàng hải Việt Nam 2015 về tàu biển.\nDựa trên kết quả từ `tool_maritime_search`, Điều 13 của Bộ  ... (1428 characters truncated) ... n định rạch ròi để dễ quản lý và áp dụng các quy định liên quan đến an toàn, đăng kiểm, vận hành...\n\nCó chỗ nào bạn thấy chưa rõ không, cứ hỏi nhé!', 'created_at': datetime.datetime(2025, 12, 9, 19, 44, 27, 996307, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:44:28.011140925Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:28.017180376Z 2025-12-09 19:44:28,017 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:44:28.017195556Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:44:28.017198986Z                                                              ^
2025-12-09T19:44:28.017201516Z 
2025-12-09T19:44:28.017204186Z [SQL: 
2025-12-09T19:44:28.017206946Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:44:28.017210576Z                                total_sessions, total_messages, updated_at
2025-12-09T19:44:28.017214037Z                         FROM learning_profile
2025-12-09T19:44:28.017215857Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:28.017218146Z                     ]
2025-12-09T19:44:28.017242527Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:44:28.017246097Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:28.022683433Z 2025-12-09 19:44:28,022 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:28.022707694Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:44:28.022711784Z                                         ^
2025-12-09T19:44:28.022714194Z 
2025-12-09T19:44:28.022716894Z [SQL: 
2025-12-09T19:44:28.022723674Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:44:28.022725914Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:44:28.022727734Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:44:28.022730035Z                     ]
2025-12-09T19:44:28.022731864Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:44:28.022733555Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:28.028447247Z 2025-12-09 19:44:28,028 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:28.028460728Z LINE 5:                         WHERE user_id = 'test-user'
2025-12-09T19:44:28.028464028Z                                                 ^
2025-12-09T19:44:28.028466578Z 
2025-12-09T19:44:28.028469868Z [SQL: 
2025-12-09T19:44:28.028472928Z                         UPDATE learning_profile
2025-12-09T19:44:28.028476928Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:44:28.028479248Z                             updated_at = NOW()
2025-12-09T19:44:28.028480958Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:28.028483308Z                     ]
2025-12-09T19:44:28.028484968Z [parameters: {'messages': 2, 'user_id': 'test-user'}]
2025-12-09T19:44:28.028486678Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:28.454983445Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:44:28.617958801Z 2025-12-09 19:44:28,617 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:44:28.618571906Z 2025-12-09 19:44:28,618 - app.api.v1.chat - INFO - Chat request from user test-user (role: student, auth: api_key): Điều kiện để đăng ký tàu biển Việt Nam là gì?...
2025-12-09T19:44:28.62590801Z 2025-12-09 19:44:28,625 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:44:33.031619015Z 2025-12-09 19:44:33,031 - app.services.chat_service - INFO - Processing request for user test-user with role: student
2025-12-09T19:44:33.037496882Z 2025-12-09 19:44:33,037 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:44:33.037513253Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:44:33.037516383Z                                                              ^
2025-12-09T19:44:33.037518433Z 
2025-12-09T19:44:33.037520643Z [SQL: 
2025-12-09T19:44:33.037522873Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:44:33.037525173Z                                total_sessions, total_messages, updated_at
2025-12-09T19:44:33.037528073Z                         FROM learning_profile
2025-12-09T19:44:33.037530483Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:33.037549494Z                     ]
2025-12-09T19:44:33.037551814Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:44:33.037553964Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:33.043143154Z 2025-12-09 19:44:33,043 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:33.043158224Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:44:33.043161734Z                                         ^
2025-12-09T19:44:33.043164144Z 
2025-12-09T19:44:33.043166704Z [SQL: 
2025-12-09T19:44:33.043169364Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:44:33.043172504Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:44:33.043174644Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:44:33.043177634Z                     ]
2025-12-09T19:44:33.043180044Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:44:33.043182315Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:33.048893327Z 2025-12-09 19:44:33,048 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:44:33.048903807Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:44:33.048906448Z                                                              ^
2025-12-09T19:44:33.048908448Z 
2025-12-09T19:44:33.048910678Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:44:33.048913218Z FROM chat_messages 
2025-12-09T19:44:33.048915848Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:44:33.048917978Z  LIMIT %(param_1)s]
2025-12-09T19:44:33.048920848Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:44:33.048922988Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:33.054757154Z 2025-12-09 19:44:33,054 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test-user ---
2025-12-09T19:44:33.054769994Z 2025-12-09 19:44:33,054 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:44:33.054815455Z 2025-12-09 19:44:33,054 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:44:33.054819095Z 2025-12-09 19:44:33,054 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:44:33.054870627Z 2025-12-09 19:44:33,054 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:44:33.054919488Z 2025-12-09 19:44:33,054 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:44:33.060163539Z 2025-12-09 19:44:33,060 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:44:33.06018664Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:44:33.06019001Z                                                              ^
2025-12-09T19:44:33.06019208Z 
2025-12-09T19:44:33.06019463Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:44:33.06020763Z FROM chat_messages 
2025-12-09T19:44:33.06021075Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:44:33.06021291Z  LIMIT %(param_1)s]
2025-12-09T19:44:33.06021561Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:44:33.060217661Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:33.060411035Z 2025-12-09 19:44:33,060 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:44:34.366788198Z 2025-12-09 19:44:34,366 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'điều kiện đăng ký tàu biển Việt Nam'})
2025-12-09T19:44:34.367538766Z 2025-12-09 19:44:34,367 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:44:34.367616838Z 2025-12-09 19:44:34,367 - app.services.hybrid_search_service - INFO - Hybrid search for: điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:44:34.667616281Z 2025-12-09 19:44:34,667 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:44:34.770936055Z 2025-12-09 19:44:34,770 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:44:34.772545675Z 2025-12-09 19:44:34,772 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:44:34.772629297Z 2025-12-09 19:44:34,772 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: điều | rule | quy | tắc | regulation | kiện | đăng | ký | tàu | vessel | ship | biển | việt | nam
2025-12-09T19:44:34.921568372Z 2025-12-09 19:44:34,921 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:44:34.923587783Z 2025-12-09 19:44:34,923 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:44:34.923818389Z 2025-12-09 19:44:34,923 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (1 in both, 0 title-boosted)
2025-12-09T19:44:34.92387383Z 2025-12-09 19:44:34,923 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:44:34.924034074Z 2025-12-09 19:44:34,923 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: c8797f1b-7da6-4709-9d30-dd61931997a7
2025-12-09T19:44:34.924142597Z 2025-12-09 19:44:34,924 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: 9ec8b517-7a77-4ab3-8ada-91709ba2f474
2025-12-09T19:44:34.95823931Z 2025-12-09 19:44:34,958 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:44:38.228490298Z 2025-12-09 19:44:38,228 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:44:38.337708509Z 2025-12-09 19:44:38,337 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:44:38.337874843Z 2025-12-09 19:44:38,337 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:44:44.203167013Z 2025-12-09 19:44:44,202 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:44:44.203217314Z 2025-12-09 19:44:44,203 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'điều kiện đăng ký tàu biển Việt Nam'}, 'result': 'Theo Điều 20 của quy định, tàu biển khi đăng ký vào Sổ đăng ký tàu biển quốc gia Việt Nam phải đáp ứ'}]
2025-12-09T19:44:44.203646575Z 2025-12-09 19:44:44,203 - app.api.v1.chat - INFO - Chat response generated in 15.585s (agent: rag)
2025-12-09T19:44:44.203923352Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:44:44.210477136Z 2025-12-09 19:44:44,210 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:44:44.210491066Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:44:44.210494276Z                                                              ^
2025-12-09T19:44:44.210496446Z 
2025-12-09T19:44:44.210499436Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:44:44.210503967Z [parameters: {'id': UUID('a75f34ef-c84c-4f7b-8c03-f89c7de13f27'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'user', 'content': 'Điều kiện để đăng ký tàu biển Việt Nam là gì?', 'created_at': datetime.datetime(2025, 12, 9, 19, 44, 44, 206518, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:44:44.210506427Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:44.21705929Z 2025-12-09 19:44:44,216 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:44:44.217074641Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:44:44.217078831Z                                                              ^
2025-12-09T19:44:44.217081411Z 
2025-12-09T19:44:44.217084931Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:44:44.217090721Z [parameters: {'id': UUID('886590ee-efa8-4fab-b56b-cc9bfb15dd03'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'assistant', 'content': 'À này bạn, muốn đăng ký một con tàu mang cờ Việt Nam mình thì không phải cứ thích là được đâu nhé. Nó cũng có đủ các điều kiện ràng buộc chặt chẽ, y  ... (2093 characters truncated) ... thuật. Điều này cũng là để bảo vệ quyền lợi của chủ tàu, thủy thủ đoàn và đảm bảo an toàn hàng hải nói chung thôi. Có gì thắc mắc nữa cứ hỏi tôi nhé!', 'created_at': datetime.datetime(2025, 12, 9, 19, 44, 44, 213036, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:44:44.217094001Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:44.222660611Z 2025-12-09 19:44:44,222 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:44:44.222672141Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:44:44.222675221Z                                                              ^
2025-12-09T19:44:44.222677341Z 
2025-12-09T19:44:44.222679531Z [SQL: 
2025-12-09T19:44:44.222681871Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:44:44.222684321Z                                total_sessions, total_messages, updated_at
2025-12-09T19:44:44.222687111Z                         FROM learning_profile
2025-12-09T19:44:44.222701152Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:44.222704612Z                     ]
2025-12-09T19:44:44.222707162Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:44:44.222710012Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:44.227676266Z 2025-12-09 19:44:44,227 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:44.227692496Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:44:44.227695686Z                                         ^
2025-12-09T19:44:44.227697817Z 
2025-12-09T19:44:44.227700066Z [SQL: 
2025-12-09T19:44:44.227702326Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:44:44.227720177Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:44:44.227724387Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:44:44.227728227Z                     ]
2025-12-09T19:44:44.227731787Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:44:44.227735167Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:44.232996889Z 2025-12-09 19:44:44,232 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:44.233006819Z LINE 5:                         WHERE user_id = 'test-user'
2025-12-09T19:44:44.233009489Z                                                 ^
2025-12-09T19:44:44.233011619Z 
2025-12-09T19:44:44.23301379Z [SQL: 
2025-12-09T19:44:44.23301639Z                         UPDATE learning_profile
2025-12-09T19:44:44.23301879Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:44:44.23302086Z                             updated_at = NOW()
2025-12-09T19:44:44.23302296Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:44.23302538Z                     ]
2025-12-09T19:44:44.23302753Z [parameters: {'messages': 2, 'user_id': 'test-user'}]
2025-12-09T19:44:44.23302988Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:44.731573658Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:44:44.857537619Z 2025-12-09 19:44:44,857 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:44:44.858141634Z 2025-12-09 19:44:44,858 - app.api.v1.chat - INFO - Chat request from user test-user (role: student, auth: api_key): Còn về thuyền viên thì sao?...
2025-12-09T19:44:44.866504403Z 2025-12-09 19:44:44,866 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:44:49.582623352Z 2025-12-09 19:44:49,582 - app.services.chat_service - INFO - Processing request for user test-user with role: student
2025-12-09T19:44:49.588224842Z 2025-12-09 19:44:49,588 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:44:49.588244662Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:44:49.588250772Z                                                              ^
2025-12-09T19:44:49.588255223Z 
2025-12-09T19:44:49.588259593Z [SQL: 
2025-12-09T19:44:49.588262813Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:44:49.588265893Z                                total_sessions, total_messages, updated_at
2025-12-09T19:44:49.588294553Z                         FROM learning_profile
2025-12-09T19:44:49.588297644Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:49.588300644Z                     ]
2025-12-09T19:44:49.588303524Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:44:49.588306564Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:49.593616846Z 2025-12-09 19:44:49,593 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:49.593629817Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:44:49.593632987Z                                         ^
2025-12-09T19:44:49.593635147Z 
2025-12-09T19:44:49.593637407Z [SQL: 
2025-12-09T19:44:49.593639937Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:44:49.593642527Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:44:49.593644587Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:44:49.593648197Z                     ]
2025-12-09T19:44:49.593652098Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:44:49.593656278Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:49.599515074Z 2025-12-09 19:44:49,599 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:44:49.599531614Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:44:49.599536555Z                                                              ^
2025-12-09T19:44:49.599540055Z 
2025-12-09T19:44:49.599543815Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:44:49.599547665Z FROM chat_messages 
2025-12-09T19:44:49.599551545Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:44:49.599554915Z  LIMIT %(param_1)s]
2025-12-09T19:44:49.599559185Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:44:49.599562795Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:49.605002721Z 2025-12-09 19:44:49,604 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test-user ---
2025-12-09T19:44:49.605014842Z 2025-12-09 19:44:49,604 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:44:49.605021522Z 2025-12-09 19:44:49,604 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:44:49.605064963Z 2025-12-09 19:44:49,604 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:44:49.605109574Z 2025-12-09 19:44:49,605 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:44:49.605113274Z 2025-12-09 19:44:49,605 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:44:49.610515949Z 2025-12-09 19:44:49,610 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:44:49.6105298Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:44:49.61053457Z                                                              ^
2025-12-09T19:44:49.61055097Z 
2025-12-09T19:44:49.610555Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:44:49.61055878Z FROM chat_messages 
2025-12-09T19:44:49.610563121Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:44:49.610566941Z  LIMIT %(param_1)s]
2025-12-09T19:44:49.610570861Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:44:49.610574071Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:49.610765255Z 2025-12-09 19:44:49,610 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:44:53.14277507Z 2025-12-09 19:44:53,142 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:44:53.143016116Z 2025-12-09 19:44:53,142 - app.api.v1.chat - INFO - Chat response generated in 8.285s (agent: chat)
2025-12-09T19:44:53.143201891Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:44:53.14998819Z 2025-12-09 19:44:53,149 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:44:53.150008401Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:44:53.150013611Z                                                              ^
2025-12-09T19:44:53.150016921Z 
2025-12-09T19:44:53.150021151Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:44:53.150028322Z [parameters: {'id': UUID('a3b8e595-f882-4fd2-8c39-bdc0beea33dd'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'user', 'content': 'Còn về thuyền viên thì sao?', 'created_at': datetime.datetime(2025, 12, 9, 19, 44, 53, 145763, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:44:53.150031891Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:53.156118194Z 2025-12-09 19:44:53,155 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:44:53.156133174Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:44:53.156136444Z                                                              ^
2025-12-09T19:44:53.156138594Z 
2025-12-09T19:44:53.156141434Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:44:53.156146555Z [parameters: {'id': UUID('987227ba-2ea1-45e0-a6a9-91dc65ddb6e5'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'assistant', 'content': 'Nói về thuyền viên thì nhiều lắm bạn ơi! ⚓ Cả một thế giới trên biển ấy chứ. Bạn muốn biết cụ thể về khía cạnh nào nhỉ?\n\nVí dụ như là:\n*   **Điều  ... (260 characters truncated) ... an toàn, bảo hộ lao động cho anh em trên tàu?**\n\nCứ nói rõ ra, tôi sẽ chia sẻ kinh nghiệm cho bạn. Đề tài này tôi có thể nói cả ngày không hết đấy!', 'created_at': datetime.datetime(2025, 12, 9, 19, 44, 53, 152089, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:44:53.156152425Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:53.16158118Z 2025-12-09 19:44:53,161 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:44:53.161595331Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:44:53.161599411Z                                                              ^
2025-12-09T19:44:53.161601751Z 
2025-12-09T19:44:53.161604461Z [SQL: 
2025-12-09T19:44:53.161610621Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:44:53.161613491Z                                total_sessions, total_messages, updated_at
2025-12-09T19:44:53.161617191Z                         FROM learning_profile
2025-12-09T19:44:53.161620211Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:53.161623312Z                     ]
2025-12-09T19:44:53.161625921Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:44:53.161628602Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:44:53.166883423Z 2025-12-09 19:44:53,166 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:53.166899693Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:44:53.166903064Z                                         ^
2025-12-09T19:44:53.166905204Z 
2025-12-09T19:44:53.166907393Z [SQL: 
2025-12-09T19:44:53.166909634Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:44:53.166912374Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:44:53.166914434Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:44:53.166917164Z                     ]
2025-12-09T19:44:53.166919354Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:44:53.166921534Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:44:53.172149855Z 2025-12-09 19:44:53,172 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:44:53.172162165Z LINE 5:                         WHERE user_id = 'test-user'
2025-12-09T19:44:53.172165355Z                                                 ^
2025-12-09T19:44:53.172167875Z 
2025-12-09T19:44:53.172170485Z [SQL: 
2025-12-09T19:44:53.172173835Z                         UPDATE learning_profile
2025-12-09T19:44:53.172177325Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:44:53.172179785Z                             updated_at = NOW()
2025-12-09T19:44:53.172182296Z                         WHERE user_id = %(user_id)s
2025-12-09T19:44:53.172185786Z                     ]
2025-12-09T19:44:53.172188446Z [parameters: {'messages': 2, 'user_id': 'test-user'}]
2025-12-09T19:44:53.172191046Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:45:12.72597302Z 116.203.134.67:0 - "GET /api/v1/health HTTP/1.1" 200
2025-12-09T19:45:52.607472987Z 14.249.192.241:0 - "GET /api/v1/health HTTP/1.1" 200
2025-12-09T19:45:53.424276686Z 14.249.192.241:0 - "GET /api/v1/knowledge/stats HTTP/1.1" 200
2025-12-09T19:45:54.013396969Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:45:54.136788975Z 2025-12-09 19:45:54,136 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:45:54.137317629Z 2025-12-09 19:45:54,137 - app.api.v1.chat - INFO - Chat request from user test-user (role: student, auth: api_key): Luật Hàng hải Việt Nam 2015 quy định những gì về t...
2025-12-09T19:45:54.144034707Z 2025-12-09 19:45:54,143 - app.services.chat_service - INFO - Processing request for user test-user with role: student
2025-12-09T19:45:54.149297588Z 2025-12-09 19:45:54,149 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:45:54.149316759Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:45:54.149320669Z                                                              ^
2025-12-09T19:45:54.149323149Z 
2025-12-09T19:45:54.149326169Z [SQL: 
2025-12-09T19:45:54.149328779Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:45:54.149331349Z                                total_sessions, total_messages, updated_at
2025-12-09T19:45:54.149334849Z                         FROM learning_profile
2025-12-09T19:45:54.149337899Z                         WHERE user_id = %(user_id)s
2025-12-09T19:45:54.149341019Z                     ]
2025-12-09T19:45:54.149343989Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:45:54.14934688Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:54.154721954Z 2025-12-09 19:45:54,154 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:45:54.154738655Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:45:54.154781276Z                                         ^
2025-12-09T19:45:54.154785146Z 
2025-12-09T19:45:54.154788996Z [SQL: 
2025-12-09T19:45:54.154792906Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:45:54.154796846Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:45:54.154800056Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:45:54.154803516Z                     ]
2025-12-09T19:45:54.154806846Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:45:54.154810156Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:45:54.160285963Z 2025-12-09 19:45:54,160 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:45:54.160299623Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:45:54.160303334Z                                                              ^
2025-12-09T19:45:54.160305694Z 
2025-12-09T19:45:54.160308504Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:45:54.160311844Z FROM chat_messages 
2025-12-09T19:45:54.160316014Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:45:54.160318844Z  LIMIT %(param_1)s]
2025-12-09T19:45:54.160321584Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:45:54.160323794Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:54.165923714Z 2025-12-09 19:45:54,165 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test-user ---
2025-12-09T19:45:54.166003056Z 2025-12-09 19:45:54,165 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:45:54.166023037Z 2025-12-09 19:45:54,165 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:45:54.166076848Z 2025-12-09 19:45:54,165 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:45:54.166132499Z 2025-12-09 19:45:54,166 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:45:54.16614236Z 2025-12-09 19:45:54,166 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:45:54.171895953Z 2025-12-09 19:45:54,171 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:45:54.171909034Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:45:54.171912704Z                                                              ^
2025-12-09T19:45:54.171915204Z 
2025-12-09T19:45:54.171917874Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:45:54.171920924Z FROM chat_messages 
2025-12-09T19:45:54.171926624Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:45:54.171930104Z  LIMIT %(param_1)s]
2025-12-09T19:45:54.171932374Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:45:54.171934165Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:54.17215578Z 2025-12-09 19:45:54,172 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:45:56.366810278Z 2025-12-09 19:45:56,366 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:45:56.367085915Z 2025-12-09 19:45:56,366 - app.api.v1.chat - INFO - Chat response generated in 2.230s (agent: chat)
2025-12-09T19:45:56.36729546Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:45:56.374356167Z 2025-12-09 19:45:56,374 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:45:56.374390317Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:45:56.374397128Z                                                              ^
2025-12-09T19:45:56.374402138Z 
2025-12-09T19:45:56.374407978Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:45:56.374415198Z [parameters: {'id': UUID('dca87ae1-1390-4c08-9d9e-e9136a334c2e'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'user', 'content': 'Luật Hàng hải Việt Nam 2015 quy định những gì về tàu biển?', 'created_at': datetime.datetime(2025, 12, 9, 19, 45, 56, 369986, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:45:56.374420918Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:56.380667334Z 2025-12-09 19:45:56,380 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:45:56.380682035Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:45:56.380687655Z                                                              ^
2025-12-09T19:45:56.380691875Z 
2025-12-09T19:45:56.380696525Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:45:56.380714026Z [parameters: {'id': UUID('5957fad4-76a5-4a8d-918e-d3f2e453d974'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'assistant', 'content': "Về Luật Hàng hải Việt Nam 2015, nói chung thì nó quy định đầy đủ các khía cạnh liên quan đến 'tàu biển' đó bạn. Từ việc đăng ký, quốc tịch, thế chấp, ... (129 characters truncated) ... g luật này nhỉ? Ví dụ như quy định về **đăng ký và quốc tịch tàu biển** hay là **quy định về an toàn hàng hải**? Tôi sẽ tra cứu cho bạn chi tiết hơn.", 'created_at': datetime.datetime(2025, 12, 9, 19, 45, 56, 376299, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:45:56.380716166Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:56.386542371Z 2025-12-09 19:45:56,386 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:45:56.386555572Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:45:56.386559172Z                                                              ^
2025-12-09T19:45:56.386561352Z 
2025-12-09T19:45:56.386563702Z [SQL: 
2025-12-09T19:45:56.386565932Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:45:56.386568062Z                                total_sessions, total_messages, updated_at
2025-12-09T19:45:56.386570712Z                         FROM learning_profile
2025-12-09T19:45:56.386575012Z                         WHERE user_id = %(user_id)s
2025-12-09T19:45:56.386579762Z                     ]
2025-12-09T19:45:56.386584102Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:45:56.386587792Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:56.392191102Z 2025-12-09 19:45:56,392 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:45:56.392203923Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:45:56.392207883Z                                         ^
2025-12-09T19:45:56.392210413Z 
2025-12-09T19:45:56.392213153Z [SQL: 
2025-12-09T19:45:56.392216053Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:45:56.392219183Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:45:56.392221803Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:45:56.392224803Z                     ]
2025-12-09T19:45:56.392227663Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:45:56.392230463Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:45:56.39727445Z 2025-12-09 19:45:56,397 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:45:56.39728953Z LINE 5:                         WHERE user_id = 'test-user'
2025-12-09T19:45:56.39729355Z                                                 ^
2025-12-09T19:45:56.39729641Z 
2025-12-09T19:45:56.39729949Z [SQL: 
2025-12-09T19:45:56.397303321Z                         UPDATE learning_profile
2025-12-09T19:45:56.39730763Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:45:56.397321241Z                             updated_at = NOW()
2025-12-09T19:45:56.397323501Z                         WHERE user_id = %(user_id)s
2025-12-09T19:45:56.397326221Z                     ]
2025-12-09T19:45:56.397328341Z [parameters: {'messages': 2, 'user_id': 'test-user'}]
2025-12-09T19:45:56.397330471Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:45:56.894063474Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:45:56.973192123Z 2025-12-09 19:45:56,973 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:45:56.973783928Z 2025-12-09 19:45:56,973 - app.api.v1.chat - INFO - Chat request from user test-user (role: student, auth: api_key): Điều kiện để đăng ký tàu biển Việt Nam là gì?...
2025-12-09T19:45:56.980114126Z 2025-12-09 19:45:56,979 - app.services.chat_service - INFO - Processing request for user test-user with role: student
2025-12-09T19:45:56.985141812Z 2025-12-09 19:45:56,985 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:45:56.985154463Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:45:56.985157223Z                                                              ^
2025-12-09T19:45:56.985158912Z 
2025-12-09T19:45:56.985161653Z [SQL: 
2025-12-09T19:45:56.985165413Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:45:56.985168613Z                                total_sessions, total_messages, updated_at
2025-12-09T19:45:56.985171943Z                         FROM learning_profile
2025-12-09T19:45:56.985174523Z                         WHERE user_id = %(user_id)s
2025-12-09T19:45:56.985177843Z                     ]
2025-12-09T19:45:56.985180863Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:45:56.985183733Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:56.990441855Z 2025-12-09 19:45:56,990 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:45:56.990457615Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:45:56.990476266Z                                         ^
2025-12-09T19:45:56.990478846Z 
2025-12-09T19:45:56.990481426Z [SQL: 
2025-12-09T19:45:56.990484236Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:45:56.990487476Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:45:56.990490016Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:45:56.990493166Z                     ]
2025-12-09T19:45:56.990495926Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:45:56.990498426Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:45:56.996380153Z 2025-12-09 19:45:56,996 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:45:56.996395824Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:45:56.996399084Z                                                              ^
2025-12-09T19:45:56.996400764Z 
2025-12-09T19:45:56.996402644Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:45:56.996416724Z FROM chat_messages 
2025-12-09T19:45:56.996420574Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:45:56.996423284Z  LIMIT %(param_1)s]
2025-12-09T19:45:56.996426254Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:45:56.996428885Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:57.002335222Z 2025-12-09 19:45:57,002 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test-user ---
2025-12-09T19:45:57.002349422Z 2025-12-09 19:45:57,002 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:45:57.002357053Z 2025-12-09 19:45:57,002 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:45:57.002423484Z 2025-12-09 19:45:57,002 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:45:57.002432615Z 2025-12-09 19:45:57,002 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:45:57.002474476Z 2025-12-09 19:45:57,002 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:45:57.00785602Z 2025-12-09 19:45:57,007 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:45:57.007871091Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:45:57.007874581Z                                                              ^
2025-12-09T19:45:57.007876901Z 
2025-12-09T19:45:57.007880091Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:45:57.007883511Z FROM chat_messages 
2025-12-09T19:45:57.007886221Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:45:57.007888781Z  LIMIT %(param_1)s]
2025-12-09T19:45:57.007892041Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:45:57.007894701Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:45:57.008131947Z 2025-12-09 19:45:57,008 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:46:00.160088727Z 2025-12-09 19:46:00,159 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'Điều kiện đăng ký tàu biển Việt Nam'})
2025-12-09T19:46:00.160770494Z 2025-12-09 19:46:00,160 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: Điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:46:00.160795454Z 2025-12-09 19:46:00,160 - app.services.hybrid_search_service - INFO - Hybrid search for: Điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:46:00.472226423Z 2025-12-09 19:46:00,472 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:46:00.575165828Z 2025-12-09 19:46:00,575 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:46:00.576619064Z 2025-12-09 19:46:00,576 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:46:00.576729377Z 2025-12-09 19:46:00,576 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: điều | rule | quy | tắc | regulation | kiện | đăng | ký | tàu | vessel | ship | biển | việt | nam
2025-12-09T19:46:00.718243426Z 2025-12-09 19:46:00,718 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: Điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:46:00.719575709Z 2025-12-09 19:46:00,719 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:46:00.719828416Z 2025-12-09 19:46:00,719 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (1 in both, 0 title-boosted)
2025-12-09T19:46:00.719849666Z 2025-12-09 19:46:00,719 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:46:00.720029321Z 2025-12-09 19:46:00,719 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: c8797f1b-7da6-4709-9d30-dd61931997a7
2025-12-09T19:46:00.720078652Z 2025-12-09 19:46:00,720 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: 9ec8b517-7a77-4ab3-8ada-91709ba2f474
2025-12-09T19:46:00.761200921Z 2025-12-09 19:46:00,761 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:46:04.730379009Z 2025-12-09 19:46:04,730 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:46:04.826950804Z 2025-12-09 19:46:04,826 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:46:04.827120698Z 2025-12-09 19:46:04,827 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:46:09.762931632Z 2025-12-09 19:46:09,762 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:46:09.762976763Z 2025-12-09 19:46:09,762 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'Điều kiện đăng ký tàu biển Việt Nam'}, 'result': 'Theo Điều 20 của luật hàng hải, tàu biển khi đăng ký vào Sổ đăng ký tàu biển quốc gia Việt Nam phải '}]
2025-12-09T19:46:09.763469855Z 2025-12-09 19:46:09,763 - app.api.v1.chat - INFO - Chat response generated in 12.790s (agent: rag)
2025-12-09T19:46:09.763721362Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:46:09.770367408Z 2025-12-09 19:46:09,770 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:09.770383648Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:09.770389329Z                                                              ^
2025-12-09T19:46:09.770393869Z 
2025-12-09T19:46:09.770399149Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:09.770409689Z [parameters: {'id': UUID('6187d764-bfd8-4de7-9fc7-b855d893b7ff'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'user', 'content': 'Điều kiện để đăng ký tàu biển Việt Nam là gì?', 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 9, 766292, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:09.770414269Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:09.776498652Z 2025-12-09 19:46:09,776 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:09.776513702Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:09.776518212Z                                                              ^
2025-12-09T19:46:09.776535582Z 
2025-12-09T19:46:09.776538582Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:09.776545023Z [parameters: {'id': UUID('696b2335-0cdc-4691-9edd-3a50969081ac'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'assistant', 'content': '<thinking>\nNgười dùng đang hỏi về điều kiện để đăng ký tàu biển Việt Nam. Tôi đã sử dụng `tool_maritime_search` để lấy thông tin từ Luật Hàng hải. B ... (2379 characters truncated) ... u kiện nhưng mục đích chung là để đảm bảo tàu biển hoạt động an toàn, hiệu quả và có sự quản lý chặt chẽ của nhà nước. Có thắc mắc gì thêm không bạn?', 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 9, 772322, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:09.776549493Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:09.781583719Z 2025-12-09 19:46:09,781 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:09.781599479Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:09.781602539Z                                                              ^
2025-12-09T19:46:09.781604809Z 
2025-12-09T19:46:09.781607119Z [SQL: 
2025-12-09T19:46:09.781609419Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:09.781611509Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:09.781614269Z                         FROM learning_profile
2025-12-09T19:46:09.781616429Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:09.781619169Z                     ]
2025-12-09T19:46:09.78162128Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:46:09.78162349Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:09.786545713Z 2025-12-09 19:46:09,786 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:46:09.786559443Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:46:09.786563293Z                                         ^
2025-12-09T19:46:09.786565723Z 
2025-12-09T19:46:09.786568463Z [SQL: 
2025-12-09T19:46:09.786571363Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:09.786574933Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:09.786577893Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:09.786581884Z                     ]
2025-12-09T19:46:09.786583944Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:09.786585664Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:09.79163186Z 2025-12-09 19:46:09,791 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:46:09.79164932Z LINE 5:                         WHERE user_id = 'test-user'
2025-12-09T19:46:09.79165201Z                                                 ^
2025-12-09T19:46:09.79165406Z 
2025-12-09T19:46:09.791656251Z [SQL: 
2025-12-09T19:46:09.79165928Z                         UPDATE learning_profile
2025-12-09T19:46:09.791661991Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:46:09.791679331Z                             updated_at = NOW()
2025-12-09T19:46:09.791683261Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:09.791687241Z                     ]
2025-12-09T19:46:09.791690781Z [parameters: {'messages': 2, 'user_id': 'test-user'}]
2025-12-09T19:46:09.791694612Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:10.22268646Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:46:10.312452145Z 2025-12-09 19:46:10,312 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:46:10.312958698Z 2025-12-09 19:46:10,312 - app.api.v1.chat - INFO - Chat request from user test-user (role: student, auth: api_key): Còn về thuyền viên thì sao?...
2025-12-09T19:46:10.319222535Z 2025-12-09 19:46:10,319 - app.services.chat_service - INFO - Processing request for user test-user with role: student
2025-12-09T19:46:10.324419805Z 2025-12-09 19:46:10,324 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:10.324437835Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:10.324441605Z                                                              ^
2025-12-09T19:46:10.324443925Z 
2025-12-09T19:46:10.324446836Z [SQL: 
2025-12-09T19:46:10.324449476Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:10.324451976Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:10.324455576Z                         FROM learning_profile
2025-12-09T19:46:10.324458146Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:10.324461556Z                     ]
2025-12-09T19:46:10.324464366Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:46:10.324467166Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:10.329611795Z 2025-12-09 19:46:10,329 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:46:10.329626765Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:46:10.329631535Z                                         ^
2025-12-09T19:46:10.329634735Z 
2025-12-09T19:46:10.329638185Z [SQL: 
2025-12-09T19:46:10.329641875Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:10.329646126Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:10.329649876Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:10.329653606Z                     ]
2025-12-09T19:46:10.329655796Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:10.329657986Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:10.335148573Z 2025-12-09 19:46:10,335 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:10.335163113Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:10.335167624Z                                                              ^
2025-12-09T19:46:10.335170304Z 
2025-12-09T19:46:10.335173014Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:10.335189024Z FROM chat_messages 
2025-12-09T19:46:10.335193034Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:10.335195554Z  LIMIT %(param_1)s]
2025-12-09T19:46:10.335199005Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:46:10.335201825Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:10.340868066Z 2025-12-09 19:46:10,340 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test-user ---
2025-12-09T19:46:10.340900527Z 2025-12-09 19:46:10,340 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:46:10.340921457Z 2025-12-09 19:46:10,340 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:46:10.34100951Z 2025-12-09 19:46:10,340 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:46:10.34101553Z 2025-12-09 19:46:10,340 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:46:10.34102843Z 2025-12-09 19:46:10,340 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:46:10.346387954Z 2025-12-09 19:46:10,346 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:10.346400285Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:10.346403825Z                                                              ^
2025-12-09T19:46:10.346406065Z 
2025-12-09T19:46:10.346408625Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:10.346411655Z FROM chat_messages 
2025-12-09T19:46:10.346414975Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:10.346417575Z  LIMIT %(param_1)s]
2025-12-09T19:46:10.346420825Z [parameters: {'session_id_1': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'param_1': 50}]
2025-12-09T19:46:10.346423445Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:10.346655511Z 2025-12-09 19:46:10,346 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:46:13.102968206Z 2025-12-09 19:46:13,102 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:46:13.103198532Z 2025-12-09 19:46:13,103 - app.api.v1.chat - INFO - Chat response generated in 2.790s (agent: chat)
2025-12-09T19:46:13.103395906Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:46:13.110247138Z 2025-12-09 19:46:13,110 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:13.110264218Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:13.110278759Z                                                              ^
2025-12-09T19:46:13.110281569Z 
2025-12-09T19:46:13.110286389Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:13.110292579Z [parameters: {'id': UUID('320e8a53-d896-460d-8ef6-46a86d724391'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'user', 'content': 'Còn về thuyền viên thì sao?', 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 13, 106382, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:13.11031445Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:13.115981231Z 2025-12-09 19:46:13,115 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:13.115998772Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:13.116003012Z                                                              ^
2025-12-09T19:46:13.116006272Z 
2025-12-09T19:46:13.116010002Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:13.116016162Z [parameters: {'id': UUID('c4e0a28c-fcc0-4668-9a76-4fb103ef2dc8'), 'session_id': UUID('b0f6b8ec-e7bd-4a92-aaa1-0cdcf85e88a9'), 'role': 'assistant', 'content': 'Nói về thuyền viên thì nhiều lắm bạn ơi! ⚓ Cả một thế giới trên biển đó. Từ trách nhiệm, quyền lợi, rồi đến các quy định về giờ làm, giờ nghỉ, ăn ở,  ... (104 characters truncated) ...  dụ như **Quy định về định biên an toàn** chẳng hạn, hay là **tiêu chuẩn đào tạo, chứng chỉ**? Cứ nói rõ, tôi sẽ cùng bạn "phá sóng" từng vấn đề một!', 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 13, 112127, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:13.116019912Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:13.116891154Z 2025-12-09 19:46:13,116 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:46:14.297429459Z 2025-12-09 19:46:14,297 - app.engine.memory_summarizer - INFO - Async summarized 4 messages
2025-12-09T19:46:14.303215074Z 2025-12-09 19:46:14,303 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:14.303231154Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:14.303234944Z                                                              ^
2025-12-09T19:46:14.303237774Z 
2025-12-09T19:46:14.303240664Z [SQL: 
2025-12-09T19:46:14.303243885Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:14.303246505Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:14.303250234Z                         FROM learning_profile
2025-12-09T19:46:14.303253095Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:14.303256525Z                     ]
2025-12-09T19:46:14.303259215Z [parameters: {'user_id': 'test-user'}]
2025-12-09T19:46:14.303262105Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:14.308811364Z 2025-12-09 19:46:14,308 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:46:14.308847274Z LINE 3:                         VALUES ('test-user', '{"level": "beg...
2025-12-09T19:46:14.308851665Z                                         ^
2025-12-09T19:46:14.308854525Z 
2025-12-09T19:46:14.308857185Z [SQL: 
2025-12-09T19:46:14.308859985Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:14.308863475Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:14.308866365Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:14.308884155Z                     ]
2025-12-09T19:46:14.308888086Z [parameters: {'user_id': 'test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:14.308891176Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:14.314905506Z 2025-12-09 19:46:14,314 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test-user"
2025-12-09T19:46:14.314934247Z LINE 5:                         WHERE user_id = 'test-user'
2025-12-09T19:46:14.314937077Z                                                 ^
2025-12-09T19:46:14.314938867Z 
2025-12-09T19:46:14.314940617Z [SQL: 
2025-12-09T19:46:14.314943757Z                         UPDATE learning_profile
2025-12-09T19:46:14.314947577Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:46:14.314949647Z                             updated_at = NOW()
2025-12-09T19:46:14.314952077Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:14.314955787Z                     ]
2025-12-09T19:46:14.314958427Z [parameters: {'messages': 2, 'user_id': 'test-user'}]
2025-12-09T19:46:14.314961207Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:24.780388716Z 14.249.192.241:0 - "GET /health HTTP/1.1" 200
2025-12-09T19:46:24.864602952Z 2025-12-09 19:46:24,864 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:46:24.865151956Z 2025-12-09 19:46:24,865 - app.api.v1.chat - INFO - Chat request from user test_flow_20251210_024623 (role: student, auth: api_key): Xin chào, tôi là Hùng, sinh viên năm 3 Đại học Hàn...
2025-12-09T19:46:24.878204292Z 2025-12-09 19:46:24,878 - app.repositories.chat_history_repository - INFO - Created new chat session for user test_flow_20251210_024623
2025-12-09T19:46:24.88613816Z 2025-12-09 19:46:24,886 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:46:29.925948235Z 2025-12-09 19:46:29,925 - app.services.chat_service - INFO - Processing request for user test_flow_20251210_024623 with role: student
2025-12-09T19:46:29.931444783Z 2025-12-09 19:46:29,931 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:29.931462713Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:29.931467603Z                                                              ^
2025-12-09T19:46:29.931471073Z 
2025-12-09T19:46:29.931475053Z [SQL: 
2025-12-09T19:46:29.931478693Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:29.931482153Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:29.931486293Z                         FROM learning_profile
2025-12-09T19:46:29.931489813Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:29.931494284Z                     ]
2025-12-09T19:46:29.931497784Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:46:29.931501294Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:29.936866008Z 2025-12-09 19:46:29,936 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:46:29.936883068Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:46:29.936889428Z                                         ^
2025-12-09T19:46:29.936909779Z 
2025-12-09T19:46:29.936912629Z [SQL: 
2025-12-09T19:46:29.936914939Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:29.936917869Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:29.936920049Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:29.936922949Z                     ]
2025-12-09T19:46:29.936925829Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:29.936928429Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:29.942387176Z 2025-12-09 19:46:29,942 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:29.942399446Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:29.942402577Z                                                              ^
2025-12-09T19:46:29.942404767Z 
2025-12-09T19:46:29.942407027Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:29.942409517Z FROM chat_messages 
2025-12-09T19:46:29.942412247Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:29.942414397Z  LIMIT %(param_1)s]
2025-12-09T19:46:29.942417317Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:46:29.942419537Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:29.960339265Z 2025-12-09 19:46:29,960 - app.repositories.chat_history_repository - INFO - Updated user name to 'Hùng'
2025-12-09T19:46:29.960374646Z 2025-12-09 19:46:29,960 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test_flow_20251210_024623 ---
2025-12-09T19:46:29.960449238Z 2025-12-09 19:46:29,960 - app.services.chat_service - INFO - Detected Name: Hùng
2025-12-09T19:46:29.960460928Z 2025-12-09 19:46:29,960 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:46:29.96053699Z 2025-12-09 19:46:29,960 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:46:29.96054601Z 2025-12-09 19:46:29,960 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:46:29.960669033Z 2025-12-09 19:46:29,960 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:46:29.96651706Z 2025-12-09 19:46:29,966 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:29.96653042Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:29.9665341Z                                                              ^
2025-12-09T19:46:29.96653629Z 
2025-12-09T19:46:29.96653863Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:29.9665416Z FROM chat_messages 
2025-12-09T19:46:29.9665443Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:29.96654646Z  LIMIT %(param_1)s]
2025-12-09T19:46:29.96655217Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:46:29.96655445Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:29.966797597Z 2025-12-09 19:46:29,966 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:46:31.684582048Z 2025-12-09 19:46:31,684 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_save_user_info({'key': 'name', 'value': 'Hùng'})
2025-12-09T19:46:31.685243265Z 2025-12-09 19:46:31,685 - app.engine.unified_agent - INFO - [TOOL] Save User Info: name=Hùng for user test_flow_20251210_024623
2025-12-09T19:46:31.685370308Z 2025-12-09 19:46:31,685 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_save_user_info({'key': 'academic_year', 'value': 'năm 3'})
2025-12-09T19:46:31.685825529Z 2025-12-09 19:46:31,685 - app.engine.unified_agent - INFO - [TOOL] Save User Info: academic_year=năm 3 for user test_flow_20251210_024623
2025-12-09T19:46:31.685926442Z 2025-12-09 19:46:31,685 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_save_user_info({'value': 'Đại học Hàng hải', 'key': 'university'})
2025-12-09T19:46:31.686362113Z 2025-12-09 19:46:31,686 - app.engine.unified_agent - INFO - [TOOL] Save User Info: university=Đại học Hàng hải for user test_flow_20251210_024623
2025-12-09T19:46:31.686436855Z 2025-12-09 19:46:31,686 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:46:33.628875944Z 2025-12-09 19:46:33,628 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_save_user_info', 'args': {'key': 'name', 'value': 'Hùng'}, 'result': 'Đã ghi nhớ (cache only): name = Hùng'}, {'name': 'tool_save_user_info', 'args': {'key': 'academic_year', 'value': 'năm 3'}, 'result': 'Đã ghi nhớ (cache only): academic_year = năm 3'}, {'name': 'tool_save_user_info', 'args': {'value': 'Đại học Hàng hải', 'key': 'university'}, 'result': 'Đã ghi nhớ (cache only): university = Đại học Hàng hải'}]
2025-12-09T19:46:33.629161592Z 2025-12-09 19:46:33,629 - app.api.v1.chat - INFO - Chat response generated in 8.764s (agent: chat)
2025-12-09T19:46:33.629394197Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:46:33.636356702Z 2025-12-09 19:46:33,636 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:33.636375222Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:33.636380742Z                                                              ^
2025-12-09T19:46:33.636384492Z 
2025-12-09T19:46:33.636389103Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:33.636395383Z [parameters: {'id': UUID('3a1b9302-0742-4ec6-b8dc-0bc3063ca555'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'user', 'content': 'Xin chào, tôi là Hùng, sinh viên năm 3 Đại học Hàng hải', 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 33, 631996, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:33.636399563Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:33.642413273Z 2025-12-09 19:46:33,642 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:33.642427894Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:33.642433454Z                                                              ^
2025-12-09T19:46:33.642437934Z 
2025-12-09T19:46:33.642443264Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:33.642464844Z [parameters: {'id': UUID('9ba2a070-737d-41ee-934c-7e2c802847cf'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'assistant', 'content': "<thinking>\nThe user, Hùng, has introduced himself as a 3rd-year student at the Maritime University. I have successfully saved this information using ... (449 characters truncated) ...  đại cương nữa. Rất vui được làm quen và đồng hành cùng bạn. Hôm nay bạn định 'cày' phần nào của luật hàng hải hay kỹ thuật tàu biển, cứ hỏi tôi nhé!", 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 33, 638139, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:33.642468304Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:33.647969652Z 2025-12-09 19:46:33,647 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:33.647991653Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:33.647995713Z                                                              ^
2025-12-09T19:46:33.647998653Z 
2025-12-09T19:46:33.648001353Z [SQL: 
2025-12-09T19:46:33.648003223Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:33.648005083Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:33.648008383Z                         FROM learning_profile
2025-12-09T19:46:33.648011443Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:33.648014183Z                     ]
2025-12-09T19:46:33.648016293Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:46:33.648018713Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:33.653178262Z 2025-12-09 19:46:33,653 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:46:33.653187412Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:46:33.653190803Z                                         ^
2025-12-09T19:46:33.653193193Z 
2025-12-09T19:46:33.653195623Z [SQL: 
2025-12-09T19:46:33.653198173Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:33.653201073Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:33.653203663Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:33.653206963Z                     ]
2025-12-09T19:46:33.653210273Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:33.653212753Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:33.658386042Z 2025-12-09 19:46:33,658 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:46:33.658396613Z LINE 5:                         WHERE user_id = 'test_flow_20251210_...
2025-12-09T19:46:33.658399943Z                                                 ^
2025-12-09T19:46:33.658402163Z 
2025-12-09T19:46:33.658404483Z [SQL: 
2025-12-09T19:46:33.658407153Z                         UPDATE learning_profile
2025-12-09T19:46:33.658409433Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:46:33.658422203Z                             updated_at = NOW()
2025-12-09T19:46:33.658425094Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:33.658437564Z                     ]
2025-12-09T19:46:33.658439894Z [parameters: {'messages': 2, 'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:46:33.658442584Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:35.729990393Z 2025-12-09 19:46:35,729 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:46:35.730711441Z 2025-12-09 19:46:35,730 - app.api.v1.chat - INFO - Chat request from user test_flow_20251210_024623 (role: student, auth: api_key): Giải thích quy tắc 15 COLREGs về tình huống cắt hư...
2025-12-09T19:46:35.738363702Z 2025-12-09 19:46:35,738 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:46:39.349569858Z 2025-12-09 19:46:39,349 - app.services.chat_service - INFO - Processing request for user test_flow_20251210_024623 with role: student
2025-12-09T19:46:39.355768543Z 2025-12-09 19:46:39,355 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:39.355790644Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:39.355797554Z                                                              ^
2025-12-09T19:46:39.355801134Z 
2025-12-09T19:46:39.355804824Z [SQL: 
2025-12-09T19:46:39.355808674Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:39.355812214Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:39.355816364Z                         FROM learning_profile
2025-12-09T19:46:39.355819864Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:39.355823864Z                     ]
2025-12-09T19:46:39.355827334Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:46:39.355830814Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:39.361714262Z 2025-12-09 19:46:39,361 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:46:39.361732602Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:46:39.361738352Z                                         ^
2025-12-09T19:46:39.361760693Z 
2025-12-09T19:46:39.361766963Z [SQL: 
2025-12-09T19:46:39.361771773Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:39.361776163Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:39.361780593Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:39.361785163Z                     ]
2025-12-09T19:46:39.361793854Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:39.361798254Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:39.367107067Z 2025-12-09 19:46:39,366 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:39.367122377Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:39.367127287Z                                                              ^
2025-12-09T19:46:39.367130917Z 
2025-12-09T19:46:39.367134947Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:39.367171648Z FROM chat_messages 
2025-12-09T19:46:39.367175308Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:39.367177468Z  LIMIT %(param_1)s]
2025-12-09T19:46:39.367180398Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:46:39.367182558Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:39.373443455Z 2025-12-09 19:46:39,373 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test_flow_20251210_024623 ---
2025-12-09T19:46:39.373464706Z 2025-12-09 19:46:39,373 - app.services.chat_service - INFO - Detected Name: Hùng
2025-12-09T19:46:39.37363704Z 2025-12-09 19:46:39,373 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:46:39.37364556Z 2025-12-09 19:46:39,373 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:46:39.37365464Z 2025-12-09 19:46:39,373 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:46:39.373732862Z 2025-12-09 19:46:39,373 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:46:39.379545958Z 2025-12-09 19:46:39,379 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:39.379559598Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:39.379562858Z                                                              ^
2025-12-09T19:46:39.379565448Z 
2025-12-09T19:46:39.379568428Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:39.379571818Z FROM chat_messages 
2025-12-09T19:46:39.379575998Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:39.379578948Z  LIMIT %(param_1)s]
2025-12-09T19:46:39.379582368Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:46:39.379585079Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:39.379936837Z 2025-12-09 19:46:39,379 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:46:41.577957859Z 2025-12-09 19:46:41,577 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'Rule 15 COLREGs crossing situation'})
2025-12-09T19:46:41.581129139Z 2025-12-09 19:46:41,578 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: Rule 15 COLREGs crossing situation
2025-12-09T19:46:41.581146349Z 2025-12-09 19:46:41,578 - app.services.hybrid_search_service - INFO - Hybrid search for: Rule 15 COLREGs crossing situation
2025-12-09T19:46:41.581151729Z 2025-12-09 19:46:41,578 - app.services.hybrid_search_service - INFO - Detected rule numbers: ['15']
2025-12-09T19:46:41.891045759Z 2025-12-09 19:46:41,890 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:46:41.994859566Z 2025-12-09 19:46:41,994 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:46:41.996551358Z 2025-12-09 19:46:41,996 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:46:41.99664218Z 2025-12-09 19:46:41,996 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: rule | quy | tắc | regulation | điều | 15 | colregs | crossing | cắt | hướng | situation
2025-12-09T19:46:42.137874683Z 2025-12-09 19:46:42,137 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: Rule 15 COLREGs crossing situation
2025-12-09T19:46:42.210849388Z 2025-12-09 19:46:42,139 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:46:42.211491504Z 2025-12-09 19:46:42,210 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (0 in both, 5 title-boosted)
2025-12-09T19:46:42.211498234Z 2025-12-09 19:46:42,211 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:46:42.280029458Z 2025-12-09 19:46:42,279 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:46:45.600444321Z 2025-12-09 19:46:45,600 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:46:45.730691438Z 2025-12-09 19:46:45,730 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:46:45.730880113Z 2025-12-09 19:46:45,730 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:46:53.856485223Z 2025-12-09 19:46:53,856 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:46:53.856517684Z 2025-12-09 19:46:53,856 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'Rule 15 COLREGs crossing situation'}, 'result': 'Theo kiến thức tra cứu được, thông tin về "Rule 15 COLREGs crossing situation" không có sẵn. Kiến th'}]
2025-12-09T19:46:53.856979835Z 2025-12-09 19:46:53,856 - app.api.v1.chat - INFO - Chat response generated in 18.126s (agent: rag)
2025-12-09T19:46:53.857241552Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:46:53.863858827Z 2025-12-09 19:46:53,863 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:53.863875888Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:53.863880928Z                                                              ^
2025-12-09T19:46:53.863883808Z 
2025-12-09T19:46:53.863887368Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:53.863892278Z [parameters: {'id': UUID('61fffa23-cc69-4e55-8619-9db9c5adda61'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'user', 'content': 'Giải thích quy tắc 15 COLREGs về tình huống cắt hướng', 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 53, 859864, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:53.863895408Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:53.869682663Z 2025-12-09 19:46:53,869 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:46:53.869696463Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:46:53.869700294Z                                                              ^
2025-12-09T19:46:53.869703134Z 
2025-12-09T19:46:53.869706624Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:46:53.869723214Z [parameters: {'id': UUID('1991f45d-efd6-496a-b549-618bcec8d20b'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'assistant', 'content': '<thinking>\nThe user is asking for an explanation of Rule 15 of COLREGs regarding a crossing situation.\nI attempted to use `tool_maritime_search` wi ... (1099 characters truncated) ... ould try something like "Nói về tình huống cắt hướng..." or "Về Quy tắc 15 này...". I will go with "Nói về **Quy tắc 15 (Crossing Situation)** này,".', 'created_at': datetime.datetime(2025, 12, 9, 19, 46, 53, 865591, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:46:53.869725574Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:53.875718564Z 2025-12-09 19:46:53,875 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:53.875731324Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:53.875735065Z                                                              ^
2025-12-09T19:46:53.875737605Z 
2025-12-09T19:46:53.875740165Z [SQL: 
2025-12-09T19:46:53.875760945Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:53.875764125Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:53.875769385Z                         FROM learning_profile
2025-12-09T19:46:53.875772125Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:53.875775555Z                     ]
2025-12-09T19:46:53.875778315Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:46:53.875780835Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:53.881325194Z 2025-12-09 19:46:53,881 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:46:53.881335665Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:46:53.881339525Z                                         ^
2025-12-09T19:46:53.881342185Z 
2025-12-09T19:46:53.881344985Z [SQL: 
2025-12-09T19:46:53.881348045Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:53.881350805Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:53.881353595Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:53.881356585Z                     ]
2025-12-09T19:46:53.881360055Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:53.881362955Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:53.886919654Z 2025-12-09 19:46:53,886 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:46:53.886942155Z LINE 5:                         WHERE user_id = 'test_flow_20251210_...
2025-12-09T19:46:53.886946685Z                                                 ^
2025-12-09T19:46:53.886949235Z 
2025-12-09T19:46:53.886951815Z [SQL: 
2025-12-09T19:46:53.886957235Z                         UPDATE learning_profile
2025-12-09T19:46:53.886960175Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:46:53.886963075Z                             updated_at = NOW()
2025-12-09T19:46:53.886965835Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:53.886983426Z                     ]
2025-12-09T19:46:53.886986326Z [parameters: {'messages': 2, 'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:46:53.886988956Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:55.965963671Z 2025-12-09 19:46:55,965 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:46:55.966416322Z 2025-12-09 19:46:55,966 - app.api.v1.chat - INFO - Chat request from user test_flow_20251210_024623 (role: student, auth: api_key): Còn quy tắc 16 thì sao?...
2025-12-09T19:46:55.973465908Z 2025-12-09 19:46:55,973 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:46:59.403484633Z 2025-12-09 19:46:59,403 - app.services.chat_service - INFO - Processing request for user test_flow_20251210_024623 with role: student
2025-12-09T19:46:59.409064942Z 2025-12-09 19:46:59,408 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:46:59.409091853Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:46:59.409276387Z                                                              ^
2025-12-09T19:46:59.409292768Z 
2025-12-09T19:46:59.409297928Z [SQL: 
2025-12-09T19:46:59.409303458Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:46:59.409313368Z                                total_sessions, total_messages, updated_at
2025-12-09T19:46:59.409319848Z                         FROM learning_profile
2025-12-09T19:46:59.409325848Z                         WHERE user_id = %(user_id)s
2025-12-09T19:46:59.409331369Z                     ]
2025-12-09T19:46:59.409336279Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:46:59.409341129Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:59.415298458Z 2025-12-09 19:46:59,415 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:46:59.415315378Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:46:59.415319929Z                                         ^
2025-12-09T19:46:59.415323449Z 
2025-12-09T19:46:59.415327009Z [SQL: 
2025-12-09T19:46:59.415330599Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:46:59.415334829Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:46:59.415338279Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:46:59.415342519Z                     ]
2025-12-09T19:46:59.415346529Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:46:59.415350089Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:46:59.421562014Z 2025-12-09 19:46:59,421 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:59.421578705Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:59.421585295Z                                                              ^
2025-12-09T19:46:59.421590525Z 
2025-12-09T19:46:59.421595685Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:59.421602066Z FROM chat_messages 
2025-12-09T19:46:59.421624726Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:59.421628316Z  LIMIT %(param_1)s]
2025-12-09T19:46:59.421632216Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:46:59.421635916Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:59.427098033Z 2025-12-09 19:46:59,426 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test_flow_20251210_024623 ---
2025-12-09T19:46:59.427128874Z 2025-12-09 19:46:59,427 - app.services.chat_service - INFO - Detected Name: Hùng
2025-12-09T19:46:59.427211126Z 2025-12-09 19:46:59,427 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:46:59.427222736Z 2025-12-09 19:46:59,427 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:46:59.427283018Z 2025-12-09 19:46:59,427 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:46:59.427324459Z 2025-12-09 19:46:59,427 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:46:59.432997851Z 2025-12-09 19:46:59,432 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:46:59.433023391Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:46:59.433026541Z                                                              ^
2025-12-09T19:46:59.433028581Z 
2025-12-09T19:46:59.433037812Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:46:59.433040662Z FROM chat_messages 
2025-12-09T19:46:59.433043582Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:46:59.433045742Z  LIMIT %(param_1)s]
2025-12-09T19:46:59.433048512Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:46:59.433050712Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:46:59.433205416Z 2025-12-09 19:46:59,433 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:47:00.900905283Z 2025-12-09 19:47:00,900 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'Quy tắc 16 COLREGs'})
2025-12-09T19:47:00.901491527Z 2025-12-09 19:47:00,901 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: Quy tắc 16 COLREGs
2025-12-09T19:47:00.901559789Z 2025-12-09 19:47:00,901 - app.services.hybrid_search_service - INFO - Hybrid search for: Quy tắc 16 COLREGs
2025-12-09T19:47:00.901701783Z 2025-12-09 19:47:00,901 - app.services.hybrid_search_service - INFO - Detected rule numbers: ['16']
2025-12-09T19:47:01.210831564Z 2025-12-09 19:47:01,210 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:47:01.314142388Z 2025-12-09 19:47:01,313 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:47:01.315803859Z 2025-12-09 19:47:01,315 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:47:01.315920582Z 2025-12-09 19:47:01,315 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: quy | rule | regulation | tắc | 16 | colregs
2025-12-09T19:47:01.43339618Z 2025-12-09 19:47:01,433 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: Quy tắc 16 COLREGs
2025-12-09T19:47:01.435708868Z 2025-12-09 19:47:01,435 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:47:01.436041366Z 2025-12-09 19:47:01,435 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (0 in both, 3 title-boosted)
2025-12-09T19:47:01.436063387Z 2025-12-09 19:47:01,435 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:47:01.436262292Z 2025-12-09 19:47:01,436 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: 36e09d20-833b-42bd-be53-0714330193d4
2025-12-09T19:47:01.531600766Z 2025-12-09 19:47:01,531 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:47:04.585490694Z 2025-12-09 19:47:04,585 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:47:04.631853663Z 2025-12-09 19:47:04,631 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:47:04.632020117Z 2025-12-09 19:47:04,631 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:47:09.220855563Z 2025-12-09 19:47:09,220 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:47:09.220902044Z 2025-12-09 19:47:09,220 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'Quy tắc 16 COLREGs'}, 'result': 'Thông tin về "Quy tắc 16 COLREGs" không có trong kiến thức tra cứu được cung cấp. Kiến thức hiện có '}]
2025-12-09T19:47:09.221277554Z 2025-12-09 19:47:09,221 - app.api.v1.chat - INFO - Chat response generated in 13.255s (agent: rag)
2025-12-09T19:47:09.221505349Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:47:09.232642008Z 2025-12-09 19:47:09,232 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:09.232669479Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:09.232674099Z                                                              ^
2025-12-09T19:47:09.232677019Z 
2025-12-09T19:47:09.232680629Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:09.232685129Z [parameters: {'id': UUID('d3776b59-9e15-4235-bf56-aed46562f738'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'user', 'content': 'Còn quy tắc 16 thì sao?', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 9, 223967, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:09.232688099Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:09.238984427Z 2025-12-09 19:47:09,238 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:09.239000097Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:09.239006407Z                                                              ^
2025-12-09T19:47:09.239011887Z 
2025-12-09T19:47:09.239018647Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:09.239026148Z [parameters: {'id': UUID('316e5b71-1e20-4b3b-bf76-592cfd5bbbe1'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'assistant', 'content': '<thinking>\nNgười dùng đang hỏi về "Quy tắc 16 COLREGs".\nTôi đã sử dụng `tool_maritime_search` để tra cứu, nhưng kết quả trả về không phải là thông  ... (1783 characters truncated) ... oặc đi chậm lại, chứ đừng có cứ từ từ lách qua lách lại trước mũi nó. Tai nạn là cái chắc!\n\nBạn hình dung được không? Nó rất thực tế trên biển đấy.', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 9, 234494, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:09.239047638Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:09.244960546Z 2025-12-09 19:47:09,244 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:47:09.244973276Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:47:09.244979687Z                                                              ^
2025-12-09T19:47:09.244982907Z 
2025-12-09T19:47:09.244986657Z [SQL: 
2025-12-09T19:47:09.244990467Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:47:09.244992637Z                                total_sessions, total_messages, updated_at
2025-12-09T19:47:09.244995227Z                         FROM learning_profile
2025-12-09T19:47:09.244997617Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:09.245000217Z                     ]
2025-12-09T19:47:09.245002347Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:09.245004467Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:09.250197247Z 2025-12-09 19:47:09,250 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:09.250206987Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:47:09.250211247Z                                         ^
2025-12-09T19:47:09.250214908Z 
2025-12-09T19:47:09.250218488Z [SQL: 
2025-12-09T19:47:09.250222218Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:47:09.250226198Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:47:09.250230008Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:47:09.250233648Z                     ]
2025-12-09T19:47:09.250237148Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:47:09.250239268Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:09.256044273Z 2025-12-09 19:47:09,255 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:09.256058034Z LINE 5:                         WHERE user_id = 'test_flow_20251210_...
2025-12-09T19:47:09.256060704Z                                                 ^
2025-12-09T19:47:09.256062494Z 
2025-12-09T19:47:09.256064274Z [SQL: 
2025-12-09T19:47:09.256066794Z                         UPDATE learning_profile
2025-12-09T19:47:09.256068554Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:47:09.256070714Z                             updated_at = NOW()
2025-12-09T19:47:09.256073714Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:09.256089514Z                     ]
2025-12-09T19:47:09.256095505Z [parameters: {'messages': 2, 'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:09.256098235Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:11.335928951Z 2025-12-09 19:47:11,335 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:47:11.336414073Z 2025-12-09 19:47:11,336 - app.api.v1.chat - INFO - Chat request from user test_flow_20251210_024623 (role: student, auth: api_key): Tàu nào phải nhường đường?...
2025-12-09T19:47:11.343803218Z 2025-12-09 19:47:11,343 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:47:11.335928951Z 2025-12-09 19:47:11,335 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:47:11.336414073Z 2025-12-09 19:47:11,336 - app.api.v1.chat - INFO - Chat request from user test_flow_20251210_024623 (role: student, auth: api_key): Tàu nào phải nhường đường?...
2025-12-09T19:47:11.343803218Z 2025-12-09 19:47:11,343 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:47:15.39549703Z 2025-12-09 19:47:15,395 - app.services.chat_service - INFO - Processing request for user test_flow_20251210_024623 with role: student
2025-12-09T19:47:15.401228003Z 2025-12-09 19:47:15,401 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:47:15.401250644Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:47:15.401279485Z                                                              ^
2025-12-09T19:47:15.401283345Z 
2025-12-09T19:47:15.401286995Z [SQL: 
2025-12-09T19:47:15.401290775Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:47:15.401294415Z                                total_sessions, total_messages, updated_at
2025-12-09T19:47:15.401298815Z                         FROM learning_profile
2025-12-09T19:47:15.401302385Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:15.401306755Z                     ]
2025-12-09T19:47:15.401310325Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:15.401314005Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:15.407115111Z 2025-12-09 19:47:15,406 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:15.407135451Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:47:15.407140711Z                                         ^
2025-12-09T19:47:15.407144511Z 
2025-12-09T19:47:15.407148582Z [SQL: 
2025-12-09T19:47:15.407152512Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:47:15.407157062Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:47:15.407160862Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:47:15.407168802Z                     ]
2025-12-09T19:47:15.407173942Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:47:15.407177862Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:15.41388429Z 2025-12-09 19:47:15,413 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:47:15.41389985Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:47:15.41390516Z                                                              ^
2025-12-09T19:47:15.41390936Z 
2025-12-09T19:47:15.413913451Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:47:15.413918451Z FROM chat_messages 
2025-12-09T19:47:15.413923471Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:47:15.413940991Z  LIMIT %(param_1)s]
2025-12-09T19:47:15.413945301Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:47:15.413948221Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:15.420180097Z 2025-12-09 19:47:15,419 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test_flow_20251210_024623 ---
2025-12-09T19:47:15.420194278Z 2025-12-09 19:47:15,420 - app.services.chat_service - INFO - Detected Name: Hùng
2025-12-09T19:47:15.420210098Z 2025-12-09 19:47:15,420 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:47:15.420258729Z 2025-12-09 19:47:15,420 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:47:15.420300491Z 2025-12-09 19:47:15,420 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:47:15.420359722Z 2025-12-09 19:47:15,420 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:47:15.426004443Z 2025-12-09 19:47:15,425 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:47:15.426016643Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:47:15.426020423Z                                                              ^
2025-12-09T19:47:15.426022843Z 
2025-12-09T19:47:15.426025563Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:47:15.426028484Z FROM chat_messages 
2025-12-09T19:47:15.426031924Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:47:15.426034484Z  LIMIT %(param_1)s]
2025-12-09T19:47:15.426037634Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:47:15.426040294Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:15.426252789Z 2025-12-09 19:47:15,426 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:47:21.5730573Z 2025-12-09 19:47:21,572 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:47:21.573313716Z 2025-12-09 19:47:21,573 - app.api.v1.chat - INFO - Chat response generated in 10.237s (agent: chat)
2025-12-09T19:47:21.573520821Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:47:21.579684536Z 2025-12-09 19:47:21,579 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:21.579699636Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:21.579705356Z                                                              ^
2025-12-09T19:47:21.579709826Z 
2025-12-09T19:47:21.579715586Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:21.579722677Z [parameters: {'id': UUID('79e818e0-f621-4bbe-860d-9ba26dc54af7'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'user', 'content': 'Tàu nào phải nhường đường?', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 21, 575878, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:21.579739787Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:21.587513691Z 2025-12-09 19:47:21,587 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:21.587528452Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:21.587531812Z                                                              ^
2025-12-09T19:47:21.587534082Z 
2025-12-09T19:47:21.587537392Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:21.587542202Z [parameters: {'id': UUID('5c97113e-4490-4add-a6af-e740ed1dd791'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'assistant', 'content': '<thinking>\nThe user is asking a very general question about "who gives way" in maritime navigation. This directly relates to the **COLREGs (Internat ... (653 characters truncated) ... . Since this is a follow-up, and I\'ve used direct rule naming before, I\'ll try a more conversational opening related to a common situation on biển.', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 21, 582156, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:21.587544892Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:21.592925307Z 2025-12-09 19:47:21,592 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:47:21.592938637Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:47:21.592942427Z                                                              ^
2025-12-09T19:47:21.592945047Z 
2025-12-09T19:47:21.592947617Z [SQL: 
2025-12-09T19:47:21.592950647Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:47:21.592953277Z                                total_sessions, total_messages, updated_at
2025-12-09T19:47:21.592959368Z                         FROM learning_profile
2025-12-09T19:47:21.592962337Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:21.592965918Z                     ]
2025-12-09T19:47:21.592968528Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:21.592971108Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:21.598009474Z 2025-12-09 19:47:21,597 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:21.598024234Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:47:21.598029344Z                                         ^
2025-12-09T19:47:21.598032774Z 
2025-12-09T19:47:21.598036074Z [SQL: 
2025-12-09T19:47:21.598039575Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:47:21.598043475Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:47:21.598047215Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:47:21.598050995Z                     ]
2025-12-09T19:47:21.598055185Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:47:21.598058795Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:21.603320636Z 2025-12-09 19:47:21,603 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:21.603345687Z LINE 5:                         WHERE user_id = 'test_flow_20251210_...
2025-12-09T19:47:21.603349117Z                                                 ^
2025-12-09T19:47:21.603351267Z 
2025-12-09T19:47:21.603353627Z [SQL: 
2025-12-09T19:47:21.603356397Z                         UPDATE learning_profile
2025-12-09T19:47:21.603359057Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:47:21.603361297Z                             updated_at = NOW()
2025-12-09T19:47:21.603363568Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:21.603366168Z                     ]
2025-12-09T19:47:21.603368428Z [parameters: {'messages': 2, 'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:21.603370768Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:23.660279031Z 2025-12-09 19:47:23,659 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:47:23.661174783Z 2025-12-09 19:47:23,660 - app.api.v1.chat - INFO - Chat request from user test_flow_20251210_024623 (role: student, auth: api_key): Bạn còn nhớ tên tôi không?...
2025-12-09T19:47:23.667901742Z 2025-12-09 19:47:23,667 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:47:27.011356751Z 2025-12-09 19:47:27,007 - app.services.chat_service - INFO - Processing request for user test_flow_20251210_024623 with role: student
2025-12-09T19:47:27.01531544Z 2025-12-09 19:47:27,013 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:47:27.01533866Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:47:27.015343561Z                                                              ^
2025-12-09T19:47:27.015347271Z 
2025-12-09T19:47:27.015351281Z [SQL: 
2025-12-09T19:47:27.015355191Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:47:27.015359091Z                                total_sessions, total_messages, updated_at
2025-12-09T19:47:27.015363521Z                         FROM learning_profile
2025-12-09T19:47:27.015367321Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:27.015371241Z                     ]
2025-12-09T19:47:27.015375461Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:27.015379401Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:27.019607067Z 2025-12-09 19:47:27,019 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:27.019631558Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:47:27.019636718Z                                         ^
2025-12-09T19:47:27.019640548Z 
2025-12-09T19:47:27.019655648Z [SQL: 
2025-12-09T19:47:27.019659858Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:47:27.019664338Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:47:27.019668359Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:47:27.019672699Z                     ]
2025-12-09T19:47:27.019677179Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:47:27.019681399Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:27.027790362Z 2025-12-09 19:47:27,027 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:47:27.027808672Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:47:27.027811992Z                                                              ^
2025-12-09T19:47:27.027814172Z 
2025-12-09T19:47:27.027816493Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:47:27.027819313Z FROM chat_messages 
2025-12-09T19:47:27.027822593Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:47:27.027824843Z  LIMIT %(param_1)s]
2025-12-09T19:47:27.027827703Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:47:27.027830223Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:27.033734781Z 2025-12-09 19:47:27,033 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test_flow_20251210_024623 ---
2025-12-09T19:47:27.033769751Z 2025-12-09 19:47:27,033 - app.services.chat_service - INFO - Detected Name: Hùng
2025-12-09T19:47:27.033828373Z 2025-12-09 19:47:27,033 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:47:27.033834663Z 2025-12-09 19:47:27,033 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:47:27.033896394Z 2025-12-09 19:47:27,033 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:47:27.033903735Z 2025-12-09 19:47:27,033 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:47:27.039501195Z 2025-12-09 19:47:27,039 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:47:27.039517335Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:47:27.039521005Z                                                              ^
2025-12-09T19:47:27.039523165Z 
2025-12-09T19:47:27.039525765Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:47:27.039528625Z FROM chat_messages 
2025-12-09T19:47:27.039532095Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:47:27.039534615Z  LIMIT %(param_1)s]
2025-12-09T19:47:27.039537495Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:47:27.039539716Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:27.039765131Z 2025-12-09 19:47:27,039 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:47:28.308607285Z 2025-12-09 19:47:28,308 - app.engine.unified_agent - INFO - [ReAct] Calling: get_user_info({})
2025-12-09T19:47:28.308653336Z 2025-12-09 19:47:28,308 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:47:30.131784502Z 2025-12-09 19:47:30,131 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'get_user_info', 'args': {}, 'result': "Tool 'get_user_info' not found"}]
2025-12-09T19:47:30.132028348Z 2025-12-09 19:47:30,131 - app.api.v1.chat - INFO - Chat response generated in 6.471s (agent: chat)
2025-12-09T19:47:30.132270255Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:47:30.138837099Z 2025-12-09 19:47:30,138 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:30.138855509Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:30.138859849Z                                                              ^
2025-12-09T19:47:30.138862799Z 
2025-12-09T19:47:30.138866449Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:30.13887182Z [parameters: {'id': UUID('a1d67969-7b00-45b7-a843-73661497e71a'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'user', 'content': 'Bạn còn nhớ tên tôi không?', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 30, 134783, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:30.13887467Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:30.144766637Z 2025-12-09 19:47:30,144 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:30.144783207Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:30.144786968Z                                                              ^
2025-12-09T19:47:30.144789048Z 
2025-12-09T19:47:30.144791977Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:30.144796288Z [parameters: {'id': UUID('e72c80e7-418a-469d-bd7a-fa03a3dcf2c2'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'assistant', 'content': 'Nhớ chứ, bạn là **Hùng** phải không? Tôi luôn nhớ những gương mặt mới mà! Có gì cần tôi giúp không Hùng?', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 30, 140630, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:30.144798988Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:30.150352647Z 2025-12-09 19:47:30,150 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:47:30.150365527Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:47:30.150369107Z                                                              ^
2025-12-09T19:47:30.150371137Z 
2025-12-09T19:47:30.150373197Z [SQL: 
2025-12-09T19:47:30.150375397Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:47:30.150377457Z                                total_sessions, total_messages, updated_at
2025-12-09T19:47:30.150380177Z                         FROM learning_profile
2025-12-09T19:47:30.150382288Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:30.150384948Z                     ]
2025-12-09T19:47:30.150387417Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:30.150389448Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:30.155526146Z 2025-12-09 19:47:30,155 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:30.155557687Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:47:30.155561727Z                                         ^
2025-12-09T19:47:30.155564357Z 
2025-12-09T19:47:30.155566927Z [SQL: 
2025-12-09T19:47:30.155570267Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:47:30.155573587Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:47:30.155576307Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:47:30.155579758Z                     ]
2025-12-09T19:47:30.155583138Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:47:30.155586598Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:30.160621124Z 2025-12-09 19:47:30,160 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:30.160638764Z LINE 5:                         WHERE user_id = 'test_flow_20251210_...
2025-12-09T19:47:30.160642294Z                                                 ^
2025-12-09T19:47:30.160644744Z 
2025-12-09T19:47:30.160647414Z [SQL: 
2025-12-09T19:47:30.160650654Z                         UPDATE learning_profile
2025-12-09T19:47:30.160653314Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:47:30.160655694Z                             updated_at = NOW()
2025-12-09T19:47:30.160658074Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:30.160661585Z                     ]
2025-12-09T19:47:30.160664225Z [parameters: {'messages': 2, 'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:30.160666755Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:32.228977253Z 2025-12-09 19:47:32,228 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:47:32.229436964Z 2025-12-09 19:47:32,229 - app.api.v1.chat - INFO - Chat request from user test_flow_20251210_024623 (role: student, auth: api_key): Học nhiều quá mệt quá...
2025-12-09T19:47:32.236678685Z 2025-12-09 19:47:32,236 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:47:35.378340568Z 2025-12-09 19:47:35,378 - app.services.chat_service - INFO - Processing request for user test_flow_20251210_024623 with role: student
2025-12-09T19:47:35.38442228Z 2025-12-09 19:47:35,384 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:47:35.38443964Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:47:35.384446431Z                                                              ^
2025-12-09T19:47:35.384451071Z 
2025-12-09T19:47:35.384458361Z [SQL: 
2025-12-09T19:47:35.384464251Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:47:35.384469971Z                                total_sessions, total_messages, updated_at
2025-12-09T19:47:35.384476261Z                         FROM learning_profile
2025-12-09T19:47:35.384481421Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:35.384488032Z                     ]
2025-12-09T19:47:35.384492812Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:35.384496292Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:35.38964363Z 2025-12-09 19:47:35,389 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:35.389682582Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:47:35.389685812Z                                         ^
2025-12-09T19:47:35.389687542Z 
2025-12-09T19:47:35.389689362Z [SQL: 
2025-12-09T19:47:35.389691202Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:47:35.389693242Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:47:35.389695042Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:47:35.389697312Z                     ]
2025-12-09T19:47:35.389699612Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:47:35.389701292Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:35.395647501Z 2025-12-09 19:47:35,395 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:47:35.395658611Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:47:35.395661891Z                                                              ^
2025-12-09T19:47:35.395664291Z 
2025-12-09T19:47:35.395667001Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:47:35.395669891Z FROM chat_messages 
2025-12-09T19:47:35.395673121Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:47:35.395676111Z  LIMIT %(param_1)s]
2025-12-09T19:47:35.395679012Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:47:35.395681032Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:35.400935473Z 2025-12-09 19:47:35,400 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER test_flow_20251210_024623 ---
2025-12-09T19:47:35.400949633Z 2025-12-09 19:47:35,400 - app.services.chat_service - INFO - Detected Name: Hùng
2025-12-09T19:47:35.400968844Z 2025-12-09 19:47:35,400 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:47:35.401044466Z 2025-12-09 19:47:35,400 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:47:35.401052106Z 2025-12-09 19:47:35,400 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:47:35.401102847Z 2025-12-09 19:47:35,401 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:47:35.407315832Z 2025-12-09 19:47:35,407 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:47:35.407332433Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:47:35.407336803Z                                                              ^
2025-12-09T19:47:35.407339803Z 
2025-12-09T19:47:35.407343033Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:47:35.407347283Z FROM chat_messages 
2025-12-09T19:47:35.407351203Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:47:35.407357804Z  LIMIT %(param_1)s]
2025-12-09T19:47:35.407376384Z [parameters: {'session_id_1': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'param_1': 50}]
2025-12-09T19:47:35.407379674Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:35.407561409Z 2025-12-09 19:47:35,407 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:47:39.629488468Z 2025-12-09 19:47:39,629 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:47:39.629726425Z 2025-12-09 19:47:39,629 - app.api.v1.chat - INFO - Chat response generated in 7.400s (agent: chat)
2025-12-09T19:47:39.62995745Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:47:39.636638517Z 2025-12-09 19:47:39,636 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:39.636650248Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:39.636653518Z                                                              ^
2025-12-09T19:47:39.636655598Z 
2025-12-09T19:47:39.636659548Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:39.636663828Z [parameters: {'id': UUID('94c0362a-bcc0-4f84-81b9-8d8acaf176ef'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'user', 'content': 'Học nhiều quá mệt quá', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 39, 632590, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:39.636666178Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:39.642536425Z 2025-12-09 19:47:39,642 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:47:39.642548245Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:47:39.642551855Z                                                              ^
2025-12-09T19:47:39.642554685Z 
2025-12-09T19:47:39.642558055Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:47:39.642563406Z [parameters: {'id': UUID('341f2996-cca3-4d78-96e0-264eb72332d7'), 'session_id': UUID('9efb8aa9-7b98-40c9-b344-bd0ca2a6db09'), 'role': 'assistant', 'content': 'Ôi dào, cái này ai học luật biển cũng trải qua hết! 😴 Ngày xưa tôi ôn thi Đại phó cũng thế, nhiều khi cầm quyển luật mà mắt cứ díp lại.\n\nThôi, đừng ... (112 characters truncated) ... ao. Khi nào thấy khỏe lại thì mình chiến tiếp. Nhớ là, học hành cũng như đi biển thôi, biết lúc nào cần nghỉ ngơi để giữ sức là cực kỳ quan trọng đó!', 'created_at': datetime.datetime(2025, 12, 9, 19, 47, 39, 638398, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:47:39.642566555Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:39.643230642Z 2025-12-09 19:47:39,643 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:47:40.69272533Z 2025-12-09 19:47:40,692 - app.engine.memory_summarizer - INFO - Async summarized 4 messages
2025-12-09T19:47:40.698396952Z 2025-12-09 19:47:40,698 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:47:40.698428202Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:47:40.698432453Z                                                              ^
2025-12-09T19:47:40.698435433Z 
2025-12-09T19:47:40.698438323Z [SQL: 
2025-12-09T19:47:40.698441233Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:47:40.698443803Z                                total_sessions, total_messages, updated_at
2025-12-09T19:47:40.698447053Z                         FROM learning_profile
2025-12-09T19:47:40.698449543Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:40.698453343Z                     ]
2025-12-09T19:47:40.698456083Z [parameters: {'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:40.698458803Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:47:40.703764966Z 2025-12-09 19:47:40,703 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:40.703780126Z LINE 3:                         VALUES ('test_flow_20251210_024623',...
2025-12-09T19:47:40.703783387Z                                         ^
2025-12-09T19:47:40.703785587Z 
2025-12-09T19:47:40.703788016Z [SQL: 
2025-12-09T19:47:40.703790287Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:47:40.703793247Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:47:40.703795427Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:47:40.703798337Z                     ]
2025-12-09T19:47:40.703801007Z [parameters: {'user_id': 'test_flow_20251210_024623', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:47:40.703803147Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:47:40.708695509Z 2025-12-09 19:47:40,708 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "test_flow_20251210_024623"
2025-12-09T19:47:40.7087099Z LINE 5:                         WHERE user_id = 'test_flow_20251210_...
2025-12-09T19:47:40.70871478Z                                                 ^
2025-12-09T19:47:40.70871803Z 
2025-12-09T19:47:40.70872107Z [SQL: 
2025-12-09T19:47:40.70872495Z                         UPDATE learning_profile
2025-12-09T19:47:40.70872845Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:47:40.70873207Z                             updated_at = NOW()
2025-12-09T19:47:40.7087359Z                         WHERE user_id = %(user_id)s
2025-12-09T19:47:40.708768641Z                     ]
2025-12-09T19:47:40.708773821Z [parameters: {'messages': 2, 'user_id': 'test_flow_20251210_024623'}]
2025-12-09T19:47:40.708776051Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:03.674578603Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:48:03.783346813Z 2025-12-09 19:48:03,783 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:48:03.783895377Z 2025-12-09 19:48:03,783 - app.api.v1.chat - INFO - Chat request from user lights-test-user (role: student, auth: api_key): Khi thấy đèn đỏ trên tàu khác, tôi nên làm gì?...
2025-12-09T19:48:03.791029146Z 2025-12-09 19:48:03,790 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:48:07.915910848Z 2025-12-09 19:48:07,915 - app.services.chat_service - INFO - Processing request for user lights-test-user with role: student
2025-12-09T19:48:07.92156695Z 2025-12-09 19:48:07,921 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:48:07.921598941Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:48:07.921604631Z                                                              ^
2025-12-09T19:48:07.921607341Z 
2025-12-09T19:48:07.921609991Z [SQL: 
2025-12-09T19:48:07.921612921Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:48:07.921615551Z                                total_sessions, total_messages, updated_at
2025-12-09T19:48:07.921620621Z                         FROM learning_profile
2025-12-09T19:48:07.921623131Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:07.921626151Z                     ]
2025-12-09T19:48:07.921628571Z [parameters: {'user_id': 'lights-test-user'}]
2025-12-09T19:48:07.921630942Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:07.927103139Z 2025-12-09 19:48:07,926 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:07.927116879Z LINE 3:                         VALUES ('lights-test-user', '{"level...
2025-12-09T19:48:07.927119989Z                                         ^
2025-12-09T19:48:07.927122089Z 
2025-12-09T19:48:07.927124169Z [SQL: 
2025-12-09T19:48:07.927126499Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:48:07.927128979Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:48:07.927131029Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:48:07.927133609Z                     ]
2025-12-09T19:48:07.927136359Z [parameters: {'user_id': 'lights-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:48:07.927138539Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:07.932924734Z 2025-12-09 19:48:07,932 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:07.932938174Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:07.932941834Z                                                              ^
2025-12-09T19:48:07.932944165Z 
2025-12-09T19:48:07.932947005Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:07.932950325Z FROM chat_messages 
2025-12-09T19:48:07.932954775Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:07.932957335Z  LIMIT %(param_1)s]
2025-12-09T19:48:07.932961055Z [parameters: {'session_id_1': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'param_1': 50}]
2025-12-09T19:48:07.932963655Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:07.938587556Z 2025-12-09 19:48:07,938 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER lights-test-user ---
2025-12-09T19:48:07.938601966Z 2025-12-09 19:48:07,938 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:48:07.938605556Z 2025-12-09 19:48:07,938 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:48:07.938608316Z 2025-12-09 19:48:07,938 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:48:07.938611076Z 2025-12-09 19:48:07,938 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:48:07.938626597Z 2025-12-09 19:48:07,938 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:48:07.943639812Z 2025-12-09 19:48:07,943 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:07.943652862Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:07.943655922Z                                                              ^
2025-12-09T19:48:07.943657942Z 
2025-12-09T19:48:07.943660282Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:07.943662982Z FROM chat_messages 
2025-12-09T19:48:07.943667803Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:07.943670133Z  LIMIT %(param_1)s]
2025-12-09T19:48:07.943672833Z [parameters: {'session_id_1': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'param_1': 50}]
2025-12-09T19:48:07.943675133Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:07.943879938Z 2025-12-09 19:48:07,943 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:48:10.02595884Z 2025-12-09 19:48:10,025 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'hành động khi thấy đèn đỏ tàu khác COLREGs'})
2025-12-09T19:48:10.026161346Z 2025-12-09 19:48:10,026 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: hành động khi thấy đèn đỏ tàu khác COLREGs
2025-12-09T19:48:10.026178666Z 2025-12-09 19:48:10,026 - app.services.hybrid_search_service - INFO - Hybrid search for: hành động khi thấy đèn đỏ tàu khác COLREGs
2025-12-09T19:48:10.324484117Z 2025-12-09 19:48:10,324 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:48:10.4293854Z 2025-12-09 19:48:10,429 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:48:10.431274007Z 2025-12-09 19:48:10,431 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:48:10.431645307Z 2025-12-09 19:48:10,431 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: hành | động | khi | thấy | đèn | light | lighting | đỏ | tàu | vessel | ship | khác | colregs
2025-12-09T19:48:10.645886375Z 2025-12-09 19:48:10,645 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: hành động khi thấy đèn đỏ tàu khác COLREGs
2025-12-09T19:48:10.648073339Z 2025-12-09 19:48:10,647 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:48:10.648350437Z 2025-12-09 19:48:10,648 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (5 in both, 0 title-boosted)
2025-12-09T19:48:10.648358147Z 2025-12-09 19:48:10,648 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:48:10.722764387Z 2025-12-09 19:48:10,722 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:48:19.3374742Z 2025-12-09 19:48:19,337 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:48:19.531047792Z 2025-12-09 19:48:19,530 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:48:19.531205166Z 2025-12-09 19:48:19,531 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:48:24.73053806Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:48:24.849187548Z 2025-12-09 19:48:24,849 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:48:24.850214304Z 2025-12-09 19:48:24,849 - app.api.v1.chat - INFO - Chat request from user lights-test-user (role: student, auth: api_key): Còn đèn xanh thì sao?...
2025-12-09T19:48:24.85967181Z 2025-12-09 19:48:24,859 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:48:27.290065574Z 2025-12-09 19:48:27,289 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:48:27.290098865Z 2025-12-09 19:48:27,289 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'hành động khi thấy đèn đỏ tàu khác COLREGs'}, 'result': 'Về vấn đề hành động khi thấy đèn đỏ của tàu khác theo COLREGs, thông tin tra cứu được hiện tại tập t'}]
2025-12-09T19:48:27.290619908Z 2025-12-09 19:48:27,290 - app.api.v1.chat - INFO - Chat response generated in 23.507s (agent: rag)
2025-12-09T19:48:27.297422938Z 2025-12-09 19:48:27,297 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:48:27.297438989Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:48:27.297444878Z                                                              ^
2025-12-09T19:48:27.297448669Z 
2025-12-09T19:48:27.297453699Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:48:27.297459539Z [parameters: {'id': UUID('6b64d431-606c-45db-9277-157e6223b5e6'), 'session_id': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'role': 'user', 'content': 'Khi thấy đèn đỏ trên tàu khác, tôi nên làm gì?', 'created_at': datetime.datetime(2025, 12, 9, 19, 48, 27, 293016, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:48:27.297463499Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:27.304118276Z 2025-12-09 19:48:27,304 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:48:27.304133786Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:48:27.304138876Z                                                              ^
2025-12-09T19:48:27.304142656Z 
2025-12-09T19:48:27.304148386Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:48:27.304154096Z [parameters: {'id': UUID('9679e550-b47e-4f9f-8708-72beff0954fc'), 'session_id': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'role': 'assistant', 'content': '<thinking>\nNgười dùng đang hỏi về việc hành động khi thấy đèn đỏ trên tàu khác. Đây là một câu hỏi rất cơ bản và quan trọng trong COLREGs, liên quan ... (1600 characters truncated) ... tắc 15 để phân tích tình huống cắt hướng.\n*   Nhấn mạnh rằng dù được ưu tiên, vẫn phải luôn cảnh giác và hành động tránh va.\n*   Đưa ví dụ thực tế.', 'created_at': datetime.datetime(2025, 12, 9, 19, 48, 27, 299812, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:48:27.304172347Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:27.309709105Z 2025-12-09 19:48:27,309 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:48:27.309725506Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:48:27.309728946Z                                                              ^
2025-12-09T19:48:27.309731276Z 
2025-12-09T19:48:27.309733386Z [SQL: 
2025-12-09T19:48:27.309735546Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:48:27.309759046Z                                total_sessions, total_messages, updated_at
2025-12-09T19:48:27.309766987Z                         FROM learning_profile
2025-12-09T19:48:27.309769277Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:27.309771957Z                     ]
2025-12-09T19:48:27.309774097Z [parameters: {'user_id': 'lights-test-user'}]
2025-12-09T19:48:27.309776287Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:27.315733836Z 2025-12-09 19:48:27,315 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:27.315817888Z LINE 3:                         VALUES ('lights-test-user', '{"level...
2025-12-09T19:48:27.315823568Z                                         ^
2025-12-09T19:48:27.315825898Z 
2025-12-09T19:48:27.315828328Z [SQL: 
2025-12-09T19:48:27.315831108Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:48:27.315834258Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:48:27.315836658Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:48:27.315839469Z                     ]
2025-12-09T19:48:27.315842669Z [parameters: {'user_id': 'lights-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:48:27.315845079Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:27.321187572Z 2025-12-09 19:48:27,320 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:27.321199172Z LINE 5:                         WHERE user_id = 'lights-test-user'
2025-12-09T19:48:27.321202413Z                                                 ^
2025-12-09T19:48:27.321204493Z 
2025-12-09T19:48:27.321206653Z [SQL: 
2025-12-09T19:48:27.321209133Z                         UPDATE learning_profile
2025-12-09T19:48:27.321211293Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:48:27.321213403Z                             updated_at = NOW()
2025-12-09T19:48:27.321215483Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:27.321217993Z                     ]
2025-12-09T19:48:27.321220133Z [parameters: {'messages': 2, 'user_id': 'lights-test-user'}]
2025-12-09T19:48:27.321222183Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:28.97086319Z 2025-12-09 19:48:28,970 - app.services.chat_service - INFO - Processing request for user lights-test-user with role: student
2025-12-09T19:48:28.976934422Z 2025-12-09 19:48:28,976 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:48:28.976979083Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:48:28.976984654Z                                                              ^
2025-12-09T19:48:28.976987264Z 
2025-12-09T19:48:28.976989884Z [SQL: 
2025-12-09T19:48:28.976992594Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:48:28.976995544Z                                total_sessions, total_messages, updated_at
2025-12-09T19:48:28.976998854Z                         FROM learning_profile
2025-12-09T19:48:28.977001414Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:28.977005504Z                     ]
2025-12-09T19:48:28.977008144Z [parameters: {'user_id': 'lights-test-user'}]
2025-12-09T19:48:28.977010734Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:28.982295476Z 2025-12-09 19:48:28,982 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:28.982309377Z LINE 3:                         VALUES ('lights-test-user', '{"level...
2025-12-09T19:48:28.982312977Z                                         ^
2025-12-09T19:48:28.982315227Z 
2025-12-09T19:48:28.982317337Z [SQL: 
2025-12-09T19:48:28.982319547Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:48:28.982322217Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:48:28.982324417Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:48:28.982326827Z                     ]
2025-12-09T19:48:28.982329547Z [parameters: {'user_id': 'lights-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:48:28.982331707Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:28.988006069Z 2025-12-09 19:48:28,987 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:28.988019719Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:28.98802352Z                                                              ^
2025-12-09T19:48:28.98802645Z 
2025-12-09T19:48:28.98802924Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:28.98803263Z FROM chat_messages 
2025-12-09T19:48:28.98803582Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:28.98803844Z  LIMIT %(param_1)s]
2025-12-09T19:48:28.988062151Z [parameters: {'session_id_1': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'param_1': 50}]
2025-12-09T19:48:28.988066951Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:28.993283551Z 2025-12-09 19:48:28,993 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER lights-test-user ---
2025-12-09T19:48:28.993311812Z 2025-12-09 19:48:28,993 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:48:28.993353923Z 2025-12-09 19:48:28,993 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:48:28.993400764Z 2025-12-09 19:48:28,993 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:48:28.993495867Z 2025-12-09 19:48:28,993 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:48:28.993500187Z 2025-12-09 19:48:28,993 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:48:28.999044565Z 2025-12-09 19:48:28,998 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:28.999069186Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:28.999073016Z                                                              ^
2025-12-09T19:48:28.999074966Z 
2025-12-09T19:48:28.999077346Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:28.999080076Z FROM chat_messages 
2025-12-09T19:48:28.999082626Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:28.999084716Z  LIMIT %(param_1)s]
2025-12-09T19:48:28.999087256Z [parameters: {'session_id_1': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'param_1': 50}]
2025-12-09T19:48:28.999089406Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:28.999390154Z 2025-12-09 19:48:28,999 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:48:32.937536076Z 2025-12-09 19:48:32,937 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:48:32.937854155Z 2025-12-09 19:48:32,937 - app.api.v1.chat - INFO - Chat response generated in 8.088s (agent: chat)
2025-12-09T19:48:32.938188563Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:48:32.945008413Z 2025-12-09 19:48:32,944 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:48:32.945023704Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:48:32.945028294Z                                                              ^
2025-12-09T19:48:32.945031914Z 
2025-12-09T19:48:32.945036014Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:48:32.945040594Z [parameters: {'id': UUID('dc96931f-eea6-4a4a-8c00-b4c19f52e777'), 'session_id': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'role': 'user', 'content': 'Còn đèn xanh thì sao?', 'created_at': datetime.datetime(2025, 12, 9, 19, 48, 32, 940442, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:48:32.945044174Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:32.950959422Z 2025-12-09 19:48:32,950 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:48:32.951007373Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:48:32.951014144Z                                                              ^
2025-12-09T19:48:32.951019044Z 
2025-12-09T19:48:32.951024014Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:48:32.951029404Z [parameters: {'id': UUID('2410e27c-399a-47c1-8193-5af8d88871de'), 'session_id': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'role': 'assistant', 'content': '<thinking>\nNgười dùng đang hỏi về trường hợp ngược lại với "đèn đỏ thì dừng", tức là "đèn xanh". Trong ngữ cảnh luật hàng hải (COLREGs), "đèn đỏ" tư ... (987 characters truncated) ... g để đảm bảo an toàn.\n\nNôm na là, bạn có quyền ưu tiên, nhưng quyền đó không có nghĩa là bạn "đâm đầu" vào nguy hiểm. An toàn là trên hết, bạn nhé.', 'created_at': datetime.datetime(2025, 12, 9, 19, 48, 32, 946771, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:48:32.951053915Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:32.95607939Z 2025-12-09 19:48:32,955 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:48:32.956091471Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:48:32.956093981Z                                                              ^
2025-12-09T19:48:32.956096361Z 
2025-12-09T19:48:32.956099381Z [SQL: 
2025-12-09T19:48:32.956102241Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:48:32.956104791Z                                total_sessions, total_messages, updated_at
2025-12-09T19:48:32.956107901Z                         FROM learning_profile
2025-12-09T19:48:32.956110311Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:32.956113671Z                     ]
2025-12-09T19:48:32.956116481Z [parameters: {'user_id': 'lights-test-user'}]
2025-12-09T19:48:32.956119491Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:32.961564788Z 2025-12-09 19:48:32,961 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:32.961575908Z LINE 3:                         VALUES ('lights-test-user', '{"level...
2025-12-09T19:48:32.961579588Z                                         ^
2025-12-09T19:48:32.961582168Z 
2025-12-09T19:48:32.961584818Z [SQL: 
2025-12-09T19:48:32.961587708Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:48:32.961591008Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:48:32.961593788Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:48:32.961597168Z                     ]
2025-12-09T19:48:32.961600458Z [parameters: {'user_id': 'lights-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:48:32.961603558Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:32.966605434Z 2025-12-09 19:48:32,966 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:32.966618604Z LINE 5:                         WHERE user_id = 'lights-test-user'
2025-12-09T19:48:32.966622684Z                                                 ^
2025-12-09T19:48:32.966625004Z 
2025-12-09T19:48:32.966627334Z [SQL: 
2025-12-09T19:48:32.966630184Z                         UPDATE learning_profile
2025-12-09T19:48:32.966632474Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:48:32.966638224Z                             updated_at = NOW()
2025-12-09T19:48:32.966665395Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:32.966668785Z                     ]
2025-12-09T19:48:32.966671245Z [parameters: {'messages': 2, 'user_id': 'lights-test-user'}]
2025-12-09T19:48:32.966673575Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:33.49264929Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:48:33.599937573Z 2025-12-09 19:48:33,599 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:48:33.600412185Z 2025-12-09 19:48:33,600 - app.api.v1.chat - INFO - Chat request from user lights-test-user (role: student, auth: api_key): Đèn trắng thì sao?...
2025-12-09T19:48:33.608077827Z 2025-12-09 19:48:33,607 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:48:36.24037955Z 2025-12-09 19:48:36,240 - app.services.chat_service - INFO - Processing request for user lights-test-user with role: student
2025-12-09T19:48:36.246091613Z 2025-12-09 19:48:36,245 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:48:36.246114024Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:48:36.246133524Z                                                              ^
2025-12-09T19:48:36.246139104Z 
2025-12-09T19:48:36.246144655Z [SQL: 
2025-12-09T19:48:36.246150185Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:48:36.246155395Z                                total_sessions, total_messages, updated_at
2025-12-09T19:48:36.246161585Z                         FROM learning_profile
2025-12-09T19:48:36.246167325Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:36.246172675Z                     ]
2025-12-09T19:48:36.246176225Z [parameters: {'user_id': 'lights-test-user'}]
2025-12-09T19:48:36.246179985Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:36.251776625Z 2025-12-09 19:48:36,251 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:36.251799486Z LINE 3:                         VALUES ('lights-test-user', '{"level...
2025-12-09T19:48:36.251804526Z                                         ^
2025-12-09T19:48:36.251807946Z 
2025-12-09T19:48:36.251811406Z [SQL: 
2025-12-09T19:48:36.251815086Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:48:36.251819396Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:48:36.251822966Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:48:36.251827226Z                     ]
2025-12-09T19:48:36.251831577Z [parameters: {'user_id': 'lights-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:48:36.251835207Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:36.258031852Z 2025-12-09 19:48:36,257 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:36.258049962Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:36.258054662Z                                                              ^
2025-12-09T19:48:36.258058013Z 
2025-12-09T19:48:36.258061842Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:36.258066033Z FROM chat_messages 
2025-12-09T19:48:36.258070483Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:36.258073923Z  LIMIT %(param_1)s]
2025-12-09T19:48:36.258077953Z [parameters: {'session_id_1': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'param_1': 50}]
2025-12-09T19:48:36.258096274Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:36.263395356Z 2025-12-09 19:48:36,263 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER lights-test-user ---
2025-12-09T19:48:36.263410766Z 2025-12-09 19:48:36,263 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:48:36.263463158Z 2025-12-09 19:48:36,263 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:48:36.263466068Z 2025-12-09 19:48:36,263 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:48:36.263470758Z 2025-12-09 19:48:36,263 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:48:36.263517009Z 2025-12-09 19:48:36,263 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:48:36.268821062Z 2025-12-09 19:48:36,268 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:36.268831912Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:36.268835412Z                                                              ^
2025-12-09T19:48:36.268837662Z 
2025-12-09T19:48:36.268840352Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:36.268843752Z FROM chat_messages 
2025-12-09T19:48:36.268847222Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:36.268849792Z  LIMIT %(param_1)s]
2025-12-09T19:48:36.268852972Z [parameters: {'session_id_1': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'param_1': 50}]
2025-12-09T19:48:36.268855823Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:36.269062898Z 2025-12-09 19:48:36,268 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:48:37.911223788Z 2025-12-09 19:48:37,911 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'đèn trắng trong COLREGs'})
2025-12-09T19:48:37.911819743Z 2025-12-09 19:48:37,911 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: đèn trắng trong COLREGs
2025-12-09T19:48:37.911865144Z 2025-12-09 19:48:37,911 - app.services.hybrid_search_service - INFO - Hybrid search for: đèn trắng trong COLREGs
2025-12-09T19:48:38.222184715Z 2025-12-09 19:48:38,221 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:48:38.324182426Z 2025-12-09 19:48:38,324 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:48:38.325735585Z 2025-12-09 19:48:38,325 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:48:38.325903669Z 2025-12-09 19:48:38,325 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: đèn | light | lighting | trắng | colregs
2025-12-09T19:48:38.432616758Z 2025-12-09 19:48:38,432 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 5 results for query: đèn trắng trong COLREGs
2025-12-09T19:48:38.435221313Z 2025-12-09 19:48:38,434 - app.services.hybrid_search_service - INFO - Sparse search returned 5 results
2025-12-09T19:48:38.435239634Z 2025-12-09 19:48:38,434 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 5 sparse -> 5 results (0 in both, 0 title-boosted)
2025-12-09T19:48:38.435243424Z 2025-12-09 19:48:38,434 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:48:38.435261674Z 2025-12-09 19:48:38,434 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: c9e89f35-de79-4978-8703-b0795cad518f
2025-12-09T19:48:38.435264684Z 2025-12-09 19:48:38,434 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: e6890162-0471-467e-8ea0-7559fb983ac4
2025-12-09T19:48:38.537975543Z 2025-12-09 19:48:38,537 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:48:43.58700069Z 2025-12-09 19:48:43,586 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:48:43.632278912Z 2025-12-09 19:48:43,632 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:48:43.632388715Z 2025-12-09 19:48:43,632 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:48:50.846850792Z ==> Detected service running on port 10000
2025-12-09T19:48:51.246986275Z ==> Docs on specifying a port: https://render.com/docs/web-services#port-binding
2025-12-09T19:48:50.57502535Z 2025-12-09 19:48:50,574 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:48:50.575055721Z 2025-12-09 19:48:50,574 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'đèn trắng trong COLREGs'}, 'result': 'Theo kiến thức tra cứu được, thông tin chi tiết về đèn trắng trong Quy tắc quốc tế về tránh va chạm '}]
2025-12-09T19:48:50.575390219Z 2025-12-09 19:48:50,575 - app.api.v1.chat - INFO - Chat response generated in 16.975s (agent: rag)
2025-12-09T19:48:50.575624185Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:48:50.582338333Z 2025-12-09 19:48:50,582 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:48:50.582394344Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:48:50.582399724Z                                                              ^
2025-12-09T19:48:50.582403614Z 
2025-12-09T19:48:50.582408474Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:48:50.582415255Z [parameters: {'id': UUID('eeca59fb-bfec-48ae-af18-46e756f1eee2'), 'session_id': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'role': 'user', 'content': 'Đèn trắng thì sao?', 'created_at': datetime.datetime(2025, 12, 9, 19, 48, 50, 578066, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:48:50.582419295Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:50.589334238Z 2025-12-09 19:48:50,589 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:48:50.589363418Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:48:50.589369668Z                                                              ^
2025-12-09T19:48:50.589373759Z 
2025-12-09T19:48:50.589378679Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:48:50.589386229Z [parameters: {'id': UUID('87849785-2af5-4c39-8d97-514f0236cf11'), 'session_id': UUID('e3e67f26-a884-4bf4-aac4-fa0d36b028c7'), 'role': 'assistant', 'content': 'Tiếp tục với câu hỏi về đèn trắng của bạn, đây là một điểm khá hay đó! Bởi vì trong COLREGs, đèn trắng không phải là một quy tắc cụ thể như đèn đỏ ha ... (1399 characters truncated) ... trí, số lượng và cách nó chiếu sáng để đoán xem đó là loại tàu gì và nó đang làm gì. Hiểu ý tôi chứ? Đó là cái tinh túy của việc đọc đèn ban đêm đấy!', 'created_at': datetime.datetime(2025, 12, 9, 19, 48, 50, 584258, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:48:50.589405769Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:50.595850741Z 2025-12-09 19:48:50,595 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:48:50.595862911Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:48:50.595866601Z                                                              ^
2025-12-09T19:48:50.595868991Z 
2025-12-09T19:48:50.595871711Z [SQL: 
2025-12-09T19:48:50.595874621Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:48:50.595877461Z                                total_sessions, total_messages, updated_at
2025-12-09T19:48:50.595880651Z                         FROM learning_profile
2025-12-09T19:48:50.595883422Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:50.595886562Z                     ]
2025-12-09T19:48:50.595889632Z [parameters: {'user_id': 'lights-test-user'}]
2025-12-09T19:48:50.595892152Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:50.602287362Z 2025-12-09 19:48:50,601 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:50.602298992Z LINE 3:                         VALUES ('lights-test-user', '{"level...
2025-12-09T19:48:50.602302462Z                                         ^
2025-12-09T19:48:50.602304972Z 
2025-12-09T19:48:50.602307432Z [SQL: 
2025-12-09T19:48:50.602310042Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:48:50.602313262Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:48:50.602316502Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:48:50.602319483Z                     ]
2025-12-09T19:48:50.602322763Z [parameters: {'user_id': 'lights-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:48:50.602325013Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:50.607967634Z 2025-12-09 19:48:50,607 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "lights-test-user"
2025-12-09T19:48:50.607979914Z LINE 5:                         WHERE user_id = 'lights-test-user'
2025-12-09T19:48:50.607984514Z                                                 ^
2025-12-09T19:48:50.607987594Z 
2025-12-09T19:48:50.607990764Z [SQL: 
2025-12-09T19:48:50.607994664Z                         UPDATE learning_profile
2025-12-09T19:48:50.607998094Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:48:50.608002185Z                             updated_at = NOW()
2025-12-09T19:48:50.608005655Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:50.608010215Z                     ]
2025-12-09T19:48:50.608013575Z [parameters: {'messages': 2, 'user_id': 'lights-test-user'}]
2025-12-09T19:48:50.608016945Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:51.141350924Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:48:51.249690173Z 2025-12-09 19:48:51,249 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:48:51.250210946Z 2025-12-09 19:48:51,250 - app.api.v1.chat - INFO - Chat request from user reg-test-user (role: student, auth: api_key): Điều kiện đăng ký tàu biển Việt Nam là gì?...
2025-12-09T19:48:51.257340714Z 2025-12-09 19:48:51,257 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:48:54.174174454Z 2025-12-09 19:48:54,174 - app.services.chat_service - INFO - Processing request for user reg-test-user with role: student
2025-12-09T19:48:54.179792405Z 2025-12-09 19:48:54,179 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:48:54.179815875Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:48:54.179820825Z                                                              ^
2025-12-09T19:48:54.179824316Z 
2025-12-09T19:48:54.179827896Z [SQL: 
2025-12-09T19:48:54.179831796Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:48:54.179835486Z                                total_sessions, total_messages, updated_at
2025-12-09T19:48:54.179839896Z                         FROM learning_profile
2025-12-09T19:48:54.179843676Z                         WHERE user_id = %(user_id)s
2025-12-09T19:48:54.179848086Z                     ]
2025-12-09T19:48:54.179852026Z [parameters: {'user_id': 'reg-test-user'}]
2025-12-09T19:48:54.179855806Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:54.185938849Z 2025-12-09 19:48:54,185 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:48:54.185956569Z LINE 3:                         VALUES ('reg-test-user', '{"level": ...
2025-12-09T19:48:54.185962649Z                                         ^
2025-12-09T19:48:54.185966949Z 
2025-12-09T19:48:54.185971449Z [SQL: 
2025-12-09T19:48:54.185976269Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:48:54.185981619Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:48:54.18598584Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:48:54.18599077Z                     ]
2025-12-09T19:48:54.1859955Z [parameters: {'user_id': 'reg-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:48:54.1860001Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:48:54.191406535Z 2025-12-09 19:48:54,191 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:54.191424366Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:54.191430326Z                                                              ^
2025-12-09T19:48:54.191433726Z 
2025-12-09T19:48:54.191437376Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:54.191441416Z FROM chat_messages 
2025-12-09T19:48:54.191446686Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:54.191450176Z  LIMIT %(param_1)s]
2025-12-09T19:48:54.191454267Z [parameters: {'session_id_1': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'param_1': 50}]
2025-12-09T19:48:54.191471387Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:54.19681619Z 2025-12-09 19:48:54,196 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER reg-test-user ---
2025-12-09T19:48:54.196897592Z 2025-12-09 19:48:54,196 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:48:54.196903333Z 2025-12-09 19:48:54,196 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:48:54.196906423Z 2025-12-09 19:48:54,196 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:48:54.197075737Z 2025-12-09 19:48:54,196 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:48:54.197083197Z 2025-12-09 19:48:54,196 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:48:54.202459431Z 2025-12-09 19:48:54,202 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:48:54.202471922Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:48:54.202475742Z                                                              ^
2025-12-09T19:48:54.202477872Z 
2025-12-09T19:48:54.202480252Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:48:54.202483362Z FROM chat_messages 
2025-12-09T19:48:54.202486332Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:48:54.202488522Z  LIMIT %(param_1)s]
2025-12-09T19:48:54.202491372Z [parameters: {'session_id_1': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'param_1': 50}]
2025-12-09T19:48:54.202493652Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:48:54.202690927Z 2025-12-09 19:48:54,202 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:48:55.694326273Z 2025-12-09 19:48:55,694 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'Điều kiện đăng ký tàu biển Việt Nam'})
2025-12-09T19:48:55.695040181Z 2025-12-09 19:48:55,694 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: Điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:48:55.695090132Z 2025-12-09 19:48:55,695 - app.services.hybrid_search_service - INFO - Hybrid search for: Điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:48:56.007529156Z 2025-12-09 19:48:56,007 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:48:56.120411679Z 2025-12-09 19:48:56,120 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:48:56.122132142Z 2025-12-09 19:48:56,122 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:48:56.122274856Z 2025-12-09 19:48:56,122 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: điều | rule | quy | tắc | regulation | kiện | đăng | ký | tàu | vessel | ship | biển | việt | nam
2025-12-09T19:48:56.334241007Z 2025-12-09 19:48:56,334 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: Điều kiện đăng ký tàu biển Việt Nam
2025-12-09T19:48:56.335797616Z 2025-12-09 19:48:56,335 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:48:56.336066943Z 2025-12-09 19:48:56,335 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (1 in both, 0 title-boosted)
2025-12-09T19:48:56.336298679Z 2025-12-09 19:48:56,336 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:48:56.336304219Z 2025-12-09 19:48:56,336 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: c8797f1b-7da6-4709-9d30-dd61931997a7
2025-12-09T19:48:56.336307109Z 2025-12-09 19:48:56,336 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: 9ec8b517-7a77-4ab3-8ada-91709ba2f474
2025-12-09T19:48:56.411062489Z 2025-12-09 19:48:56,410 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:48:59.240225966Z 2025-12-09 19:48:59,240 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:48:59.326853092Z 2025-12-09 19:48:59,326 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:48:59.326957575Z 2025-12-09 19:48:59,326 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:49:04.520554037Z 2025-12-09 19:49:04,520 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:49:04.520609068Z 2025-12-09 19:49:04,520 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'Điều kiện đăng ký tàu biển Việt Nam'}, 'result': 'Theo Điều 20 của quy định, tàu biển khi đăng ký vào Sổ đăng ký tàu biển quốc gia Việt Nam phải đáp ứ'}]
2025-12-09T19:49:04.521121791Z 2025-12-09 19:49:04,521 - app.api.v1.chat - INFO - Chat response generated in 13.271s (agent: rag)
2025-12-09T19:49:04.521414458Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:49:04.527863449Z 2025-12-09 19:49:04,527 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:04.52788022Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:04.52788541Z                                                              ^
2025-12-09T19:49:04.5278894Z 
2025-12-09T19:49:04.52789449Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:04.52789932Z [parameters: {'id': UUID('702f25ce-a75a-426d-9f7c-22c5b1aa76b7'), 'session_id': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'role': 'user', 'content': 'Điều kiện đăng ký tàu biển Việt Nam là gì?', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 4, 523867, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:04.52790324Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:04.533842439Z 2025-12-09 19:49:04,533 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:04.533855839Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:04.533861739Z                                                              ^
2025-12-09T19:49:04.533866209Z 
2025-12-09T19:49:04.533870879Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:04.533876279Z [parameters: {'id': UUID('4b7346a5-1bca-4940-b448-2c68ac835178'), 'session_id': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'role': 'assistant', 'content': "**Quy tắc Đăng ký tàu biển** - À này bạn, muốn cho con tàu mình mang cờ Việt Nam, ra khơi ngẩng cao đầu thì cũng phải qua mấy cái 'cửa' chứ không phả ... (1708 characters truncated) ... mang quốc tịch Việt Nam ra khơi đấy bạn. Có vẻ hơi rắc rối một chút, nhưng cái gì liên quan đến an toàn và luật pháp thì phải chặt chẽ thôi, bạn nhỉ?", 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 4, 529602, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:04.53389128Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:04.541367777Z 2025-12-09 19:49:04,541 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:04.541381297Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:04.541388627Z                                                              ^
2025-12-09T19:49:04.541391627Z 
2025-12-09T19:49:04.541394828Z [SQL: 
2025-12-09T19:49:04.541398328Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:04.541402108Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:04.541406648Z                         FROM learning_profile
2025-12-09T19:49:04.541409338Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:04.541412038Z                     ]
2025-12-09T19:49:04.541414718Z [parameters: {'user_id': 'reg-test-user'}]
2025-12-09T19:49:04.541416898Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:04.54667557Z 2025-12-09 19:49:04,546 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:04.54670455Z LINE 3:                         VALUES ('reg-test-user', '{"level": ...
2025-12-09T19:49:04.546709831Z                                         ^
2025-12-09T19:49:04.546712291Z 
2025-12-09T19:49:04.546714951Z [SQL: 
2025-12-09T19:49:04.546717611Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:04.546720601Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:04.546723831Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:04.546727071Z                     ]
2025-12-09T19:49:04.546730391Z [parameters: {'user_id': 'reg-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:04.546733021Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:04.551459259Z 2025-12-09 19:49:04,551 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:04.551471799Z LINE 5:                         WHERE user_id = 'reg-test-user'
2025-12-09T19:49:04.55147607Z                                                 ^
2025-12-09T19:49:04.55147949Z 
2025-12-09T19:49:04.55148291Z [SQL: 
2025-12-09T19:49:04.5514872Z                         UPDATE learning_profile
2025-12-09T19:49:04.55149091Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:49:04.55149451Z                             updated_at = NOW()
2025-12-09T19:49:04.55149837Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:04.55150207Z                     ]
2025-12-09T19:49:04.5515059Z [parameters: {'messages': 2, 'user_id': 'reg-test-user'}]
2025-12-09T19:49:04.551521651Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:05.012941131Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:49:05.102176213Z 2025-12-09 19:49:05,101 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:49:05.102703856Z 2025-12-09 19:49:05,102 - app.api.v1.chat - INFO - Chat request from user reg-test-user (role: student, auth: api_key): Cần những giấy tờ gì?...
2025-12-09T19:49:05.109820054Z 2025-12-09 19:49:05,109 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:49:09.735364128Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:49:09.82898368Z 2025-12-09 19:49:09,828 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:49:09.829936084Z 2025-12-09 19:49:09,829 - app.api.v1.chat - INFO - Chat request from user reg-test-user (role: student, auth: api_key): Phí bao nhiêu?...
2025-12-09T19:49:09.836621221Z 2025-12-09 19:49:09,836 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:49:12.708386154Z 2025-12-09 19:49:12,708 - app.services.chat_service - INFO - Processing request for user reg-test-user with role: student
2025-12-09T19:49:12.71424183Z 2025-12-09 19:49:12,714 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:12.71426353Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:12.714268691Z                                                              ^
2025-12-09T19:49:12.714272411Z 
2025-12-09T19:49:12.714276261Z [SQL: 
2025-12-09T19:49:12.714280111Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:12.714284021Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:12.714288901Z                         FROM learning_profile
2025-12-09T19:49:12.714292841Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:12.714297181Z                     ]
2025-12-09T19:49:12.714301091Z [parameters: {'user_id': 'reg-test-user'}]
2025-12-09T19:49:12.714304931Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:12.719363008Z 2025-12-09 19:49:12,719 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:12.719381089Z LINE 3:                         VALUES ('reg-test-user', '{"level": ...
2025-12-09T19:49:12.719385659Z                                         ^
2025-12-09T19:49:12.719389169Z 
2025-12-09T19:49:12.719392849Z [SQL: 
2025-12-09T19:49:12.719396739Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:12.719402969Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:12.719409169Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:12.719416019Z                     ]
2025-12-09T19:49:12.719423159Z [parameters: {'user_id': 'reg-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:12.71942875Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:12.72502115Z 2025-12-09 19:49:12,724 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:12.72503314Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:12.72505298Z                                                              ^
2025-12-09T19:49:12.72505538Z 
2025-12-09T19:49:12.72505758Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:12.725060391Z FROM chat_messages 
2025-12-09T19:49:12.72506332Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:12.725065481Z  LIMIT %(param_1)s]
2025-12-09T19:49:12.725068351Z [parameters: {'session_id_1': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'param_1': 50}]
2025-12-09T19:49:12.725070931Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:12.7306493Z 2025-12-09 19:49:12,730 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER reg-test-user ---
2025-12-09T19:49:12.730664281Z 2025-12-09 19:49:12,730 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:49:12.730705042Z 2025-12-09 19:49:12,730 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:49:12.730783584Z 2025-12-09 19:49:12,730 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:49:12.730797254Z 2025-12-09 19:49:12,730 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:49:12.730867096Z 2025-12-09 19:49:12,730 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:49:12.736120927Z 2025-12-09 19:49:12,735 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:12.736133337Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:12.736137577Z                                                              ^
2025-12-09T19:49:12.736140458Z 
2025-12-09T19:49:12.736143978Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:12.736147878Z FROM chat_messages 
2025-12-09T19:49:12.736152448Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:12.736156218Z  LIMIT %(param_1)s]
2025-12-09T19:49:12.736160068Z [parameters: {'session_id_1': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'param_1': 50}]
2025-12-09T19:49:12.736163578Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:12.736346253Z 2025-12-09 19:49:12,736 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:49:13.924369425Z 2025-12-09 19:49:13,924 - app.services.chat_service - INFO - Processing request for user reg-test-user with role: student
2025-12-09T19:49:13.93014825Z 2025-12-09 19:49:13,930 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:13.93016388Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:13.93016762Z                                                              ^
2025-12-09T19:49:13.93017039Z 
2025-12-09T19:49:13.93017334Z [SQL: 
2025-12-09T19:49:13.93017626Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:13.93017905Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:13.930191981Z                         FROM learning_profile
2025-12-09T19:49:13.930206891Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:13.930209711Z                     ]
2025-12-09T19:49:13.930211531Z [parameters: {'user_id': 'reg-test-user'}]
2025-12-09T19:49:13.930213251Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:13.935847152Z 2025-12-09 19:49:13,935 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:13.935864003Z LINE 3:                         VALUES ('reg-test-user', '{"level": ...
2025-12-09T19:49:13.935867363Z                                         ^
2025-12-09T19:49:13.935869683Z 
2025-12-09T19:49:13.935872053Z [SQL: 
2025-12-09T19:49:13.935874363Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:13.935876603Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:13.935878773Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:13.935881353Z                     ]
2025-12-09T19:49:13.935884303Z [parameters: {'user_id': 'reg-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:13.935886403Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:13.941554275Z 2025-12-09 19:49:13,941 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:13.941567575Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:13.941570785Z                                                              ^
2025-12-09T19:49:13.941573575Z 
2025-12-09T19:49:13.941576656Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:13.941580096Z FROM chat_messages 
2025-12-09T19:49:13.941583716Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:13.941586546Z  LIMIT %(param_1)s]
2025-12-09T19:49:13.941589306Z [parameters: {'session_id_1': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'param_1': 50}]
2025-12-09T19:49:13.941591626Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:13.947407421Z 2025-12-09 19:49:13,947 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER reg-test-user ---
2025-12-09T19:49:13.947427432Z 2025-12-09 19:49:13,947 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:49:13.947476493Z 2025-12-09 19:49:13,947 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:49:13.947512314Z 2025-12-09 19:49:13,947 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:49:13.947536654Z 2025-12-09 19:49:13,947 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:49:13.947570326Z 2025-12-09 19:49:13,947 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:49:13.952810857Z 2025-12-09 19:49:13,952 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:13.952824497Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:13.952829137Z                                                              ^
2025-12-09T19:49:13.952832217Z 
2025-12-09T19:49:13.952835797Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:13.952854947Z FROM chat_messages 
2025-12-09T19:49:13.952858578Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:13.952860768Z  LIMIT %(param_1)s]
2025-12-09T19:49:13.952863368Z [parameters: {'session_id_1': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'param_1': 50}]
2025-12-09T19:49:13.952866198Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:13.953090713Z 2025-12-09 19:49:13,953 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:49:15.001530165Z 2025-12-09 19:49:15,001 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:49:15.001769211Z 2025-12-09 19:49:15,001 - app.api.v1.chat - INFO - Chat response generated in 9.899s (agent: chat)
2025-12-09T19:49:15.008409317Z 2025-12-09 19:49:15,008 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:15.008426987Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:15.008430538Z                                                              ^
2025-12-09T19:49:15.008432698Z 
2025-12-09T19:49:15.008435687Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:15.008441568Z [parameters: {'id': UUID('71fd76b7-89e5-4ef3-a2b7-53123081dda7'), 'session_id': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'role': 'user', 'content': 'Cần những giấy tờ gì?', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 15, 4121, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:15.008444358Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:15.014441498Z 2025-12-09 19:49:15,014 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:15.014457768Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:15.014461068Z                                                              ^
2025-12-09T19:49:15.014463228Z 
2025-12-09T19:49:15.014466168Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:15.014470758Z [parameters: {'id': UUID('16a6c68c-c682-48c3-9307-7d2b88498bdc'), 'session_id': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'role': 'assistant', 'content': 'Bạn ơi, câu hỏi này rộng quá! "Giấy tờ" thì có nhiều loại lắm, tùy vào bạn đang muốn hỏi về cái gì.\n\nBạn muốn hỏi về giấy tờ của **tàu biển** khi r ... (114 characters truncated) ... oặc là **giấy tờ đăng ký tàu** chẳng hạn?\n\nBạn nói rõ hơn xem bạn đang quan tâm đến loại giấy tờ nào, tôi mới chia sẻ kinh nghiệm cho bạn được chứ!', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 15, 10357, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:15.014473898Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:15.01970852Z 2025-12-09 19:49:15,019 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:15.01973486Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:15.019739Z                                                              ^
2025-12-09T19:49:15.019759641Z 
2025-12-09T19:49:15.019762841Z [SQL: 
2025-12-09T19:49:15.019765491Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:15.019768421Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:15.019771761Z                         FROM learning_profile
2025-12-09T19:49:15.019774621Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:15.019777801Z                     ]
2025-12-09T19:49:15.019780571Z [parameters: {'user_id': 'reg-test-user'}]
2025-12-09T19:49:15.019783251Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:15.025224438Z 2025-12-09 19:49:15,025 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:15.025239668Z LINE 3:                         VALUES ('reg-test-user', '{"level": ...
2025-12-09T19:49:15.025244368Z                                         ^
2025-12-09T19:49:15.025247578Z 
2025-12-09T19:49:15.025250788Z [SQL: 
2025-12-09T19:49:15.025254938Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:15.025259948Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:15.025262528Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:15.025265028Z                     ]
2025-12-09T19:49:15.025267559Z [parameters: {'user_id': 'reg-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:15.025269759Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:15.030383016Z 2025-12-09 19:49:15,030 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:15.030393347Z LINE 5:                         WHERE user_id = 'reg-test-user'
2025-12-09T19:49:15.030396547Z                                                 ^
2025-12-09T19:49:15.030399447Z 
2025-12-09T19:49:15.030402197Z [SQL: 
2025-12-09T19:49:15.030404897Z                         UPDATE learning_profile
2025-12-09T19:49:15.030408227Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:49:15.030410787Z                             updated_at = NOW()
2025-12-09T19:49:15.030413627Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:15.030416847Z                     ]
2025-12-09T19:49:15.030418647Z [parameters: {'messages': 2, 'user_id': 'reg-test-user'}]
2025-12-09T19:49:15.030420467Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:16.234069701Z 2025-12-09 19:49:16,233 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:49:16.234290326Z 2025-12-09 19:49:16,234 - app.api.v1.chat - INFO - Chat response generated in 6.404s (agent: chat)
2025-12-09T19:49:16.234482441Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:49:16.240678606Z 2025-12-09 19:49:16,240 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:16.240698806Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:16.240702566Z                                                              ^
2025-12-09T19:49:16.240738378Z 
2025-12-09T19:49:16.240786799Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:16.240795039Z [parameters: {'id': UUID('ef036895-941c-45ea-9d41-0e5555ba8401'), 'session_id': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'role': 'user', 'content': 'Phí bao nhiêu?', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 16, 236711, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:16.240796999Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:16.247005394Z 2025-12-09 19:49:16,246 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:16.247023584Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:16.247027735Z                                                              ^
2025-12-09T19:49:16.247030495Z 
2025-12-09T19:49:16.247034045Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:16.247037565Z [parameters: {'id': UUID('51e0a465-183e-4117-9060-6a22846c5285'), 'session_id': UUID('1cc765bd-b579-466e-b21b-74286e5d54b0'), 'role': 'assistant', 'content': 'Này bạn, bạn hỏi "phí" về vấn đề gì thế? Có phải bạn đang muốn hỏi về **phí đăng ký tàu**, **phí trọng tải**, hay **phí hoa tiêu** không? Cứ nói rõ hơn chút nhé, tôi mới có thể giúp bạn được.', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 16, 242543, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:16.247040425Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:16.253046975Z 2025-12-09 19:49:16,252 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:16.253062266Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:16.253065836Z                                                              ^
2025-12-09T19:49:16.253068676Z 
2025-12-09T19:49:16.253071126Z [SQL: 
2025-12-09T19:49:16.253073826Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:16.253076306Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:16.253079436Z                         FROM learning_profile
2025-12-09T19:49:16.253082396Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:16.253086356Z                     ]
2025-12-09T19:49:16.253089056Z [parameters: {'user_id': 'reg-test-user'}]
2025-12-09T19:49:16.253091776Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:16.259088896Z 2025-12-09 19:49:16,258 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:16.259102387Z LINE 3:                         VALUES ('reg-test-user', '{"level": ...
2025-12-09T19:49:16.259105957Z                                         ^
2025-12-09T19:49:16.259108557Z 
2025-12-09T19:49:16.259111477Z [SQL: 
2025-12-09T19:49:16.259114607Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:16.259117787Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:16.259136867Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:16.259141258Z                     ]
2025-12-09T19:49:16.259144768Z [parameters: {'user_id': 'reg-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:16.259147298Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:16.264147183Z 2025-12-09 19:49:16,263 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "reg-test-user"
2025-12-09T19:49:16.264164303Z LINE 5:                         WHERE user_id = 'reg-test-user'
2025-12-09T19:49:16.264167043Z                                                 ^
2025-12-09T19:49:16.264169253Z 
2025-12-09T19:49:16.264171673Z [SQL: 
2025-12-09T19:49:16.264174593Z                         UPDATE learning_profile
2025-12-09T19:49:16.264177393Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:49:16.264179853Z                             updated_at = NOW()
2025-12-09T19:49:16.264182094Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:16.264184624Z                     ]
2025-12-09T19:49:16.264186744Z [parameters: {'messages': 2, 'user_id': 'reg-test-user'}]
2025-12-09T19:49:16.264188904Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:16.846541789Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:49:16.951841672Z 2025-12-09 19:49:16,951 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:49:16.952347395Z 2025-12-09 19:49:16,952 - app.api.v1.chat - INFO - Chat request from user colregs-test-user (role: student, auth: api_key): Quy tắc 15 COLREGs nói về gì?...
2025-12-09T19:49:16.959389551Z 2025-12-09 19:49:16,959 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:49:20.359162489Z 2025-12-09 19:49:20,358 - app.services.chat_service - INFO - Processing request for user colregs-test-user with role: student
2025-12-09T19:49:20.36521553Z 2025-12-09 19:49:20,365 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:20.365235061Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:20.365241691Z                                                              ^
2025-12-09T19:49:20.365246061Z 
2025-12-09T19:49:20.365250891Z [SQL: 
2025-12-09T19:49:20.365255941Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:20.365260381Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:20.365265952Z                         FROM learning_profile
2025-12-09T19:49:20.365270822Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:20.365276032Z                     ]
2025-12-09T19:49:20.365280502Z [parameters: {'user_id': 'colregs-test-user'}]
2025-12-09T19:49:20.365285292Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:20.370437501Z 2025-12-09 19:49:20,370 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:49:20.370457311Z LINE 3:                         VALUES ('colregs-test-user', '{"leve...
2025-12-09T19:49:20.370462822Z                                         ^
2025-12-09T19:49:20.370466471Z 
2025-12-09T19:49:20.370470492Z [SQL: 
2025-12-09T19:49:20.370504072Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:20.370508553Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:20.370511333Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:20.370514543Z                     ]
2025-12-09T19:49:20.370518223Z [parameters: {'user_id': 'colregs-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:20.370521093Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:20.375976Z 2025-12-09 19:49:20,375 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:20.37598878Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:20.37599269Z                                                              ^
2025-12-09T19:49:20.37599505Z 
2025-12-09T19:49:20.37599774Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:20.37600156Z FROM chat_messages 
2025-12-09T19:49:20.3760055Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:20.37600854Z  LIMIT %(param_1)s]
2025-12-09T19:49:20.3760117Z [parameters: {'session_id_1': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'param_1': 50}]
2025-12-09T19:49:20.376014801Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:20.381393505Z 2025-12-09 19:49:20,381 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER colregs-test-user ---
2025-12-09T19:49:20.381405195Z 2025-12-09 19:49:20,381 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:49:20.381461237Z 2025-12-09 19:49:20,381 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:49:20.381481867Z 2025-12-09 19:49:20,381 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:49:20.381626741Z 2025-12-09 19:49:20,381 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:49:20.381633531Z 2025-12-09 19:49:20,381 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:49:20.386855232Z 2025-12-09 19:49:20,386 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:20.386868782Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:20.386872202Z                                                              ^
2025-12-09T19:49:20.386874202Z 
2025-12-09T19:49:20.386876622Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:20.386879902Z FROM chat_messages 
2025-12-09T19:49:20.386883892Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:20.386886612Z  LIMIT %(param_1)s]
2025-12-09T19:49:20.386889862Z [parameters: {'session_id_1': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'param_1': 50}]
2025-12-09T19:49:20.386892342Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:20.387094178Z 2025-12-09 19:49:20,387 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:49:23.373916168Z 2025-12-09 19:49:23,373 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: []
2025-12-09T19:49:23.374290058Z 2025-12-09 19:49:23,374 - app.api.v1.chat - INFO - Chat response generated in 6.422s (agent: chat)
2025-12-09T19:49:23.374902993Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:49:23.381957319Z 2025-12-09 19:49:23,381 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:23.38197573Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:23.38197925Z                                                              ^
2025-12-09T19:49:23.38198154Z 
2025-12-09T19:49:23.38198445Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:23.38199032Z [parameters: {'id': UUID('82241c4b-6a6f-4709-b781-a6cd9449613e'), 'session_id': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'role': 'user', 'content': 'Quy tắc 15 COLREGs nói về gì?', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 23, 377028, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:23.38199282Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:23.388127724Z 2025-12-09 19:49:23,387 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:23.388143454Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:23.388146914Z                                                              ^
2025-12-09T19:49:23.388149084Z 
2025-12-09T19:49:23.38836042Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:23.38836742Z [parameters: {'id': UUID('fd3e270f-d70d-4396-9afa-c8f80cfa9600'), 'session_id': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'role': 'assistant', 'content': '**Quy tắc 15 (Cắt hướng - Crossing Situation)** này đơn giản lắm bạn ạ, nó nói về việc xử lý tình huống khi hai tàu gặp nhau mà có nguy cơ va chạm và ... (755 characters truncated) ... c độ (stand-on vessel)**.\n\nNhớ nhé, **đèn đỏ thì dừng** – tàu nào thấy đèn đỏ (mạn phải) của tàu kia thì mình phải nhường đường! Dễ hiểu không bạn?', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 23, 383789, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:23.38837058Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:23.394916164Z 2025-12-09 19:49:23,394 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:23.394947234Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:23.394951124Z                                                              ^
2025-12-09T19:49:23.394953574Z 
2025-12-09T19:49:23.394956274Z [SQL: 
2025-12-09T19:49:23.394959005Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:23.394962105Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:23.394964995Z                         FROM learning_profile
2025-12-09T19:49:23.394967905Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:23.394970675Z                     ]
2025-12-09T19:49:23.394988005Z [parameters: {'user_id': 'colregs-test-user'}]
2025-12-09T19:49:23.394991045Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:23.402182075Z 2025-12-09 19:49:23,402 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:49:23.402229056Z LINE 3:                         VALUES ('colregs-test-user', '{"leve...
2025-12-09T19:49:23.402232296Z                                         ^
2025-12-09T19:49:23.402234747Z 
2025-12-09T19:49:23.402237036Z [SQL: 
2025-12-09T19:49:23.402239327Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:23.402242377Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:23.402244667Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:23.402247317Z                     ]
2025-12-09T19:49:23.402250367Z [parameters: {'user_id': 'colregs-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:23.402252597Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:23.407779895Z 2025-12-09 19:49:23,407 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:49:23.407797566Z LINE 5:                         WHERE user_id = 'colregs-test-user'
2025-12-09T19:49:23.407801166Z                                                 ^
2025-12-09T19:49:23.407803746Z 
2025-12-09T19:49:23.407806596Z [SQL: 
2025-12-09T19:49:23.407810236Z                         UPDATE learning_profile
2025-12-09T19:49:23.407812956Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:49:23.407815686Z                             updated_at = NOW()
2025-12-09T19:49:23.407818376Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:23.407821256Z                     ]
2025-12-09T19:49:23.407823826Z [parameters: {'messages': 2, 'user_id': 'colregs-test-user'}]
2025-12-09T19:49:23.407826836Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:24.096805398Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:49:24.250993324Z 2025-12-09 19:49:24,250 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:49:24.251402084Z 2025-12-09 19:49:24,251 - app.api.v1.chat - INFO - Chat request from user colregs-test-user (role: student, auth: api_key): Còn quy tắc 16?...
2025-12-09T19:49:24.258069331Z 2025-12-09 19:49:24,257 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:49:27.686406643Z 2025-12-09 19:49:27,686 - app.services.chat_service - INFO - Processing request for user colregs-test-user with role: student
2025-12-09T19:49:27.692846964Z 2025-12-09 19:49:27,692 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:27.692867745Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:27.692875895Z                                                              ^
2025-12-09T19:49:27.692881115Z 
2025-12-09T19:49:27.692886685Z [SQL: 
2025-12-09T19:49:27.692892416Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:27.692897996Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:27.692905216Z                         FROM learning_profile
2025-12-09T19:49:27.692926977Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:27.692932527Z                     ]
2025-12-09T19:49:27.692935127Z [parameters: {'user_id': 'colregs-test-user'}]
2025-12-09T19:49:27.692937297Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:27.699662225Z 2025-12-09 19:49:27,699 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:49:27.699680155Z LINE 3:                         VALUES ('colregs-test-user', '{"leve...
2025-12-09T19:49:27.699684226Z                                         ^
2025-12-09T19:49:27.699687146Z 
2025-12-09T19:49:27.699690526Z [SQL: 
2025-12-09T19:49:27.699693776Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:27.699697036Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:27.699700256Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:27.699703296Z                     ]
2025-12-09T19:49:27.699708446Z [parameters: {'user_id': 'colregs-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:27.699711696Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:27.707351087Z 2025-12-09 19:49:27,707 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:27.707366728Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:27.707371458Z                                                              ^
2025-12-09T19:49:27.707374828Z 
2025-12-09T19:49:27.707378218Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:27.707381948Z FROM chat_messages 
2025-12-09T19:49:27.707388248Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:27.707392028Z  LIMIT %(param_1)s]
2025-12-09T19:49:27.707395858Z [parameters: {'session_id_1': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'param_1': 50}]
2025-12-09T19:49:27.707399179Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:27.713341517Z 2025-12-09 19:49:27,713 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER colregs-test-user ---
2025-12-09T19:49:27.713361697Z 2025-12-09 19:49:27,713 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:49:27.713370318Z 2025-12-09 19:49:27,713 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:49:27.713430009Z 2025-12-09 19:49:27,713 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:49:27.71345645Z 2025-12-09 19:49:27,713 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:49:27.71348402Z 2025-12-09 19:49:27,713 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:49:27.718834814Z 2025-12-09 19:49:27,718 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:27.718844085Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:27.718847975Z                                                              ^
2025-12-09T19:49:27.718850775Z 
2025-12-09T19:49:27.718853695Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:27.718884466Z FROM chat_messages 
2025-12-09T19:49:27.718887366Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:27.718889166Z  LIMIT %(param_1)s]
2025-12-09T19:49:27.718891186Z [parameters: {'session_id_1': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'param_1': 50}]
2025-12-09T19:49:27.718892976Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:27.71906555Z 2025-12-09 19:49:27,718 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:49:29.449665732Z 2025-12-09 19:49:29,449 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'Quy tắc 16 COLREGs'})
2025-12-09T19:49:29.450261137Z 2025-12-09 19:49:29,450 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: Quy tắc 16 COLREGs
2025-12-09T19:49:29.450291178Z 2025-12-09 19:49:29,450 - app.services.hybrid_search_service - INFO - Hybrid search for: Quy tắc 16 COLREGs
2025-12-09T19:49:29.45036696Z 2025-12-09 19:49:29,450 - app.services.hybrid_search_service - INFO - Detected rule numbers: ['16']
2025-12-09T19:49:29.781667466Z 2025-12-09 19:49:29,781 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:49:29.894736954Z 2025-12-09 19:49:29,894 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:49:29.896324093Z 2025-12-09 19:49:29,896 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:49:29.896387355Z 2025-12-09 19:49:29,896 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: quy | rule | regulation | tắc | 16 | colregs
2025-12-09T19:49:30.027613907Z 2025-12-09 19:49:30,027 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: Quy tắc 16 COLREGs
2025-12-09T19:49:30.029043673Z 2025-12-09 19:49:30,028 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:49:30.029371831Z 2025-12-09 19:49:30,029 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (0 in both, 3 title-boosted)
2025-12-09T19:49:30.029387951Z 2025-12-09 19:49:30,029 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:49:30.029521855Z 2025-12-09 19:49:30,029 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: e7fba5e7-c797-4fcf-89e3-bd993c6397bf
2025-12-09T19:49:30.116853189Z 2025-12-09 19:49:30,116 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:49:34.346908702Z 2025-12-09 19:49:34,346 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:49:34.425902488Z 2025-12-09 19:49:34,425 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:49:34.426028661Z 2025-12-09 19:49:34,425 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:49:40.374646676Z 2025-12-09 19:49:40,374 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:49:40.374688127Z 2025-12-09 19:49:40,374 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'Quy tắc 16 COLREGs'}, 'result': 'Về Quy tắc 16 COLREGs, thông tin tra cứu được không cung cấp chi tiết về quy tắc này.\n\nThông tin số '}]
2025-12-09T19:49:40.375268261Z 2025-12-09 19:49:40,375 - app.api.v1.chat - INFO - Chat response generated in 16.124s (agent: rag)
2025-12-09T19:49:40.375597389Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:49:40.384642705Z 2025-12-09 19:49:40,383 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:40.384668386Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:40.384671886Z                                                              ^
2025-12-09T19:49:40.384673976Z 
2025-12-09T19:49:40.384676746Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:40.384681186Z [parameters: {'id': UUID('ef24a059-a072-4470-94b5-03b10fa96f88'), 'session_id': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'role': 'user', 'content': 'Còn quy tắc 16?', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 40, 378717, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:40.384683846Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:40.390774019Z 2025-12-09 19:49:40,390 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:49:40.390792399Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:49:40.390795639Z                                                              ^
2025-12-09T19:49:40.39079779Z 
2025-12-09T19:49:40.39083302Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:49:40.39083812Z [parameters: {'id': UUID('223e4c66-35f9-45bc-ae30-4e9ce8331929'), 'session_id': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'role': 'assistant', 'content': '<thinking>\nThe user asked about "Quy tắc 16". I used `tool_maritime_search` to look it up. The search result, however, returned information about "V ... (1856 characters truncated) ... Quy tắc này là để đảm bảo rằng khi một tàu có nghĩa vụ nhường đường, họ sẽ làm điều đó một cách hiệu quả nhất, tránh để tình huống trở nên nguy hiểm.', 'created_at': datetime.datetime(2025, 12, 9, 19, 49, 40, 386367, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:49:40.390841131Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:40.396336098Z 2025-12-09 19:49:40,396 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:40.396352629Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:40.396356209Z                                                              ^
2025-12-09T19:49:40.396358338Z 
2025-12-09T19:49:40.396360609Z [SQL: 
2025-12-09T19:49:40.396362869Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:40.396365259Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:40.396367909Z                         FROM learning_profile
2025-12-09T19:49:40.396370009Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:40.396372189Z                     ]
2025-12-09T19:49:40.396374289Z [parameters: {'user_id': 'colregs-test-user'}]
2025-12-09T19:49:40.396390229Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:40.402641636Z 2025-12-09 19:49:40,402 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:49:40.402658546Z LINE 3:                         VALUES ('colregs-test-user', '{"leve...
2025-12-09T19:49:40.402662256Z                                         ^
2025-12-09T19:49:40.402664596Z 
2025-12-09T19:49:40.402667156Z [SQL: 
2025-12-09T19:49:40.402669787Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:40.402673396Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:40.402676477Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:40.402679307Z                     ]
2025-12-09T19:49:40.402681547Z [parameters: {'user_id': 'colregs-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:40.402683367Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:40.408043841Z 2025-12-09 19:49:40,407 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:49:40.408057821Z LINE 5:                         WHERE user_id = 'colregs-test-user'
2025-12-09T19:49:40.408061281Z                                                 ^
2025-12-09T19:49:40.408064061Z 
2025-12-09T19:49:40.408066801Z [SQL: 
2025-12-09T19:49:40.408070082Z                         UPDATE learning_profile
2025-12-09T19:49:40.408072662Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:49:40.408075232Z                             updated_at = NOW()
2025-12-09T19:49:40.408078012Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:40.408080872Z                     ]
2025-12-09T19:49:40.408083702Z [parameters: {'messages': 2, 'user_id': 'colregs-test-user'}]
2025-12-09T19:49:40.408086632Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:40.984639202Z 14.249.192.241:0 - "POST /api/v1/chat/ HTTP/1.1" 307
2025-12-09T19:49:41.086440388Z 2025-12-09 19:49:41,086 - app.core.security - WARNING - No API key configured - allowing all requests
2025-12-09T19:49:41.086999562Z 2025-12-09 19:49:41,086 - app.api.v1.chat - INFO - Chat request from user colregs-test-user (role: student, auth: api_key): Quy tắc 17 thì sao?...
2025-12-09T19:49:41.096961801Z 2025-12-09 19:49:41,096 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:49:45.030618691Z 2025-12-09 19:49:45,030 - app.services.chat_service - INFO - Processing request for user colregs-test-user with role: student
2025-12-09T19:49:45.036621751Z 2025-12-09 19:49:45,036 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:49:45.036638042Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:49:45.036642032Z                                                              ^
2025-12-09T19:49:45.036644472Z 
2025-12-09T19:49:45.036647082Z [SQL: 
2025-12-09T19:49:45.036649872Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:49:45.036652732Z                                total_sessions, total_messages, updated_at
2025-12-09T19:49:45.036656302Z                         FROM learning_profile
2025-12-09T19:49:45.036659102Z                         WHERE user_id = %(user_id)s
2025-12-09T19:49:45.036670703Z                     ]
2025-12-09T19:49:45.036673293Z [parameters: {'user_id': 'colregs-test-user'}]
2025-12-09T19:49:45.036677043Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:45.042222471Z 2025-12-09 19:49:45,042 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:49:45.042242472Z LINE 3:                         VALUES ('colregs-test-user', '{"leve...
2025-12-09T19:49:45.042246752Z                                         ^
2025-12-09T19:49:45.042249722Z 
2025-12-09T19:49:45.042252962Z [SQL: 
2025-12-09T19:49:45.042255952Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:49:45.042259442Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:49:45.042262142Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:49:45.042265483Z                     ]
2025-12-09T19:49:45.042268412Z [parameters: {'user_id': 'colregs-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:49:45.042271153Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:49:45.048411696Z 2025-12-09 19:49:45,048 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:45.048427057Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:45.048431007Z                                                              ^
2025-12-09T19:49:45.048433637Z 
2025-12-09T19:49:45.048436737Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:45.048440667Z FROM chat_messages 
2025-12-09T19:49:45.048444507Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:45.048447527Z  LIMIT %(param_1)s]
2025-12-09T19:49:45.048451067Z [parameters: {'session_id_1': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'param_1': 50}]
2025-12-09T19:49:45.048453817Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:45.054083308Z 2025-12-09 19:49:45,053 - app.services.chat_service - INFO - --- PREPARING PROMPT FOR USER colregs-test-user ---
2025-12-09T19:49:45.054097628Z 2025-12-09 19:49:45,054 - app.services.chat_service - INFO - Detected Name: UNKNOWN
2025-12-09T19:49:45.054355615Z 2025-12-09 19:49:45,054 - app.services.chat_service - INFO - Retrieved History Length: 0 chars
2025-12-09T19:49:45.054361705Z 2025-12-09 19:49:45,054 - app.services.chat_service - INFO - Semantic Context Length: 0 chars
2025-12-09T19:49:45.054365015Z 2025-12-09 19:49:45,054 - app.services.chat_service - INFO - -------------------------------------------
2025-12-09T19:49:45.054367415Z 2025-12-09 19:49:45,054 - app.services.chat_service - INFO - [UNIFIED AGENT] Processing with LLM-driven orchestration (ReAct)
2025-12-09T19:49:45.060116979Z 2025-12-09 19:49:45,060 - app.repositories.chat_history_repository - ERROR - Failed to get messages: (psycopg2.errors.UndefinedColumn) column chat_messages.is_blocked does not exist
2025-12-09T19:49:45.060127969Z LINE 1: ... chat_messages.content, chat_messages.created_at, chat_messa...
2025-12-09T19:49:45.060131899Z                                                              ^
2025-12-09T19:49:45.060134509Z 
2025-12-09T19:49:45.060137599Z [SQL: SELECT chat_messages.id, chat_messages.session_id, chat_messages.role, chat_messages.content, chat_messages.created_at, chat_messages.is_blocked, chat_messages.block_reason 
2025-12-09T19:49:45.06015472Z FROM chat_messages 
2025-12-09T19:49:45.06015852Z WHERE chat_messages.session_id = %(session_id_1)s::UUID AND chat_messages.is_blocked = false ORDER BY chat_messages.created_at DESC 
2025-12-09T19:49:45.06016133Z  LIMIT %(param_1)s]
2025-12-09T19:49:45.06016467Z [parameters: {'session_id_1': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'param_1': 50}]
2025-12-09T19:49:45.06016756Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:49:45.060353315Z 2025-12-09 19:49:45,060 - app.engine.unified_agent - INFO - [ReAct] Iteration 1
2025-12-09T19:49:46.593323115Z 2025-12-09 19:49:46,593 - app.engine.unified_agent - INFO - [ReAct] Calling: tool_maritime_search({'query': 'Quy tắc 17 COLREGs'})
2025-12-09T19:49:46.593907029Z 2025-12-09 19:49:46,593 - app.engine.unified_agent - INFO - [TOOL] Maritime Search: Quy tắc 17 COLREGs
2025-12-09T19:49:46.59396145Z 2025-12-09 19:49:46,593 - app.services.hybrid_search_service - INFO - Hybrid search for: Quy tắc 17 COLREGs
2025-12-09T19:49:46.593978111Z 2025-12-09 19:49:46,593 - app.services.hybrid_search_service - INFO - Detected rule numbers: ['17']
2025-12-09T19:49:46.903064611Z 2025-12-09 19:49:46,902 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents "HTTP/1.1 200 OK"
2025-12-09T19:49:47.009812431Z 2025-12-09 19:49:47,009 - app.repositories.dense_search_repository - INFO - Dense search returned 10 results
2025-12-09T19:49:47.011269677Z 2025-12-09 19:49:47,011 - app.services.hybrid_search_service - INFO - Dense search returned 10 results
2025-12-09T19:49:47.011343659Z 2025-12-09 19:49:47,011 - app.repositories.sparse_search_repository - INFO - Sparse search tsquery: quy | rule | regulation | tắc | 17 | colregs
2025-12-09T19:49:47.222833288Z 2025-12-09 19:49:47,222 - app.repositories.sparse_search_repository - INFO - PostgreSQL sparse search returned 10 results for query: Quy tắc 17 COLREGs
2025-12-09T19:49:47.224285625Z 2025-12-09 19:49:47,224 - app.services.hybrid_search_service - INFO - Sparse search returned 10 results
2025-12-09T19:49:47.224521901Z 2025-12-09 19:49:47,224 - app.engine.rrf_reranker - INFO - RRF merged 10 dense + 10 sparse -> 5 results (2 in both, 2 title-boosted)
2025-12-09T19:49:47.224567392Z 2025-12-09 19:49:47,224 - app.services.hybrid_search_service - INFO - Hybrid search completed: 5 results, method=hybrid
2025-12-09T19:49:47.224761656Z 2025-12-09 19:49:47,224 - app.engine.tools.rag_tool - WARNING - Skipping result with empty title/content: 6d7a6837-769d-4079-b0b7-7cadfe6113ef
2025-12-09T19:49:47.275172268Z 2025-12-09 19:49:47,275 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2025-12-09T19:49:52.49279105Z 2025-12-09 19:49:52,492 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
2025-12-09T19:49:52.536633826Z 2025-12-09 19:49:52,536 - app.engine.unified_agent - INFO - [TOOL] Saved 5 sources for API response
2025-12-09T19:49:52.53677819Z 2025-12-09 19:49:52,536 - app.engine.unified_agent - INFO - [ReAct] Iteration 2
2025-12-09T19:50:00.938476496Z 2025-12-09 19:50:00,938 - app.services.chat_service - INFO - [UNIFIED AGENT] Retrieved 5 sources for API response
2025-12-09T19:50:00.938533928Z 2025-12-09 19:50:00,938 - app.services.chat_service - INFO - [UNIFIED AGENT] Tools used: [{'name': 'tool_maritime_search', 'args': {'query': 'Quy tắc 17 COLREGs'}, 'result': 'Về Quy tắc 17 COLREGs, kiến thức tra cứu được cung cấp không chứa thông tin liên quan đến quy tắc nà'}]
2025-12-09T19:50:00.939798169Z 2025-12-09 19:50:00,939 - app.api.v1.chat - INFO - Chat response generated in 19.852s (agent: rag)
2025-12-09T19:50:00.93984023Z 14.249.192.241:0 - "POST /api/v1/chat HTTP/1.1" 200
2025-12-09T19:50:00.946427375Z 2025-12-09 19:50:00,946 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:50:00.946442685Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:50:00.946446975Z                                                              ^
2025-12-09T19:50:00.946449515Z 
2025-12-09T19:50:00.946453346Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:50:00.946463016Z [parameters: {'id': UUID('42e8bc88-f2f5-40ab-923e-3ea8e01973c1'), 'session_id': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'role': 'user', 'content': 'Quy tắc 17 thì sao?', 'created_at': datetime.datetime(2025, 12, 9, 19, 50, 0, 942230, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:50:00.946465966Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:50:00.95263942Z 2025-12-09 19:50:00,952 - app.repositories.chat_history_repository - ERROR - Failed to save message: (psycopg2.errors.UndefinedColumn) column "is_blocked" of relation "chat_messages" does not exist
2025-12-09T19:50:00.95265163Z LINE 1: ...sages (id, session_id, role, content, created_at, is_blocked...
2025-12-09T19:50:00.952654731Z                                                              ^
2025-12-09T19:50:00.952657301Z 
2025-12-09T19:50:00.952660631Z [SQL: INSERT INTO chat_messages (id, session_id, role, content, created_at, is_blocked, block_reason) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s, %(content)s, %(created_at)s, %(is_blocked)s, %(block_reason)s)]
2025-12-09T19:50:00.952663791Z [parameters: {'id': UUID('91266ec9-3b45-4319-9020-d17c5cbce645'), 'session_id': UUID('129e4a24-9085-43cb-a6e9-06fe6fb1b17e'), 'role': 'assistant', 'content': 'Tiếp tục với **Quy tắc 17 (Hành động của tàu được quyền ưu tiên)** trong COLREGs, đây là một quy tắc cực kỳ quan trọng đó bạn. Công cụ tìm kiếm của t ... (2603 characters truncated) ...  toàn là trên hết mà, đúng không?\n\nBạn có thấy ví dụ trên boong tàu hay ngoài đường phố dễ hình dung hơn không? Cứ hỏi nhé, tôi sẽ giải thích thêm!', 'created_at': datetime.datetime(2025, 12, 9, 19, 50, 0, 948264, tzinfo=datetime.timezone.utc), 'is_blocked': False, 'block_reason': None}]
2025-12-09T19:50:00.952666371Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:50:00.958277341Z 2025-12-09 19:50:00,958 - app.repositories.learning_profile_repository - ERROR - Failed to get learning profile: (psycopg2.errors.UndefinedColumn) column "weak_areas" does not exist
2025-12-09T19:50:00.95860463Z LINE 2: ...                      SELECT user_id, attributes, weak_areas...
2025-12-09T19:50:00.95860955Z                                                              ^
2025-12-09T19:50:00.9586121Z 
2025-12-09T19:50:00.95861479Z [SQL: 
2025-12-09T19:50:00.95861798Z                         SELECT user_id, attributes, weak_areas, strong_areas, 
2025-12-09T19:50:00.95862095Z                                total_sessions, total_messages, updated_at
2025-12-09T19:50:00.95862494Z                         FROM learning_profile
2025-12-09T19:50:00.95862776Z                         WHERE user_id = %(user_id)s
2025-12-09T19:50:00.95863085Z                     ]
2025-12-09T19:50:00.95863321Z [parameters: {'user_id': 'colregs-test-user'}]
2025-12-09T19:50:00.95863573Z (Background on this error at: https://sqlalche.me/e/20/f405)
2025-12-09T19:50:00.96421976Z 2025-12-09 19:50:00,963 - app.repositories.learning_profile_repository - ERROR - Failed to create learning profile: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:50:00.96423112Z LINE 3:                         VALUES ('colregs-test-user', '{"leve...
2025-12-09T19:50:00.9642353Z                                         ^
2025-12-09T19:50:00.96423781Z 
2025-12-09T19:50:00.964240331Z [SQL: 
2025-12-09T19:50:00.964243911Z                         INSERT INTO learning_profile (user_id, attributes)
2025-12-09T19:50:00.964247111Z                         VALUES (%(user_id)s, %(attributes)s)
2025-12-09T19:50:00.964249551Z                         ON CONFLICT (user_id) DO NOTHING
2025-12-09T19:50:00.964269391Z                     ]
2025-12-09T19:50:00.964272921Z [parameters: {'user_id': 'colregs-test-user', 'attributes': '{"level": "beginner"}'}]
2025-12-09T19:50:00.964275901Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:50:00.969551373Z 2025-12-09 19:50:00,969 - app.repositories.learning_profile_repository - ERROR - Failed to increment stats: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type uuid: "colregs-test-user"
2025-12-09T19:50:00.969562404Z LINE 5:                         WHERE user_id = 'colregs-test-user'
2025-12-09T19:50:00.969565653Z                                                 ^
2025-12-09T19:50:00.969568324Z 
2025-12-09T19:50:00.969571014Z [SQL: 
2025-12-09T19:50:00.969574244Z                         UPDATE learning_profile
2025-12-09T19:50:00.969577064Z                         SET total_messages = total_messages + %(messages)s,
2025-12-09T19:50:00.969579864Z                             updated_at = NOW()
2025-12-09T19:50:00.969582614Z                         WHERE user_id = %(user_id)s
2025-12-09T19:50:00.969585884Z                     ]
2025-12-09T19:50:00.969588624Z [parameters: {'messages': 2, 'user_id': 'colregs-test-user'}]
2025-12-09T19:50:00.969591064Z (Background on this error at: https://sqlalche.me/e/20/9h9h)
2025-12-09T19:50:12.921520072Z 116.203.134.67:0 - "GET /api/v1/health HTTP/1.1" 200