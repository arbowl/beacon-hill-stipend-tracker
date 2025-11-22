"""
Earmark audit report generation module.

This module creates human-readable audit reports showing:
1. Raw PDF text for each earmark
2. What amount was extracted
3. Who it was assigned to
4. Space for manual verification

Outputs both CSV (for spreadsheet review) and HTML (for easier reading).

Enhanced version includes:
- Keyboard shortcuts for rapid navigation
- Bulk actions and smart queues
- Progress tracking and session management
- Inline corrections with member search
- Mobile-responsive design
- Optimized for 1,000+ entries
"""

from pathlib import Path
from typing import Any
import csv
import html

# Import enhanced HTML generator
try:
    from src.earmarks.audit_enhanced import export_enhanced_html_report
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False


def export_audit_report(
    earmarks_by_member: dict[str, list[dict[str, Any]]],
    members: list[dict[str, Any]],
    output_dir: Path = Path("out")
) -> tuple[Path, Path]:
    """
    Export human-readable audit report showing raw text and assignments.
    
    Creates both:
    - CSV for spreadsheet review
    - HTML for easier reading with highlighting
    
    Args:
        earmarks_by_member: Dictionary mapping member codes to their earmarks
        members: List of member dictionaries from API
        output_dir: Directory to write output files (default: out/)
    
    Returns:
        Tuple of (csv_path, html_path)
    """
    # Build member lookup
    member_lookup = {
        m.get('member_code'): m 
        for m in members 
        if m.get('member_code')
    }
    
    # Flatten earmarks_by_member into audit rows
    audit_rows = []
    
    for member_code, member_earmarks in earmarks_by_member.items():
        # Skip special categories like UNKNOWN/UNMATCHED for now
        # (we'll add them at the end)
        if member_code in ('UNKNOWN', 'UNMATCHED'):
            continue
            
        member = member_lookup.get(member_code, {})
        
        for earmark in member_earmarks:
            # Get mapping metadata if available
            mapping_meta = earmark.get('mapping_metadata', {})
            
            audit_rows.append({
                'amendment_number': earmark.get('amendment_number', ''),
                'raw_text': earmark.get('raw_text', '')[:800],  # First 800 chars
                'extracted_amount': earmark.get('amount', 0),
                'assigned_to': member.get('name', 'Unknown'),
                'member_code': member_code,
                'district': member.get('district', ''),
                'chamber': earmark.get('chamber', member.get('branch', '')),
                'sponsor_in_pdf': earmark.get('primary_sponsor', 
                                             mapping_meta.get('sponsor_name', '')),
                'match_confidence': mapping_meta.get('confidence', ''),
                'match_method': mapping_meta.get('match_method', ''),
                'page_number': earmark.get('page_number', ''),
                'line_item': earmark.get('line_item', ''),
                'my_verification': ''  # Empty for user to fill
            })
    
    # Add unmatched earmarks at the end
    for special_key in ('UNKNOWN', 'UNMATCHED'):
        if special_key in earmarks_by_member:
            for earmark in earmarks_by_member[special_key]:
                audit_rows.append({
                    'amendment_number': earmark.get('amendment_number', ''),
                    'raw_text': earmark.get('raw_text', '')[:800],
                    'extracted_amount': earmark.get('amount', 0),
                    'assigned_to': f'*** {special_key} ***',
                    'member_code': special_key,
                    'district': '',
                    'chamber': earmark.get('chamber', ''),
                    'sponsor_in_pdf': earmark.get('primary_sponsor', ''),
                    'match_confidence': '',
                    'match_method': earmark.get('mapping_status', ''),
                    'page_number': earmark.get('page_number', ''),
                    'line_item': earmark.get('line_item', ''),
                    'my_verification': ''
                })
    
    # Sort by amount (biggest first - audit high stakes items)
    audit_rows.sort(key=lambda x: x['extracted_amount'] or 0, reverse=True)
    
    # Export CSV
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / 'earmark_audit_report.csv'
    html_path = output_dir / 'earmark_audit_report.html'
    
    _export_csv_report(audit_rows, csv_path)
    
    # Use enhanced HTML if available, otherwise fall back to basic
    if ENHANCED_AVAILABLE:
        try:
            export_enhanced_html_report(audit_rows, html_path, members)
        except Exception as e:
            print(f"  Warning: Enhanced HTML failed ({e}), using basic HTML")
            _export_html_report(audit_rows, html_path)
    else:
        _export_html_report(audit_rows, html_path)
    
    return csv_path, html_path


def _export_csv_report(audit_rows: list[dict[str, Any]], output_path: Path) -> None:
    """Export audit report as CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'amendment_number',
            'extracted_amount',
            'assigned_to',
            'district',
            'chamber',
            'sponsor_in_pdf',
            'match_confidence',
            'match_method',
            'line_item',
            'page_number',
            'raw_text',
            'my_verification'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in audit_rows:
            writer.writerow({
                'amendment_number': row['amendment_number'],
                'extracted_amount': f"${row['extracted_amount']:,.2f}" 
                                   if row['extracted_amount'] else '',
                'assigned_to': row['assigned_to'],
                'district': row['district'],
                'chamber': row['chamber'],
                'sponsor_in_pdf': row['sponsor_in_pdf'],
                'match_confidence': f"{row['match_confidence']:.2f}" 
                                   if row['match_confidence'] else '',
                'match_method': row['match_method'],
                'line_item': row['line_item'],
                'page_number': row['page_number'],
                'raw_text': row['raw_text'],
                'my_verification': row['my_verification']
            })
    
    print(f"  [+] CSV audit report: {output_path}")
    print(f"    Total assignments to audit: {len(audit_rows)}")
    print(f"    Sorted by amount (highest first)")


def _export_html_report(audit_rows: list[dict[str, Any]], output_path: Path) -> None:
    """Export audit report as interactive HTML."""
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earmark Assignment Audit Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                         "Helvetica Neue", Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        
        .header {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            margin: 0 0 10px 0;
            color: #333;
        }}
        
        .stats {{
            color: #666;
            font-size: 14px;
        }}
        
        .filters {{
            background: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .filters input, .filters select {{
            padding: 8px;
            margin-right: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
        
        .earmark-card {{
            background: white;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #4CAF50;
        }}
        
        .earmark-card.unmatched {{
            border-left-color: #ff9800;
        }}
        
        .earmark-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }}
        
        .amendment-num {{
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }}
        
        .amount {{
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }}
        
        .amount.large {{
            color: #f44336;
        }}
        
        .assignment-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
            padding: 10px;
            background: #f9f9f9;
            border-radius: 4px;
        }}
        
        .info-item {{
            font-size: 14px;
        }}
        
        .info-label {{
            font-weight: 600;
            color: #666;
            margin-right: 5px;
        }}
        
        .info-value {{
            color: #333;
        }}
        
        .raw-text {{
            background: #fafafa;
            padding: 15px;
            border-radius: 4px;
            border-left: 3px solid #2196F3;
            margin-bottom: 15px;
            font-family: "Courier New", monospace;
            font-size: 13px;
            line-height: 1.6;
            white-space: pre-wrap;
            overflow-wrap: break-word;
        }}
        
        .raw-text .highlight {{
            background: #ffeb3b;
            padding: 2px 4px;
            border-radius: 2px;
            font-weight: bold;
        }}
        
        .verification {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        
        .verification button {{
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        }}
        
        .btn-correct {{
            background: #4CAF50;
            color: white;
        }}
        
        .btn-wrong {{
            background: #f44336;
            color: white;
        }}
        
        .btn-unsure {{
            background: #ff9800;
            color: white;
        }}
        
        .verification input[type="text"] {{
            flex: 1;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
        
        .verified {{
            opacity: 0.6;
        }}
        
        .metadata {{
            font-size: 12px;
            color: #999;
            margin-top: 10px;
        }}
        
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .badge-house {{
            background: #e3f2fd;
            color: #1976d2;
        }}
        
        .badge-senate {{
            background: #f3e5f5;
            color: #7b1fa2;
        }}
        
        .badge-low {{
            background: #ffebee;
            color: #c62828;
        }}
        
        .badge-high {{
            background: #e8f5e9;
            color: #2e7d32;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Earmark Assignment Audit Report</h1>
        <div class="stats">
            <strong>{len(audit_rows)}</strong> assignments to review
            · Sorted by amount (highest first)
        </div>
    </div>
    
    <div class="filters">
        <input type="text" id="searchBox" placeholder="Search by name, district, or text..." 
               onkeyup="filterCards()">
        <select id="chamberFilter" onchange="filterCards()">
            <option value="">All Chambers</option>
            <option value="House">House</option>
            <option value="Senate">Senate</option>
        </select>
        <select id="statusFilter" onchange="filterCards()">
            <option value="">All Statuses</option>
            <option value="unverified">Not Yet Verified</option>
            <option value="correct">Marked Correct</option>
            <option value="wrong">Marked Wrong</option>
        </select>
        <button onclick="exportAuditDecisions()" style="padding: 8px 16px; background: #2196F3; 
                color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500;">
            📥 Export My Audit Decisions
        </button>
        <span id="exportStatus" style="margin-left: 10px; color: #4CAF50; font-weight: 500;"></span>
    </div>
    
    <div id="earmarkContainer">
"""
    
    # Generate cards for each earmark
    for idx, row in enumerate(audit_rows):
        amount = row['extracted_amount'] or 0
        amount_class = 'large' if amount > 100000 else ''
        card_class = 'unmatched' if row['member_code'] in ('UNKNOWN', 'UNMATCHED') else ''
        
        # Try to highlight the amount in the raw text
        raw_text = html.escape(row['raw_text'])
        if amount:
            # Try to find and highlight the amount
            amount_patterns = [
                f"${amount:,.0f}",
                f"${amount/1000:.0f}K",
                f"${amount/1000000:.1f}M"
            ]
            for pattern in amount_patterns:
                if pattern in raw_text:
                    raw_text = raw_text.replace(
                        pattern, 
                        f'<span class="highlight">{pattern}</span>'
                    )
                    break
        
        confidence_badge = ''
        if row['match_confidence']:
            conf_val = float(row['match_confidence'])
            badge_class = 'badge-high' if conf_val >= 0.8 else 'badge-low'
            confidence_badge = f'<span class="badge {badge_class}">Match: {conf_val:.0%}</span>'
        
        chamber_badge = ''
        if row['chamber']:
            chamber_class = f"badge-{row['chamber'].lower()}"
            chamber_badge = f'<span class="badge {chamber_class}">{row["chamber"]}</span>'
        
        html_content += f"""
        <div class="earmark-card {card_class}" data-chamber="{row['chamber']}" 
             data-status="unverified" id="card-{idx}">
            <div class="earmark-header">
                <div>
                    <span class="amendment-num">Amendment #{row['amendment_number']}</span>
                    {chamber_badge}
                    {confidence_badge}
                </div>
                <div class="amount {amount_class}">
                    ${amount:,.2f}
                </div>
            </div>
            
            <div class="assignment-info">
                <div class="info-item">
                    <span class="info-label">Assigned To:</span>
                    <span class="info-value">{html.escape(row['assigned_to'])}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">District:</span>
                    <span class="info-value">{html.escape(row['district'])}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Sponsor in PDF:</span>
                    <span class="info-value">{html.escape(row['sponsor_in_pdf'])}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Line Item:</span>
                    <span class="info-value">{html.escape(row['line_item'] if row['line_item'] else '')}</span>
                </div>
            </div>
            
            <div class="raw-text">{raw_text}</div>
            
            <div class="verification">
                <button class="btn-correct" onclick="markStatus({idx}, 'correct')">
                    ✓ Correct
                </button>
                <button class="btn-wrong" onclick="markStatus({idx}, 'wrong')">
                    ✗ Wrong
                </button>
                <button class="btn-unsure" onclick="markStatus({idx}, 'unsure')">
                    ? Unsure
                </button>
                <input type="text" id="notes-{idx}" placeholder="Add notes...">
            </div>
            
            <div class="metadata">
                Page {row['page_number']} · 
                Match method: {row['match_method'] or 'N/A'}
            </div>
        </div>
"""
    
    # Add JavaScript for interactivity
    html_content += """
    </div>
    
    <script>
        function markStatus(cardId, status) {
            const card = document.getElementById(`card-${cardId}`);
            card.setAttribute('data-status', status);
            
            if (status === 'correct') {
                card.style.borderLeftColor = '#4CAF50';
                card.classList.add('verified');
            } else if (status === 'wrong') {
                card.style.borderLeftColor = '#f44336';
                card.classList.remove('verified');
            } else {
                card.style.borderLeftColor = '#ff9800';
                card.classList.remove('verified');
            }
            
            // Store in localStorage for persistence
            const notes = document.getElementById(`notes-${cardId}`).value;
            localStorage.setItem(`audit-${cardId}`, JSON.stringify({
                status: status,
                notes: notes
            }));
        }
        
        function filterCards() {
            const searchText = document.getElementById('searchBox').value.toLowerCase();
            const chamber = document.getElementById('chamberFilter').value;
            const status = document.getElementById('statusFilter').value;
            
            const cards = document.querySelectorAll('.earmark-card');
            
            cards.forEach(card => {
                const text = card.textContent.toLowerCase();
                const cardChamber = card.getAttribute('data-chamber');
                const cardStatus = card.getAttribute('data-status');
                
                const matchesSearch = !searchText || text.includes(searchText);
                const matchesChamber = !chamber || cardChamber === chamber;
                const matchesStatus = !status || cardStatus === status;
                
                if (matchesSearch && matchesChamber && matchesStatus) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
        
        // Restore saved statuses on load
        window.addEventListener('load', () => {
            const cards = document.querySelectorAll('.earmark-card');
            cards.forEach((card, idx) => {
                const saved = localStorage.getItem(`audit-${idx}`);
                if (saved) {
                    const data = JSON.parse(saved);
                    if (data.notes) {
                        document.getElementById(`notes-${idx}`).value = data.notes;
                    }
                    if (data.status) {
                        markStatus(idx, data.status);
                    }
                }
            });
        });
        
        // Export audit decisions to JSON file
        function exportAuditDecisions() {
            const cards = document.querySelectorAll('.earmark-card');
            const decisions = [];
            let verifiedCount = 0;
            
            cards.forEach((card, idx) => {
                const saved = localStorage.getItem(`audit-${idx}`);
                const amendmentNum = card.querySelector('.amendment-num').textContent.replace('Amendment #', '');
                const assignedTo = card.querySelector('.info-value').textContent;
                const amount = card.querySelector('.amount').textContent.replace(/[$,]/g, '');
                const chamber = card.getAttribute('data-chamber');
                const sponsorInPdf = card.querySelectorAll('.info-value')[2].textContent;
                
                let status = 'unverified';
                let notes = '';
                
                if (saved) {
                    const data = JSON.parse(saved);
                    status = data.status || 'unverified';
                    notes = data.notes || '';
                    if (status !== 'unverified') verifiedCount++;
                }
                
                decisions.push({
                    amendment_number: amendmentNum,
                    assigned_to: assignedTo,
                    extracted_amount: parseFloat(amount),
                    chamber: chamber,
                    sponsor_in_pdf: sponsorInPdf,
                    audit_status: status,
                    audit_notes: notes,
                    audited_at: new Date().toISOString()
                });
            });
            
            // Create export object with metadata
            const exportData = {
                audit_metadata: {
                    total_items: decisions.length,
                    verified_count: verifiedCount,
                    correct_count: decisions.filter(d => d.audit_status === 'correct').length,
                    wrong_count: decisions.filter(d => d.audit_status === 'wrong').length,
                    unsure_count: decisions.filter(d => d.audit_status === 'unsure').length,
                    exported_at: new Date().toISOString()
                },
                decisions: decisions
            };
            
            // Download as JSON file
            const dataStr = JSON.stringify(exportData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `earmark_audit_decisions_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            // Show success message
            const statusEl = document.getElementById('exportStatus');
            statusEl.textContent = `✓ Exported ${verifiedCount} verified items`;
            setTimeout(() => {
                statusEl.textContent = '';
            }, 3000);
        }
    </script>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  [+] HTML audit report: {output_path}")
    print(f"    Open in browser for interactive review")


def print_audit_summary(
    earmarks_by_member: dict[str, list[dict[str, Any]]]
) -> None:
    """Print summary statistics for the audit."""
    total_earmarks = sum(len(earmarks) for earmarks in earmarks_by_member.values())
    total_members = len([k for k in earmarks_by_member.keys() 
                        if k not in ('UNKNOWN', 'UNMATCHED')])
    
    unmatched = len(earmarks_by_member.get('UNKNOWN', [])) + \
                len(earmarks_by_member.get('UNMATCHED', []))
    
    print("\n[Earmark Audit Summary]")
    print(f"  Total earmarks: {total_earmarks}")
    print(f"  Assigned to members: {total_members}")
    print(f"  Unmatched: {unmatched}")
    print(f"  Match rate: {((total_earmarks-unmatched)/total_earmarks*100):.1f}%")

