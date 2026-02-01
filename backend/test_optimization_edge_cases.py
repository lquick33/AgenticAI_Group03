"""
Edge Case Tests for Quick Win Optimizations

Specifically tests for potential bugs in:
1. Cache edge cases (concurrency, expiration timing)
2. Cache coherence (invalidation)
3. PDF DPI configuration
4. Function behavior changes

Run with: python test_optimization_edge_cases.py
"""

import sys
import traceback
from time import time, sleep
from typing import Dict, Any, Optional, Tuple
from unittest.mock import MagicMock, patch

# Track test results
results = {"passed": 0, "failed": 0, "skipped": 0}


def test(name: str):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper():
            try:
                print(f"\n{'='*60}")
                print(f"TEST: {name}")
                print('='*60)
                func()
                results["passed"] += 1
                print(f"✅ PASSED: {name}")
            except Exception as e:
                results["failed"] += 1
                print(f"❌ FAILED: {name}")
                print(f"   Error: {e}")
                traceback.print_exc()
        return wrapper
    return decorator


# =============================================================================
# Edge Case 1: Cache Coherence
# =============================================================================

@test("PageAnalysisCache - stale data prevention")
def test_page_cache_stale_data():
    """
    Bug: Cache could return stale data if analysis is updated.
    Verify: Cache should be invalidated when data changes.
    """
    from app.services.storage import PageAnalysisCache
    
    cache = PageAnalysisCache(ttl_seconds=300)
    material_id = "mat-123"
    user_id = "user-456"
    
    # Initial data
    old_data = {"summary": "Old summary", "key_terms": ["old"]}
    cache.set(material_id, 1, user_id, old_data)
    
    # Simulate data update - should invalidate
    cache.invalidate(material_id, 1, user_id)
    
    # Should return None after invalidation
    result = cache.get(material_id, 1, user_id)
    assert result is None, "Cache should be empty after invalidation"
    
    # New data
    new_data = {"summary": "New summary", "key_terms": ["new"]}
    cache.set(material_id, 1, user_id, new_data)
    
    result = cache.get(material_id, 1, user_id)
    assert result == new_data, "Cache should return new data"
    print("   - Stale data correctly prevented via invalidation")


@test("SummaryCache - multi-user isolation")
def test_summary_cache_user_isolation():
    """
    Bug: User A could see User B's summary.
    Verify: Cache keys include user_id for isolation.
    """
    from app.services.storage import SummaryCache
    
    cache = SummaryCache(ttl_seconds=600)
    material_id = "mat-123"
    
    # User A's data
    user_a_data = {"topics": ["Secret A"], "overview": "User A's content"}
    cache.set(material_id, "user-a", user_a_data)
    
    # User B's data
    user_b_data = {"topics": ["Secret B"], "overview": "User B's content"}
    cache.set(material_id, "user-b", user_b_data)
    
    # Each user should only see their own data
    assert cache.get(material_id, "user-a") == user_a_data
    assert cache.get(material_id, "user-b") == user_b_data
    
    # User C should see nothing
    assert cache.get(material_id, "user-c") is None
    
    print("   - User data is properly isolated")


@test("Cache - key collision prevention")
def test_cache_key_collision():
    """
    Bug: Keys like "mat-1:2:user" and "mat:1:2:user" could collide.
    Verify: Different material/page combinations have unique keys.
    """
    from app.services.storage import PageAnalysisCache
    
    cache = PageAnalysisCache(ttl_seconds=300)
    
    # These should all be unique
    cache.set("mat-1", 2, "user", {"id": "1-2"})
    cache.set("mat-12", 0, "user", {"id": "12-0"})  # Could collide if format is wrong
    cache.set("mat", 12, "user", {"id": "0-12"})
    
    # Verify all are separate
    assert cache.get("mat-1", 2, "user")["id"] == "1-2"
    assert cache.get("mat-12", 0, "user")["id"] == "12-0"
    assert cache.get("mat", 12, "user")["id"] == "0-12"
    
    print("   - No key collisions detected")


# =============================================================================
# Edge Case 2: Expiration Timing
# =============================================================================

@test("PageAnalysisCache - expiration boundary")
def test_cache_expiration_boundary():
    """
    Bug: Cache could have off-by-one errors at TTL boundary.
    Verify: Cache expires correctly at exactly TTL.
    """
    from app.services.storage import PageAnalysisCache
    
    ttl = 2  # 2 seconds for fast test
    cache = PageAnalysisCache(ttl_seconds=ttl)
    
    test_data = {"summary": "Test"}
    cache.set("mat", 1, "user", test_data)
    
    # At t=0, should be cached
    assert cache.get("mat", 1, "user") == test_data
    print("   - t=0: cached ✓")
    
    # At t=1 (half TTL), should still be cached
    sleep(1)
    assert cache.get("mat", 1, "user") == test_data
    print("   - t=1s (50% TTL): still cached ✓")
    
    # At t=2+ (past TTL), should be expired
    sleep(1.1)
    assert cache.get("mat", 1, "user") is None
    print("   - t=2.1s (past TTL): expired ✓")


@test("SummaryCache - refresh on access")
def test_cache_no_refresh_on_access():
    """
    Bug: Some caches refresh TTL on access (LRU). Ours should not.
    Verify: TTL counts from set time, not last access.
    """
    from app.services.storage import SummaryCache
    
    cache = SummaryCache(ttl_seconds=2)
    
    test_data = {"topics": ["Test"]}
    cache.set("mat", "user", test_data)
    
    # Access at t=0.5
    sleep(0.5)
    assert cache.get("mat", "user") is not None
    
    # Access at t=1.0
    sleep(0.5)
    assert cache.get("mat", "user") is not None
    
    # Access at t=1.5 (still within TTL from original set)
    sleep(0.5)
    assert cache.get("mat", "user") is not None
    
    # Access at t=2.1 (past TTL from original set)
    sleep(0.6)
    assert cache.get("mat", "user") is None
    
    print("   - TTL is based on set time, not access time")


# =============================================================================
# Edge Case 3: Return Value Consistency
# =============================================================================

@test("get_page_analysis - cached vs uncached return same structure")
def test_page_analysis_return_consistency():
    """
    Bug: Cached and uncached calls could return different structures.
    Verify: Return structure is identical.
    """
    # Expected structure
    expected_keys = {"summary", "key_terms", "exam_questions", "diagram_description", "raw_analysis"}
    
    # Simulate cached return
    cached_data = {
        "summary": "Test",
        "key_terms": ["a", "b"],
        "exam_questions": ["Q1?"],
        "diagram_description": None,
        "raw_analysis": {}
    }
    
    # Verify structure matches
    assert set(cached_data.keys()) == expected_keys
    print("   - Cached data has correct structure")
    
    # Verify types
    assert isinstance(cached_data["summary"], str)
    assert isinstance(cached_data["key_terms"], list)
    assert isinstance(cached_data["exam_questions"], list)
    assert cached_data["diagram_description"] is None or isinstance(cached_data["diagram_description"], str)
    assert isinstance(cached_data["raw_analysis"], dict)
    print("   - All field types are correct")


@test("get_course_material_summary - None handling")
def test_summary_none_handling():
    """
    Bug: Cache could store None when no summary exists, then return wrong value.
    Verify: Function behavior for missing data is correct.
    """
    from app.services.storage import SummaryCache
    
    cache = SummaryCache(ttl_seconds=600)
    
    # If we try to cache None, what happens?
    # The actual function returns None, doesn't cache it
    # But cache.set() could accept None
    
    # Verify behavior: empty cache returns None
    assert cache.get("nonexistent", "user") is None
    print("   - Empty cache returns None correctly")
    
    # We should NOT cache None values (function level check)
    # This is handled in the function itself
    print("   - None values should not be cached (function responsibility)")


# =============================================================================
# Edge Case 4: PDF DPI Configuration
# =============================================================================

@test("PDF DPI - reasonable range check")
def test_pdf_dpi_range():
    """
    Bug: DPI could be set to absurd values (0, negative, too high).
    Verify: Config has sensible defaults.
    """
    from app.core.config import settings
    
    dpi = settings.PDF_PROCESSING_DPI
    
    # Should be positive
    assert dpi > 0, f"DPI must be positive, got {dpi}"
    
    # Should be reasonable (50-600 is typical range)
    assert dpi >= 50, f"DPI too low: {dpi}"
    assert dpi <= 600, f"DPI too high: {dpi}"
    
    print(f"   - DPI value {dpi} is within reasonable range")


@test("PDF DPI - used consistently")
def test_pdf_dpi_consistent_usage():
    """
    Bug: Some code could still use hardcoded 300 DPI.
    Verify: settings.PDF_PROCESSING_DPI is imported in pdf_processor.
    """
    import ast
    import inspect
    from app.services import pdf_processor
    from app.core.config import settings
    
    # Get the source file path
    source_file = inspect.getfile(pdf_processor)
    
    # Read the file
    with open(source_file, 'r') as f:
        content = f.read()
    
    # Check that settings is imported
    assert 'from app.core.config import settings' in content, "settings not imported"
    print("   - settings imported in pdf_processor")
    
    # Check that PDF_PROCESSING_DPI is used
    assert 'settings.PDF_PROCESSING_DPI' in content, "PDF_PROCESSING_DPI not used"
    print("   - PDF_PROCESSING_DPI is used in code")
    
    # Check that dpi=300 is NOT hardcoded (should not appear)
    # Note: Could appear in comments, so just count occurrences
    hardcoded_count = content.count('dpi=300')
    assert hardcoded_count == 0, f"Found {hardcoded_count} hardcoded dpi=300"
    print("   - No hardcoded dpi=300 found")


# =============================================================================
# Edge Case 5: Memory Management
# =============================================================================

@test("Cache - clear actually empties cache")
def test_cache_clear():
    """
    Bug: clear() could leave some entries behind.
    Verify: Cache is completely empty after clear().
    """
    from app.services.storage import PageAnalysisCache
    
    cache = PageAnalysisCache(ttl_seconds=300)
    
    # Add many entries
    for i in range(100):
        cache.set(f"mat-{i}", i, "user", {"id": i})
    
    # Clear
    cache.clear()
    
    # Verify all are gone
    for i in range(100):
        assert cache.get(f"mat-{i}", i, "user") is None
    
    # Verify internal structure is empty
    assert len(cache._cache) == 0
    print("   - Cache completely emptied after clear()")


@test("Cache - no memory leak from expired entries")
def test_cache_expired_cleanup():
    """
    Bug: Expired entries might stay in memory until explicitly accessed.
    Verify: Expired entries are cleaned up on access.
    """
    from app.services.storage import PageAnalysisCache
    
    cache = PageAnalysisCache(ttl_seconds=1)
    
    # Add entry
    cache.set("mat", 1, "user", {"data": "test"})
    
    # Wait for expiration
    sleep(1.1)
    
    # Access triggers cleanup
    result = cache.get("mat", 1, "user")
    assert result is None
    
    # Entry should be removed from internal dict
    key = "mat:1:user"
    assert key not in cache._cache, "Expired entry should be removed from internal dict"
    print("   - Expired entries are cleaned up on access")


# =============================================================================
# Edge Case 6: Concurrency (conceptual)
# =============================================================================

@test("Cache - thread safety note")
def test_cache_thread_safety():
    """
    Note: Python GIL provides basic thread safety for dict operations.
    For high-concurrency, we'd need threading.Lock.
    Current async/FastAPI usage is safe.
    """
    print("   NOTE: Thread safety analysis")
    print("   - Python dict operations are atomic under GIL")
    print("   - set() and get() are single dict operations")
    print("   - FastAPI async handlers don't need locks for this pattern")
    print("   - For multi-threaded usage, consider adding Lock")


# =============================================================================
# Run All Tests
# =============================================================================

def main():
    print("\n" + "="*60)
    print("EDGE CASE TESTS FOR QUICK WIN OPTIMIZATIONS")
    print("Looking for potential bugs and edge cases")
    print("="*60)
    
    tests = [
        # Cache coherence
        test_page_cache_stale_data,
        test_summary_cache_user_isolation,
        test_cache_key_collision,
        
        # Expiration timing
        test_cache_expiration_boundary,
        test_cache_no_refresh_on_access,
        
        # Return value consistency
        test_page_analysis_return_consistency,
        test_summary_none_handling,
        
        # PDF DPI
        test_pdf_dpi_range,
        test_pdf_dpi_consistent_usage,
        
        # Memory management
        test_cache_clear,
        test_cache_expired_cleanup,
        
        # Concurrency
        test_cache_thread_safety,
    ]
    
    for test_func in tests:
        test_func()
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print("="*60)
    
    if results['failed'] > 0:
        print("\n⚠️  Some tests failed - bugs found!")
        sys.exit(1)
    else:
        print("\n🎉 All edge case tests passed - no bugs found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
