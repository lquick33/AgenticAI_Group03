"""
Protocol Compliance Verification Script.

Uses @runtime_checkable isinstance() checks plus manual method-signature
inspection to surface structural mismatches between Protocol interfaces
and their concrete adapter implementations.
"""

import inspect
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.protocols.repositories import (
    PageAnalysisReader,
    PageAnalysisWriter,
    PageAnalysisSearcher,
    CourseRepository,
    MaterialRepository,
    MessageRepository,
    FlashcardRepository,
    FileStorageRepository,
    KnowledgeTrackingRepository,
)
from app.adapters.supabase.client import get_supabase_client
from app.adapters.supabase import (
    SupabaseFileStorageAdapter,
    SupabaseCourseAdapter,
    SupabaseMaterialAdapter,
    SupabasePageAnalysisAdapter,
    SupabaseMessageAdapter,
    SupabaseFlashcardAdapter,
    SupabaseKnowledgeAdapter,
)


def check_isinstance(adapter_cls, protocol_cls, client):
    """Check if an adapter instance passes isinstance() for a protocol."""
    instance = adapter_cls(client)
    passes = isinstance(instance, protocol_cls)
    return passes


def compare_signatures(adapter_cls, protocol_cls):
    """Compare method signatures between adapter and protocol."""
    mismatches = []

    # Get protocol methods (exclude dunder and private)
    protocol_methods = {
        name: method
        for name, method in inspect.getmembers(protocol_cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    for method_name, proto_method in protocol_methods.items():
        proto_sig = inspect.signature(proto_method)
        proto_params = list(proto_sig.parameters.keys())

        # Check if adapter has this method
        adapter_method = getattr(adapter_cls, method_name, None)
        if adapter_method is None:
            mismatches.append({
                "method": method_name,
                "issue": "MISSING",
                "protocol_params": proto_params,
                "adapter_params": None,
            })
            continue

        adapter_sig = inspect.signature(adapter_method)
        adapter_params = list(adapter_sig.parameters.keys())

        # Compare parameter lists
        if proto_params != adapter_params:
            mismatches.append({
                "method": method_name,
                "issue": "PARAM_MISMATCH",
                "protocol_params": proto_params,
                "adapter_params": adapter_params,
            })

    return mismatches


def main():
    client = get_supabase_client()

    checks = [
        ("SupabasePageAnalysisAdapter", SupabasePageAnalysisAdapter, PageAnalysisReader,  "PageAnalysisReader"),
        ("SupabasePageAnalysisAdapter", SupabasePageAnalysisAdapter, PageAnalysisWriter,  "PageAnalysisWriter"),
        ("SupabasePageAnalysisAdapter", SupabasePageAnalysisAdapter, PageAnalysisSearcher, "PageAnalysisSearcher"),
        ("SupabaseCourseAdapter",       SupabaseCourseAdapter,       CourseRepository,      "CourseRepository"),
        ("SupabaseMaterialAdapter",     SupabaseMaterialAdapter,     MaterialRepository,    "MaterialRepository"),
        ("SupabaseMessageAdapter",      SupabaseMessageAdapter,      MessageRepository,     "MessageRepository"),
        ("SupabaseFlashcardAdapter",    SupabaseFlashcardAdapter,    FlashcardRepository,   "FlashcardRepository"),
        ("SupabaseFileStorageAdapter",  SupabaseFileStorageAdapter,  FileStorageRepository, "FileStorageRepository"),
        ("SupabaseKnowledgeAdapter",    SupabaseKnowledgeAdapter,    KnowledgeTrackingRepository, "KnowledgeTrackingRepository"),
    ]

    print("=" * 70)
    print("Protocol Compliance Report")
    print("=" * 70)

    total_pass = 0
    total_fail = 0

    for adapter_name, adapter_cls, protocol_cls, protocol_name in checks:
        print(f"\n--- {adapter_name} vs {protocol_name} ---")

        # 1. isinstance check
        passes = check_isinstance(adapter_cls, protocol_cls, client)
        status = "PASS" if passes else "FAIL"
        print(f"  isinstance check: {status}")

        if passes:
            total_pass += 1
        else:
            total_fail += 1

        # 2. Detailed signature comparison
        mismatches = compare_signatures(adapter_cls, protocol_cls)
        if mismatches:
            for m in mismatches:
                if m["issue"] == "MISSING":
                    print(f"  [MISSING] {m['method']}(): not found in adapter")
                    print(f"     Protocol expects params: {m['protocol_params']}")
                else:
                    print(f"  [MISMATCH] {m['method']}(): parameter mismatch")
                    print(f"     Protocol: {m['protocol_params']}")
                    print(f"     Adapter:  {m['adapter_params']}")
        else:
            print("  [OK] All method signatures match")

    print(f"\n{'=' * 70}")
    print(f"Summary: {total_pass} PASS / {total_fail} FAIL")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
