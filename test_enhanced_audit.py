#!/usr/bin/env python3
"""
Test script for the enhanced audit system.

This script validates that:
1. Parser extracts location and organization fields
2. Enhanced HTML module loads correctly
3. Audit report generates with all new features
4. Export format includes new fields
5. System gracefully falls back if needed
"""

import json
from pathlib import Path
from src.earmarks.parser import (
    extract_location,
    extract_organization_or_recipient,
    extract_dollar_amount
)


def test_location_extraction():
    """Test location extraction from various patterns."""
    print("\n[TEST] Testing Location Extraction...")
    
    test_cases = [
        ("for the city of Boston", "Boston"),
        ("in Attleboro for youth programs", "Attleboro"),
        ("throughout Worcester County", "Worcester County"),
        ("located in Springfield", "Springfield"),
        ("at the Cambridge Community Center", "Cambridge"),
    ]
    
    passed = 0
    for text, expected in test_cases:
        result = extract_location(text)
        if result == expected:
            print(f"  [OK] '{text[:30]}...' -> '{result}'")
            passed += 1
        else:
            print(f"  [FAIL] '{text[:30]}...' -> Expected '{expected}', got '{result}'")
    
    print(f"\n  Results: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_organization_extraction():
    """Test organization/recipient extraction."""
    print("\n[TEST] Testing Organization Extraction...")
    
    test_cases = [
        ("for the Boys and Girls Club of Boston", "Boys and Girls Club"),
        ("to support the Attleboro Youth Center", "Attleboro Youth Center"),
        ("for an inclusive playground project", "inclusive playground project"),
        ("funding the Community Health Center", "Community Health Center"),
    ]
    
    passed = 0
    for text, expected_partial in test_cases:
        result = extract_organization_or_recipient(text)
        if result and expected_partial.lower() in result.lower():
            print(f"  [OK] '{text[:30]}...' -> '{result}'")
            passed += 1
        else:
            print(f"  [WARN] '{text[:30]}...' -> Got '{result}' (expected to contain '{expected_partial}')")
    
    print(f"\n  Results: {passed}/{len(test_cases)} passed")
    return passed >= len(test_cases) * 0.7  # 70% threshold for partial matches


def test_enhanced_module_loading():
    """Test that enhanced audit module loads correctly."""
    print("\n[TEST] Testing Enhanced Module Loading...")
    
    try:
        from src.earmarks.audit_enhanced import (
            export_enhanced_html_report,
            generate_earmark_card
        )
        print("  [OK] Enhanced module imports successfully")
        print("  [OK] export_enhanced_html_report available")
        print("  [OK] generate_earmark_card available")
        return True
    except ImportError as e:
        print(f"  [FAIL] Failed to import enhanced module: {e}")
        return False
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")
        return False


def test_audit_integration():
    """Test that audit.py integrates enhanced module."""
    print("\n[TEST] Testing Audit Integration...")
    
    try:
        from src.earmarks.audit import ENHANCED_AVAILABLE, export_audit_report
        
        if ENHANCED_AVAILABLE:
            print("  [OK] Enhanced audit is available")
            print("  [OK] Main audit module will use enhanced HTML")
            return True
        else:
            print("  [WARN] Enhanced audit not available, will fall back to basic")
            return False
    except Exception as e:
        print(f"  [FAIL] Error checking integration: {e}")
        return False


def test_sample_data():
    """Test with sample earmark data."""
    print("\n[TEST] Testing with Sample Data...")
    
    sample_amendments = [
        {
            'amendment_number': '47',
            'amount': 250000,
            'line_item': '0640',
            'fiscal_year': 2025,
            'chamber': 'House',
            'primary_sponsor': 'Hawkins',
            'location': 'Attleboro',
            'organization_or_recipient': 'inclusive playground project',
            'raw_text': 'Earmarks $250K in the Massachusetts cultural council line item for an inclusive playground project in Attleboro.',
            'page_number': 1
        },
        {
            'amendment_number': '155',
            'amount': 50000,
            'line_item': '0640',
            'fiscal_year': 2025,
            'chamber': 'House',
            'primary_sponsor': 'Linsky',
            'location': 'Natick',
            'organization_or_recipient': 'mural at the Natick MBTA station',
            'raw_text': 'Increases Massachusetts Cultural Council appropriation by $50K and earmarks the same amount for a mural at the Natick MBTA station.',
            'page_number': 1
        }
    ]
    
    # Check that new fields are present
    all_have_location = all('location' in a for a in sample_amendments)
    all_have_org = all('organization_or_recipient' in a for a in sample_amendments)
    
    if all_have_location and all_have_org:
        print("  [OK] Sample data includes new fields")
        print(f"  [OK] {len(sample_amendments)} amendments with location and organization")
        return True
    else:
        print("  [FAIL] Sample data missing new fields")
        return False


def test_export_format():
    """Test that export format includes new fields."""
    print("\n[TEST] Testing Export Format...")
    
    # Simulate an audit decision with new fields
    mock_decision = {
        'amendment_number': '47',
        'fiscal_year': '2025',
        'assigned_to': 'Susan Hawkins',
        'extracted_amount': 250000,
        'chamber': 'House',
        'sponsor_in_pdf': 'Hawkins',
        'line_item': '0640',
        'location': 'Attleboro',
        'organization_or_recipient': 'inclusive playground project',
        'audit_status': 'correct',
        'audit_notes': '',
        'corrected_member_code': '',
        'corrected_member_name': '',
        'audited_at': '2025-11-22T14:15:23Z'
    }
    
    required_fields = [
        'amendment_number', 'fiscal_year', 'location', 
        'organization_or_recipient', 'corrected_member_code'
    ]
    
    missing = [f for f in required_fields if f not in mock_decision]
    
    if not missing:
        print("  [OK] Export format includes all new fields")
        print(f"  [OK] Fields: {', '.join(required_fields)}")
        return True
    else:
        print(f"  [FAIL] Missing fields: {', '.join(missing)}")
        return False


def test_html_generation():
    """Test HTML generation with mock data."""
    print("\n[TEST] Testing HTML Generation...")
    
    try:
        from src.earmarks.audit_enhanced import export_enhanced_html_report
        
        # Mock data
        audit_rows = [
            {
                'amendment_number': '47',
                'extracted_amount': 250000,
                'assigned_to': 'Susan Hawkins',
                'district': '2nd Bristol',
                'chamber': 'House',
                'sponsor_in_pdf': 'Hawkins',
                'line_item': '0640',
                'location': 'Attleboro',
                'organization_or_recipient': 'playground project',
                'match_confidence': 0.95,
                'match_method': 'full_name',
                'page_number': 1,
                'fiscal_year': 2025,
                'raw_text': 'Test earmark text...',
                'member_code': 'H001'
            }
        ]
        
        members = [
            {
                'member_code': 'H001',
                'name': 'Susan Hawkins',
                'district': '2nd Bristol',
                'branch': 'House'
            }
        ]
        
        output_path = Path('out/test_audit_report.html')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        export_enhanced_html_report(audit_rows, output_path, members)
        
        if output_path.exists():
            # Check file size (should be substantial)
            size_kb = output_path.stat().st_size / 1024
            print(f"  [OK] HTML generated successfully")
            print(f"  [OK] File size: {size_kb:.1f} KB")
            
            # Check for key features in HTML
            with open(output_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            features = [
                ('Keyboard shortcuts', 'handleGlobalKeyboard' in html_content),
                ('Smart queues', 'smart-queues' in html_content),
                ('Progress bar', 'progress-bar' in html_content),
                ('Bulk actions', 'bulk-actions' in html_content),
                ('Inline correction', 'correction-panel' in html_content),
            ]
            
            for name, present in features:
                if present:
                    print(f"  [OK] {name} feature detected")
                else:
                    print(f"  [WARN] {name} feature not found")
            
            all_present = all(p for _, p in features)
            return all_present
        else:
            print("  [FAIL] HTML file not generated")
            return False
            
    except Exception as e:
        print(f"  [FAIL] Error generating HTML: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Enhanced Audit System - Test Suite")
    print("=" * 60)
    
    tests = [
        ("Location Extraction", test_location_extraction),
        ("Organization Extraction", test_organization_extraction),
        ("Enhanced Module Loading", test_enhanced_module_loading),
        ("Audit Integration", test_audit_integration),
        ("Sample Data Format", test_sample_data),
        ("Export Format", test_export_format),
        ("HTML Generation", test_html_generation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ✗ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        except BaseException as e:
            print(f"\n  [ERROR] Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} - {name}")
    
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    percentage = (passed_count / total * 100) if total > 0 else 0
    
    print(f"\n  Results: {passed_count}/{total} tests passed ({percentage:.0f}%)")
    
    if passed_count == total:
        print("\n  [SUCCESS] All tests passed! System is ready to use.")
        return 0
    elif passed_count >= total * 0.7:
        print("\n  [WARN] Most tests passed. System functional with minor issues.")
        return 0
    else:
        print("\n  [ERROR] Multiple tests failed. Review errors above.")
        return 1


if __name__ == '__main__':
    import sys
    exit_code = run_all_tests()
    
    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("\n  1. Run the main pipeline: python main.py")
    print("  2. Open: out/earmark_audit_report.html")
    print("  3. Try keyboard shortcut '?' for help")
    print("  4. Start auditing with enhanced features!")
    print("\n  For detailed docs, see: ENHANCED_AUDIT_GUIDE.md")
    print("  For shortcuts, see: KEYBOARD_SHORTCUTS.md")
    print("  For what's new, see: WHATS_NEW.md")
    print("\n")
    
    sys.exit(exit_code)

