"""
Sprint 71: Natural conversation test — checks memory, routing, and naturalness.

Tests a 7-turn casual conversation (no domain-specific topics).
"""
import asyncio
import httpx
import json
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

API = 'http://localhost:8000/api/v1'
HEADERS = {
    'X-API-Key': 'local-dev-key',
    'Content-Type': 'application/json',
}

MESSAGES = [
    'Xin chào bạn, mình là Minh, rất vui được gặp bạn!',
    'Mình năm nay 25 tuổi, đang làm kỹ sư phần mềm ở Sài Gòn. Bạn có thể gọi mình là Minh nhé.',
    'Hôm nay trời đẹp quá, bạn nghĩ sao?',
    'Mình thích đọc sách lắm, đặc biệt là sách về AI và machine learning. Bạn có gợi ý sách gì hay không?',
    'À bạn ơi, mình cũng thích chơi game nữa. Bạn biết game nào hay không?',
    'Bạn có nhớ tên mình không? Và mình làm nghề gì?',
    'Cảm ơn bạn nhiều nhé! Hẹn gặp lại!',
]

async def test_conversation():
    async with httpx.AsyncClient(timeout=120) as client:
        for i, msg in enumerate(MESSAGES, 1):
            print(f'\n{"="*70}')
            print(f'[Turn {i}] User: {msg}')
            print("-"*70)

            start = time.time()
            try:
                resp = await client.post(
                    f'{API}/chat',
                    headers=HEADERS,
                    json={
                        'message': msg,
                        'user_id': 'test-user-minh',
                        'role': 'student',
                        'session_id': 'session-natural-chat-v2',
                    }
                )
                elapsed = time.time() - start

                if resp.status_code == 200:
                    data = resp.json()
                    answer = data.get('data', {}).get('answer', 'NO ANSWER')
                    metadata = data.get('metadata', {})
                    agent = metadata.get('agent_type', '?')
                    proc_time = metadata.get('processing_time', 0)
                    trace = metadata.get('reasoning_trace', {})
                    route_step = None
                    if trace and trace.get('steps'):
                        for s in trace['steps']:
                            if s.get('step_name') == 'routing':
                                route_step = s.get('details', {}).get('routed_to', '?')

                    suggested = data.get('data', {}).get('suggested_questions', [])

                    print(f'[Turn {i}] Wiii ({elapsed:.1f}s, agent={agent}, route={route_step}):')
                    print(answer[:1000])
                    if suggested:
                        print(f'  Suggested: {suggested[:2]}')
                else:
                    print(f'[Turn {i}] ERROR {resp.status_code}: {resp.text[:500]}')
            except Exception as e:
                elapsed = time.time() - start
                print(f'[Turn {i}] EXCEPTION ({elapsed:.1f}s): {type(e).__name__}: {e}')

    print(f'\n{"="*70}')
    print("CONVERSATION TEST COMPLETE")

if __name__ == '__main__':
    asyncio.run(test_conversation())
