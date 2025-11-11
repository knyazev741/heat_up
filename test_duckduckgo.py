"""
Простой тест DuckDuckGo для диагностики
"""

from duckduckgo_search import DDGS
import time

# Тестовые запросы
queries = [
    "telegram groups Kazan Russia",
    "t.me kazan chat",
    "казань telegram группа site:t.me",
]

print("Testing DuckDuckGo search...")
print("=" * 80)

with DDGS() as ddgs:
    for q in queries:
        print(f"\nQuery: {q}")
        print("-" * 80)
        
        try:
            results = list(ddgs.text(q, max_results=5))
            print(f"Results: {len(results)}")
            
            if results:
                for i, r in enumerate(results, 1):
                    print(f"\n{i}. {r.get('title', 'N/A')}")
                    print(f"   URL: {r.get('href', 'N/A')}")
                    print(f"   Snippet: {r.get('body', 'N/A')[:100]}")
            else:
                print("  No results found")
        
        except Exception as e:
            print(f"  ERROR: {e}")
        
        time.sleep(2)  # Задержка между запросами

print("\n" + "=" * 80)
print("Test completed")




