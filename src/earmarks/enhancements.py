"""
Enhanced earmark audit report generation module with advanced UI/UX.

This module extends the basic audit functionality with:
1. Keyboard shortcuts for rapid review
2. Bulk actions and batch processing
3. Smart queues and advanced filtering  
4. Progress tracking and session management
5. Inline correction interface
6. Enhanced confidence visualization
7. Mobile-responsive design

Designed to handle 1,000+ entries efficiently.
"""

from pathlib import Path
from typing import Any
import html
import json


def export_enhanced_html_report(
    audit_rows: list[dict[str, Any]], 
    output_path: Path,
    members: list[dict[str, Any]]
) -> None:
    """
    Export enhanced interactive HTML audit report with advanced features.
    
    Args:
        audit_rows: List of earmark audit data
        output_path: Path to write HTML file
        members: List of member dictionaries for autocomplete
    """
    
    # Calculate statistics for smart queues
    high_priority = sum(1 for r in audit_rows 
                       if (r.get('match_confidence') or 0) < 0.7 
                       and (r.get('extracted_amount') or 0) > 100000)
    
    quick_wins = sum(1 for r in audit_rows 
                    if (r.get('match_confidence') or 0) >= 0.9)
    
    needs_attention = sum(1 for r in audit_rows 
                         if r.get('member_code') in ('UNKNOWN', 'UNMATCHED')
                         or (r.get('match_confidence') or 0) < 0.7)
    
    # Build member list for autocomplete (JSON)
    member_list_json = json.dumps([
        {
            'code': m.get('member_code'),
            'name': m.get('name'),
            'district': m.get('district'),
            'chamber': m.get('branch')
        }
        for m in members if m.get('member_code')
    ])
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Earmark Audit Report</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                         "Helvetica Neue", Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
            line-height: 1.5;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        /* Header Section */
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 32px;
            font-weight: 700;
        }}
        
        .header-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .stat-box {{
            background: rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            display: block;
        }}
        
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
            display: block;
            margin-top: 5px;
        }}
        
        /* Progress Bar */
        .progress-section {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .progress-bar-container {{
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
            margin: 15px 0;
        }}
        
        .progress-bar {{
            height: 100%;
            display: flex;
            transition: all 0.3s ease;
        }}
        
        .progress-segment {{
            height: 100%;
            transition: width 0.3s ease;
        }}
        
        .progress-correct {{
            background: #4CAF50;
        }}
        
        .progress-wrong {{
            background: #f44336;
        }}
        
        .progress-unsure {{
            background: #ff9800;
        }}
        
        .progress-unreviewed {{
            background: #e0e0e0;
        }}
        
        .progress-stats {{
            display: flex;
            justify-content: space-between;
            font-size: 14px;
            color: #666;
            margin-top: 10px;
        }}
        
        .progress-actions {{
            margin-top: 15px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        
        /* Smart Queues */
        .smart-queues {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .queue-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .queue-button {{
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            text-align: center;
            transition: all 0.2s ease;
            font-size: 14px;
        }}
        
        .queue-button:hover {{
            border-color: #667eea;
            background: #f0f4ff;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        
        .queue-button.active {{
            border-color: #667eea;
            background: #667eea;
            color: white;
        }}
        
        .queue-icon {{
            font-size: 24px;
            display: block;
            margin-bottom: 5px;
        }}
        
        .queue-label {{
            font-weight: 600;
            display: block;
            margin-bottom: 3px;
        }}
        
        .queue-count {{
            font-size: 12px;
            color: #666;
        }}
        
        .queue-button.active .queue-count {{
            color: rgba(255,255,255,0.9);
        }}
        
        /* Filters */
        .filters {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .filter-row {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .filters input, .filters select {{
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            flex: 1;
            min-width: 200px;
        }}
        
        .filters input:focus, .filters select:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        /* Bulk Actions Toolbar */
        .bulk-actions {{
            background: white;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: none;
        }}
        
        .bulk-actions.active {{
            display: block;
        }}
        
        .bulk-actions-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        /* Earmark Cards */
        .earmark-card {{
            background: white;
            padding: 25px;
            margin-bottom: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 5px solid #4CAF50;
            position: relative;
            transition: all 0.2s ease;
        }}
        
        .earmark-card:hover {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transform: translateY(-2px);
        }}
        
        .earmark-card.selected {{
            border-left-color: #667eea;
            background: #f0f4ff;
        }}
        
        .earmark-card.current {{
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.3);
        }}
        
        .earmark-card.status-correct {{
            border-left-color: #4CAF50;
            opacity: 0.7;
        }}
        
        .earmark-card.status-wrong {{
            border-left-color: #f44336;
        }}
        
        .earmark-card.status-unsure {{
            border-left-color: #ff9800;
        }}
        
        .earmark-card.unmatched {{
            border-left-color: #ff5722;
        }}
        
        .earmark-card.low-confidence {{
            border-left-color: #ff9800;
        }}
        
        .card-checkbox {{
            position: absolute;
            top: 25px;
            right: 25px;
            width: 24px;
            height: 24px;
            cursor: pointer;
        }}
        
        .earmark-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #eee;
        }}
        
        .header-left {{
            flex: 1;
        }}
        
        .amendment-num {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }}
        
        .badges {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
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
        
        .badge-confidence {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        
        .badge-high {{
            background: #e8f5e9;
            color: #2e7d32;
        }}
        
        .badge-medium {{
            background: #fff3e0;
            color: #ef6c00;
        }}
        
        .badge-low {{
            background: #ffebee;
            color: #c62828;
        }}
        
        .amount {{
            font-size: 32px;
            font-weight: bold;
            color: #2196F3;
            text-align: right;
        }}
        
        .amount.large {{
            color: #f44336;
        }}
        
        .amount.medium {{
            color: #ff9800;
        }}
        
        /* Info Grid */
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 8px;
        }}
        
        .info-item {{
            font-size: 14px;
        }}
        
        .info-label {{
            font-weight: 600;
            color: #666;
            display: block;
            margin-bottom: 3px;
        }}
        
        .info-value {{
            color: #333;
            display: block;
        }}
        
        .info-value.empty {{
            color: #999;
            font-style: italic;
        }}
        
        /* Comparison View */
        .comparison-view {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .comparison-panel {{
            padding: 15px;
            border-radius: 8px;
            border: 2px solid #ddd;
        }}
        
        .comparison-pdf {{
            background: #fff8e1;
            border-color: #ffc107;
        }}
        
        .comparison-system {{
            background: #e3f2fd;
            border-color: #2196f3;
        }}
        
        .panel-title {{
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
            color: #666;
        }}
        
        .panel-item {{
            margin-bottom: 8px;
            font-size: 13px;
        }}
        
        .panel-label {{
            font-weight: 600;
            color: #555;
        }}
        
        .match-indicator {{
            display: inline-block;
            margin-left: 5px;
            font-size: 16px;
        }}
        
        /* Raw Text */
        .raw-text {{
            background: #fafafa;
            padding: 15px;
            border-radius: 8px;
            border-left: 3px solid #2196F3;
            margin-bottom: 20px;
            font-family: "Courier New", monospace;
            font-size: 13px;
            line-height: 1.8;
            white-space: pre-wrap;
            overflow-wrap: break-word;
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .raw-text .highlight {{
            background: #ffeb3b;
            padding: 2px 4px;
            border-radius: 2px;
            font-weight: bold;
        }}
        
        .raw-text .highlight-org {{
            background: #b2dfdb;
            padding: 2px 4px;
            border-radius: 2px;
            font-weight: bold;
        }}
        
        .raw-text .highlight-location {{
            background: #f8bbd0;
            padding: 2px 4px;
            border-radius: 2px;
            font-weight: bold;
        }}
        
        .expand-text {{
            color: #667eea;
            cursor: pointer;
            text-decoration: underline;
            font-size: 12px;
            margin-top: 5px;
            display: inline-block;
        }}
        
        /* Verification Actions */
        .verification {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }}
        
        .verification button {{
            padding: 12px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        
        .verification button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        
        .btn-correct {{
            background: #4CAF50;
            color: white;
        }}
        
        .btn-correct:hover {{
            background: #45a049;
        }}
        
        .btn-wrong {{
            background: #f44336;
            color: white;
        }}
        
        .btn-wrong:hover {{
            background: #da190b;
        }}
        
        .btn-unsure {{
            background: #ff9800;
            color: white;
        }}
        
        .btn-unsure:hover {{
            background: #fb8c00;
        }}
        
        .btn-skip {{
            background: #9e9e9e;
            color: white;
        }}
        
        .btn-skip:hover {{
            background: #757575;
        }}
        
        .verification input[type="text"] {{
            flex: 1;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            min-width: 200px;
        }}
        
        .verification input[type="text"]:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        /* Inline Correction */
        .correction-panel {{
            display: none;
            padding: 20px;
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 8px;
            margin-top: 15px;
        }}
        
        .correction-panel.active {{
            display: block;
        }}
        
        .correction-search {{
            position: relative;
            margin-bottom: 15px;
        }}
        
        .correction-search input {{
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }}
        
        .correction-results {{
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 2px solid #ddd;
            border-top: none;
            border-radius: 0 0 6px 6px;
            max-height: 300px;
            overflow-y: auto;
            z-index: 100;
            display: none;
        }}
        
        .correction-results.active {{
            display: block;
        }}
        
        .correction-result-item {{
            padding: 12px;
            cursor: pointer;
            border-bottom: 1px solid #eee;
            transition: background 0.1s ease;
        }}
        
        .correction-result-item:hover {{
            background: #f0f4ff;
        }}
        
        .result-name {{
            font-weight: 600;
            color: #333;
        }}
        
        .result-details {{
            font-size: 12px;
            color: #666;
            margin-top: 3px;
        }}
        
        /* Metadata Edit Section */
        .metadata-edit-section {{
            margin-top: 15px;
            margin-bottom: 15px;
        }}
        
        .btn-edit-metadata {{
            padding: 10px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        
        .btn-edit-metadata:hover {{
            background: #5568d3;
            transform: translateY(-1px);
        }}
        
        .metadata-edit-panel {{
            padding: 20px;
            background: #f0f4ff;
            border: 2px solid #667eea;
            border-radius: 8px;
            margin-top: 10px;
        }}
        
        .metadata-edit-panel h4 {{
            margin-top: 0;
            color: #667eea;
        }}
        
        .edit-field {{
            margin-bottom: 15px;
        }}
        
        .edit-field label {{
            display: block;
            font-weight: 600;
            font-size: 13px;
            color: #333;
            margin-bottom: 5px;
        }}
        
        .edit-field input[type="text"],
        .edit-field input[type="number"],
        .edit-field select {{
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
        }}
        
        .edit-field input:focus,
        .edit-field select:focus {{
            outline: none;
            border-color: #667eea;
            background: white;
        }}
        
        .edit-field small {{
            display: block;
            font-size: 11px;
            color: #666;
            margin-top: 3px;
            font-style: italic;
        }}
        
        .edit-field input.modified {{
            border-color: #ff9800;
            background: #fff8e1;
        }}
        
        .edit-actions {{
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }}
        
        .edit-actions button {{
            flex: 1;
        }}
        
        /* Metadata Footer */
        .metadata {{
            font-size: 12px;
            color: #999;
            padding-top: 15px;
            border-top: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
        }}
        
        /* Button Styles */
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #5568d3;
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        
        .btn-secondary {{
            background: #6c757d;
            color: white;
        }}
        
        .btn-secondary:hover {{
            background: #5a6268;
        }}
        
        .btn-outline {{
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }}
        
        .btn-outline:hover {{
            background: #667eea;
            color: white;
        }}
        
        /* Keyboard Shortcuts Help */
        .shortcuts-help {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: white;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            font-size: 24px;
            z-index: 1000;
            transition: all 0.2s ease;
        }}
        
        .shortcuts-help:hover {{
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(0,0,0,0.2);
        }}
        
        .shortcuts-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 2000;
            align-items: center;
            justify-content: center;
        }}
        
        .shortcuts-modal.active {{
            display: flex;
        }}
        
        .shortcuts-content {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
        }}
        
        .shortcuts-grid {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 15px;
            margin-top: 20px;
        }}
        
        .shortcut-key {{
            background: #f5f5f5;
            padding: 8px 12px;
            border-radius: 6px;
            font-family: monospace;
            font-weight: bold;
            text-align: center;
            border: 2px solid #ddd;
        }}
        
        .shortcut-desc {{
            display: flex;
            align-items: center;
        }}
        
        /* Loading States */
        .loading {{
            text-align: center;
            padding: 40px;
            color: #666;
        }}
        
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* Mobile Responsive */
        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}
            
            .comparison-view {{
                grid-template-columns: 1fr;
            }}
            
            .info-grid {{
                grid-template-columns: 1fr;
            }}
            
            .header-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .queue-grid {{
                grid-template-columns: 1fr;
            }}
            
            .filter-row {{
                flex-direction: column;
            }}
            
            .filters input, .filters select {{
                width: 100%;
            }}
            
            .earmark-card {{
                padding: 15px;
            }}
            
            .amount {{
                font-size: 24px;
            }}
            
            .card-checkbox {{
                top: 15px;
                right: 15px;
            }}
        }}
        
        /* Print Styles */
        @media print {{
            .filters, .bulk-actions, .shortcuts-help {{
                display: none !important;
            }}
            
            .earmark-card {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}
        }}
        
        /* Utility Classes */
        .hidden {{
            display: none !important;
        }}
        
        .text-success {{
            color: #4CAF50;
        }}
        
        .text-danger {{
            color: #f44336;
        }}
        
        .text-warning {{
            color: #ff9800;
        }}
        
        .text-muted {{
            color: #666;
        }}
        
        .mb-0 {{ margin-bottom: 0; }}
        .mb-1 {{ margin-bottom: 10px; }}
        .mb-2 {{ margin-bottom: 20px; }}
        .mt-0 {{ margin-top: 0; }}
        .mt-1 {{ margin-top: 10px; }}
        .mt-2 {{ margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🔍 Enhanced Earmark Audit System</h1>
            <p>Designed for efficient review of 1,000+ entries</p>
            <div class="header-stats">
                <div class="stat-box">
                    <span class="stat-number" id="total-count">{len(audit_rows)}</span>
                    <span class="stat-label">Total Items</span>
                </div>
                <div class="stat-box">
                    <span class="stat-number" id="verified-count">0</span>
                    <span class="stat-label">Verified</span>
                </div>
                <div class="stat-box">
                    <span class="stat-number" id="remaining-count">{len(audit_rows)}</span>
                    <span class="stat-label">Remaining</span>
                </div>
                <div class="stat-box">
                    <span class="stat-number" id="accuracy-rate">--</span>
                    <span class="stat-label">Estimated Time</span>
                </div>
            </div>
        </div>
        
        <!-- Progress Tracking -->
        <div class="progress-section">
            <h2 style="margin: 0 0 10px 0;">📊 Your Progress</h2>
            <div class="progress-bar-container">
                <div class="progress-bar" id="progress-bar">
                    <div class="progress-segment progress-correct" style="width: 0%"></div>
                    <div class="progress-segment progress-wrong" style="width: 0%"></div>
                    <div class="progress-segment progress-unsure" style="width: 0%"></div>
                    <div class="progress-segment progress-unreviewed" style="width: 100%"></div>
                </div>
            </div>
            <div class="progress-stats">
                <span>✓ Correct: <strong id="correct-count">0</strong></span>
                <span>✗ Wrong: <strong id="wrong-count">0</strong></span>
                <span>? Unsure: <strong id="unsure-count">0</strong></span>
                <span>— Unreviewed: <strong id="unreviewed-count">{len(audit_rows)}</strong></span>
            </div>
            <div class="progress-actions">
                <button class="btn btn-primary" onclick="resumeAudit()">
                    ▶️ Resume from Last Position
                </button>
                <button class="btn btn-outline" onclick="exportAuditDecisions()">
                    📥 Export Audit Decisions
                </button>
                <span id="export-status" style="color: #4CAF50; font-weight: 600; margin-left: 10px;"></span>
            </div>
        </div>
        
        <!-- Smart Queues -->
        <div class="smart-queues">
            <h2 style="margin: 0 0 10px 0;">🎯 Smart Queues - Focus Your Effort</h2>
            <p style="color: #666; font-size: 14px; margin-bottom: 15px;">
                Click a queue to filter items by priority or type
            </p>
            <div class="queue-grid">
                <div class="queue-button" onclick="applyQueue('all')" data-queue="all">
                    <span class="queue-icon">📋</span>
                    <span class="queue-label">All Items</span>
                    <span class="queue-count">{len(audit_rows)} items</span>
                </div>
                <div class="queue-button" onclick="applyQueue('high-priority')" data-queue="high-priority">
                    <span class="queue-icon">🔥</span>
                    <span class="queue-label">High Priority</span>
                    <span class="queue-count">{high_priority} items - Low conf + High $</span>
                </div>
                <div class="queue-button" onclick="applyQueue('quick-wins')" data-queue="quick-wins">
                    <span class="queue-icon">⚡</span>
                    <span class="queue-label">Quick Wins</span>
                    <span class="queue-count">{quick_wins} items - High confidence</span>
                </div>
                <div class="queue-button" onclick="applyQueue('needs-attention')" data-queue="needs-attention">
                    <span class="queue-icon">⚠️</span>
                    <span class="queue-label">Needs Attention</span>
                    <span class="queue-count">{needs_attention} items - Low conf</span>
                </div>
                <div class="queue-button" onclick="applyQueue('unverified')" data-queue="unverified">
                    <span class="queue-icon">❓</span>
                    <span class="queue-label">Not Yet Reviewed</span>
                    <span class="queue-count">Updated live</span>
                </div>
                <div class="queue-button" onclick="applyQueue('flagged')" data-queue="flagged">
                    <span class="queue-icon">🚩</span>
                    <span class="queue-label">Flagged as Wrong</span>
                    <span class="queue-count">Updated live</span>
                </div>
            </div>
        </div>
        
        <!-- Advanced Filters -->
        <div class="filters">
            <h3 style="margin: 0 0 15px 0;">🔍 Advanced Filters</h3>
            <div class="filter-row">
                <input type="text" id="searchBox" placeholder="🔎 Search by name, district, text, org, location..." 
                       onkeyup="filterCards()" style="flex: 2;">
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
                    <option value="unsure">Marked Unsure</option>
                </select>
                <select id="confidenceFilter" onchange="filterCards()">
                    <option value="">All Confidence</option>
                    <option value="high">High (&gt;0.9)</option>
                    <option value="medium">Medium (0.7-0.9)</option>
                    <option value="low">Low (&lt;0.7)</option>
                </select>
                <select id="amountFilter" onchange="filterCards()">
                    <option value="">All Amounts</option>
                    <option value="mega">&gt;$1M</option>
                    <option value="large">$100K-$1M</option>
                    <option value="medium">$10K-$100K</option>
                    <option value="small">&lt;$10K</option>
                </select>
                <button class="btn btn-secondary" onclick="clearFilters()">Clear Filters</button>
            </div>
            <div style="margin-top: 10px; color: #666; font-size: 13px;">
                <strong id="visible-count">{len(audit_rows)}</strong> items visible
                <span id="selected-info" class="hidden"> • <strong id="selected-count">0</strong> selected</span>
            </div>
        </div>
        
        <!-- Bulk Actions Toolbar -->
        <div class="bulk-actions" id="bulk-actions">
            <div class="bulk-actions-content">
                <div>
                    <strong id="bulk-selected-count">0</strong> items selected
                </div>
                <div style="display: flex; gap: 10px;">
                    <button class="btn btn-correct" onclick="bulkMarkStatus('correct')">
                        ✓ Mark All Correct
                    </button>
                    <button class="btn btn-wrong" onclick="bulkMarkStatus('wrong')">
                        ✗ Mark All Wrong
                    </button>
                    <button class="btn btn-unsure" onclick="bulkMarkStatus('unsure')">
                        ? Mark All Unsure
                    </button>
                    <button class="btn btn-secondary" onclick="deselectAll()">
                        Clear Selection
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Earmark Cards Container -->
        <div id="earmarkContainer">
"""
    
    # Generate individual earmark cards
    for idx, row in enumerate(audit_rows):
        card_html = generate_earmark_card(idx, row, audit_rows)
        html_content += card_html
    
    # Add JavaScript and closing tags
    html_content += f"""
        </div>
        
        <!-- No Results Message -->
        <div id="no-results" class="hidden" style="text-align: center; padding: 60px 20px; color: #999;">
            <div style="font-size: 48px; margin-bottom: 20px;">🔍</div>
            <h3>No matching items found</h3>
            <p>Try adjusting your filters or search terms</p>
        </div>
    </div>
    
    <!-- Keyboard Shortcuts Help Button -->
    <div class="shortcuts-help" onclick="toggleShortcutsModal()">
        ⌨️
    </div>
    
    <!-- Shortcuts Modal -->
    <div class="shortcuts-modal" id="shortcuts-modal" onclick="toggleShortcutsModal()">
        <div class="shortcuts-content" onclick="event.stopPropagation()">
            <h2>⌨️ Keyboard Shortcuts</h2>
            <p style="color: #666;">Master these to fly through audits</p>
            <div class="shortcuts-grid">
                <div class="shortcut-key">J / ↓</div>
                <div class="shortcut-desc">Next card</div>
                
                <div class="shortcut-key">K / ↑</div>
                <div class="shortcut-desc">Previous card</div>
                
                <div class="shortcut-key">C</div>
                <div class="shortcut-desc">Mark as Correct (auto-advance)</div>
                
                <div class="shortcut-key">W</div>
                <div class="shortcut-desc">Mark as Wrong (open correction)</div>
                
                <div class="shortcut-key">U</div>
                <div class="shortcut-desc">Mark as Unsure</div>
                
                <div class="shortcut-key">S</div>
                <div class="shortcut-desc">Skip (no decision)</div>
                
                <div class="shortcut-key">Space</div>
                <div class="shortcut-desc">Toggle card selection</div>
                
                <div class="shortcut-key">Shift + A</div>
                <div class="shortcut-desc">Select all visible</div>
                
                <div class="shortcut-key">/ or F</div>
                <div class="shortcut-desc">Focus search box</div>
                
                <div class="shortcut-key">Esc</div>
                <div class="shortcut-desc">Clear selection / Close modal</div>
                
                <div class="shortcut-key">E</div>
                <div class="shortcut-desc">Export audit decisions</div>
                
                <div class="shortcut-key">Shift + E</div>
                <div class="shortcut-desc">Edit metadata fields</div>
                
                <div class="shortcut-key">?</div>
                <div class="shortcut-desc">Show this help</div>
            </div>
            <button class="btn btn-primary" onclick="toggleShortcutsModal()" style="margin-top: 20px; width: 100%;">
                Got it!
            </button>
        </div>
    </div>
    
    <script>
        // Global state
        const ALL_MEMBERS = {member_list_json};
        let currentCardIndex = -1;
        let selectedCards = new Set();
        let activeQueue = 'all';
        
        // Initialize on load
        window.addEventListener('load', () => {{
            restoreAuditState();
            updateAllCounters();
            scrollToCurrentCard();
            
            // Auto-focus search on '/' or 'f'
            document.addEventListener('keydown', handleGlobalKeyboard);
        }});
        
        // Keyboard Navigation
        function handleGlobalKeyboard(e) {{
            // Don't intercept if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
                if (e.key === 'Escape') {{
                    e.target.blur();
                }}
                return;
            }}
            
            const key = e.key.toLowerCase();
            
            switch(key) {{
                case 'j':
                case 'arrowdown':
                    e.preventDefault();
                    navigateToNextCard();
                    break;
                case 'k':
                case 'arrowup':
                    e.preventDefault();
                    navigateToPreviousCard();
                    break;
                case 'c':
                    e.preventDefault();
                    markCurrentAndAdvance('correct');
                    break;
                case 'w':
                    e.preventDefault();
                    markCurrentAndAdvance('wrong');
                    break;
                case 'u':
                    e.preventDefault();
                    markCurrentAndAdvance('unsure');
                    break;
                case 's':
                    e.preventDefault();
                    navigateToNextCard();
                    break;
                case ' ':
                    e.preventDefault();
                    toggleCurrentSelection();
                    break;
                case 'a':
                    if (e.shiftKey) {{
                        e.preventDefault();
                        selectAllVisible();
                    }}
                    break;
                case '/':
                case 'f':
                    e.preventDefault();
                    document.getElementById('searchBox').focus();
                    break;
                case 'escape':
                    deselectAll();
                    closeAllModals();
                    break;
                case 'e':
                    if (e.shiftKey) {{
                        // Shift+E: Edit metadata for current card
                        e.preventDefault();
                        const visibleCards = Array.from(document.querySelectorAll('.earmark-card:not(.hidden)'));
                        if (currentCardIndex >= 0 && currentCardIndex < visibleCards.length) {{
                            const cardId = parseInt(visibleCards[currentCardIndex].id.replace('card-', ''));
                            toggleMetadataEdit(cardId);
                        }}
                    }} else {{
                        // E: Export
                        e.preventDefault();
                        exportAuditDecisions();
                    }}
                    break;
                case '?':
                    e.preventDefault();
                    toggleShortcutsModal();
                    break;
            }}
        }}
        
        function navigateToNextCard() {{
            const visibleCards = Array.from(document.querySelectorAll('.earmark-card:not(.hidden)'));
            if (visibleCards.length === 0) return;
            
            // Remove current highlight
            if (currentCardIndex >= 0 && currentCardIndex < visibleCards.length) {{
                visibleCards[currentCardIndex].classList.remove('current');
            }}
            
            // Move to next
            currentCardIndex = (currentCardIndex + 1) % visibleCards.length;
            const nextCard = visibleCards[currentCardIndex];
            nextCard.classList.add('current');
            nextCard.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            
            // Save position
            localStorage.setItem('audit-current-position', currentCardIndex);
        }}
        
        function navigateToPreviousCard() {{
            const visibleCards = Array.from(document.querySelectorAll('.earmark-card:not(.hidden)'));
            if (visibleCards.length === 0) return;
            
            // Remove current highlight
            if (currentCardIndex >= 0 && currentCardIndex < visibleCards.length) {{
                visibleCards[currentCardIndex].classList.remove('current');
            }}
            
            // Move to previous
            currentCardIndex = currentCardIndex <= 0 ? visibleCards.length - 1 : currentCardIndex - 1;
            const prevCard = visibleCards[currentCardIndex];
            prevCard.classList.add('current');
            prevCard.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            
            // Save position
            localStorage.setItem('audit-current-position', currentCardIndex);
        }}
        
        function markCurrentAndAdvance(status) {{
            const visibleCards = Array.from(document.querySelectorAll('.earmark-card:not(.hidden)'));
            if (currentCardIndex < 0 || currentCardIndex >= visibleCards.length) {{
                // No current card, mark first visible
                currentCardIndex = 0;
            }}
            
            const currentCard = visibleCards[currentCardIndex];
            const cardId = parseInt(currentCard.id.replace('card-', ''));
            
            if (status === 'wrong') {{
                // Open correction panel for wrong
                markStatus(cardId, status);
                // Focus on correction search
                const correctionInput = currentCard.querySelector('.correction-search input');
                if (correctionInput) {{
                    correctionInput.focus();
                }}
            }} else {{
                // Mark and advance
                markStatus(cardId, status);
                setTimeout(() => navigateToNextCard(), 200);
            }}
        }}
        
        function toggleCurrentSelection() {{
            const visibleCards = Array.from(document.querySelectorAll('.earmark-card:not(.hidden)'));
            if (currentCardIndex < 0 || currentCardIndex >= visibleCards.length) return;
            
            const checkbox = visibleCards[currentCardIndex].querySelector('.card-checkbox');
            if (checkbox) {{
                checkbox.checked = !checkbox.checked;
                toggleSelection(checkbox);
            }}
        }}
        
        function scrollToCurrentCard() {{
            const visibleCards = Array.from(document.querySelectorAll('.earmark-card:not(.hidden)'));
            if (currentCardIndex >= 0 && currentCardIndex < visibleCards.length) {{
                const card = visibleCards[currentCardIndex];
                card.classList.add('current');
                setTimeout(() => {{
                    card.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}, 300);
            }}
        }}
        
        // Mark Status
        function markStatus(cardId, status) {{
            const card = document.getElementById(`card-${{cardId}}`);
            if (!card) return;
            
            card.setAttribute('data-status', status);
            
            // Update visual styling
            card.classList.remove('status-correct', 'status-wrong', 'status-unsure');
            card.classList.add(`status-${{status}}`);
            
            // Show/hide correction panel
            const correctionPanel = card.querySelector('.correction-panel');
            if (correctionPanel) {{
                if (status === 'wrong') {{
                    correctionPanel.classList.add('active');
                }} else {{
                    correctionPanel.classList.remove('active');
                }}
            }}
            
            // Store in localStorage
            const notes = document.getElementById(`notes-${{cardId}}`).value;
            const correctedMember = card.getAttribute('data-corrected-member') || '';
            
            localStorage.setItem(`audit-${{cardId}}`, JSON.stringify({{
                status: status,
                notes: notes,
                correctedMember: correctedMember,
                timestamp: new Date().toISOString()
            }}));
            
            // Update counters
            updateAllCounters();
        }}
        
        // Bulk Actions
        function toggleSelection(checkbox) {{
            const cardId = checkbox.getAttribute('data-card-id');
            const card = document.getElementById(`card-${{cardId}}`);
            
            if (checkbox.checked) {{
                selectedCards.add(cardId);
                card.classList.add('selected');
            }} else {{
                selectedCards.delete(cardId);
                card.classList.remove('selected');
            }}
            
            updateBulkActionsToolbar();
        }}
        
        function selectAllVisible() {{
            const visibleCards = document.querySelectorAll('.earmark-card:not(.hidden)');
            visibleCards.forEach(card => {{
                const checkbox = card.querySelector('.card-checkbox');
                if (checkbox && !checkbox.checked) {{
                    checkbox.checked = true;
                    toggleSelection(checkbox);
                }}
            }});
        }}
        
        function deselectAll() {{
            selectedCards.clear();
            document.querySelectorAll('.card-checkbox:checked').forEach(cb => {{
                cb.checked = false;
            }});
            document.querySelectorAll('.earmark-card.selected').forEach(card => {{
                card.classList.remove('selected');
            }});
            updateBulkActionsToolbar();
        }}
        
        function bulkMarkStatus(status) {{
            if (selectedCards.size === 0) return;
            
            if (!confirm(`Mark ${{selectedCards.size}} items as ${{status}}?`)) return;
            
            selectedCards.forEach(cardId => {{
                markStatus(parseInt(cardId), status);
            }});
            
            deselectAll();
        }}
        
        function updateBulkActionsToolbar() {{
            const toolbar = document.getElementById('bulk-actions');
            const selectedInfo = document.getElementById('selected-info');
            const bulkCount = document.getElementById('bulk-selected-count');
            const selectedCount = document.getElementById('selected-count');
            
            if (selectedCards.size > 0) {{
                toolbar.classList.add('active');
                selectedInfo.classList.remove('hidden');
                bulkCount.textContent = selectedCards.size;
                selectedCount.textContent = selectedCards.size;
            }} else {{
                toolbar.classList.remove('active');
                selectedInfo.classList.add('hidden');
            }}
        }}
        
        // Smart Queues
        function applyQueue(queueName) {{
            activeQueue = queueName;
            
            // Update active button
            document.querySelectorAll('.queue-button').forEach(btn => {{
                btn.classList.remove('active');
            }});
            document.querySelector(`[data-queue="${{queueName}}"]`).classList.add('active');
            
            // Apply filters based on queue
            const cards = document.querySelectorAll('.earmark-card');
            
            cards.forEach(card => {{
                let show = true;
                const status = card.getAttribute('data-status') || 'unverified';
                const confidence = parseFloat(card.getAttribute('data-confidence') || '0');
                const amount = parseFloat(card.getAttribute('data-amount') || '0');
                
                switch(queueName) {{
                    case 'all':
                        show = true;
                        break;
                    case 'high-priority':
                        show = confidence < 0.7 && amount > 100000;
                        break;
                    case 'quick-wins':
                        show = confidence >= 0.9;
                        break;
                    case 'needs-attention':
                        show = confidence < 0.7 || card.classList.contains('unmatched');
                        break;
                    case 'unverified':
                        show = status === 'unverified';
                        break;
                    case 'flagged':
                        show = status === 'wrong';
                        break;
                }}
                
                card.classList.toggle('hidden', !show);
            }});
            
            updateVisibleCount();
            checkNoResults();
            
            // Reset navigation to first visible
            currentCardIndex = -1;
            navigateToNextCard();
        }}
        
        // Filtering
        function filterCards() {{
            const searchText = document.getElementById('searchBox').value.toLowerCase();
            const chamber = document.getElementById('chamberFilter').value;
            const status = document.getElementById('statusFilter').value;
            const confidenceLevel = document.getElementById('confidenceFilter').value;
            const amountLevel = document.getElementById('amountFilter').value;
            
            const cards = document.querySelectorAll('.earmark-card');
            
            cards.forEach(card => {{
                const text = card.textContent.toLowerCase();
                const cardChamber = card.getAttribute('data-chamber');
                const cardStatus = card.getAttribute('data-status') || 'unverified';
                const confidence = parseFloat(card.getAttribute('data-confidence') || '0');
                const amount = parseFloat(card.getAttribute('data-amount') || '0');
                
                const matchesSearch = !searchText || text.includes(searchText);
                const matchesChamber = !chamber || cardChamber === chamber;
                const matchesStatus = !status || cardStatus === status;
                
                let matchesConfidence = true;
                if (confidenceLevel === 'high') matchesConfidence = confidence >= 0.9;
                else if (confidenceLevel === 'medium') matchesConfidence = confidence >= 0.7 && confidence < 0.9;
                else if (confidenceLevel === 'low') matchesConfidence = confidence < 0.7;
                
                let matchesAmount = true;
                if (amountLevel === 'mega') matchesAmount = amount >= 1000000;
                else if (amountLevel === 'large') matchesAmount = amount >= 100000 && amount < 1000000;
                else if (amountLevel === 'medium') matchesAmount = amount >= 10000 && amount < 100000;
                else if (amountLevel === 'small') matchesAmount = amount < 10000;
                
                const shouldShow = matchesSearch && matchesChamber && matchesStatus && matchesConfidence && matchesAmount;
                card.classList.toggle('hidden', !shouldShow);
            }});
            
            updateVisibleCount();
            checkNoResults();
        }}
        
        function clearFilters() {{
            document.getElementById('searchBox').value = '';
            document.getElementById('chamberFilter').value = '';
            document.getElementById('statusFilter').value = '';
            document.getElementById('confidenceFilter').value = '';
            document.getElementById('amountFilter').value = '';
            applyQueue('all');
        }}
        
        function updateVisibleCount() {{
            const visible = document.querySelectorAll('.earmark-card:not(.hidden)').length;
            document.getElementById('visible-count').textContent = visible;
        }}
        
        function checkNoResults() {{
            const visible = document.querySelectorAll('.earmark-card:not(.hidden)').length;
            const noResults = document.getElementById('no-results');
            const container = document.getElementById('earmarkContainer');
            
            if (visible === 0) {{
                noResults.classList.remove('hidden');
                container.classList.add('hidden');
            }} else {{
                noResults.classList.add('hidden');
                container.classList.remove('hidden');
            }}
        }}
        
        // Update Counters
        function updateAllCounters() {{
            const cards = document.querySelectorAll('.earmark-card');
            let correct = 0, wrong = 0, unsure = 0, unreviewed = 0;
            
            cards.forEach(card => {{
                const status = card.getAttribute('data-status') || 'unverified';
                switch(status) {{
                    case 'correct': correct++; break;
                    case 'wrong': wrong++; break;
                    case 'unsure': unsure++; break;
                    default: unreviewed++; break;
                }}
            }});
            
            const total = cards.length;
            const verified = correct + wrong + unsure;
            const remaining = unreviewed;
            
            // Update header stats
            document.getElementById('total-count').textContent = total;
            document.getElementById('verified-count').textContent = verified;
            document.getElementById('remaining-count').textContent = remaining;
            
            // Estimate time (assume 30 seconds per item)
            const estimatedMinutes = Math.ceil(remaining * 0.5);
            const hours = Math.floor(estimatedMinutes / 60);
            const mins = estimatedMinutes % 60;
            let timeStr = hours > 0 ? `${{hours}}h ${{mins}}m` : `${{mins}}m`;
            document.getElementById('accuracy-rate').textContent = timeStr;
            
            // Update progress stats
            document.getElementById('correct-count').textContent = correct;
            document.getElementById('wrong-count').textContent = wrong;
            document.getElementById('unsure-count').textContent = unsure;
            document.getElementById('unreviewed-count').textContent = unreviewed;
            
            // Update progress bar
            const correctPct = (correct / total * 100).toFixed(1);
            const wrongPct = (wrong / total * 100).toFixed(1);
            const unsurePct = (unsure / total * 100).toFixed(1);
            const unreviewedPct = (unreviewed / total * 100).toFixed(1);
            
            const progressBar = document.getElementById('progress-bar');
            progressBar.innerHTML = `
                <div class="progress-segment progress-correct" style="width: ${{correctPct}}%"></div>
                <div class="progress-segment progress-wrong" style="width: ${{wrongPct}}%"></div>
                <div class="progress-segment progress-unsure" style="width: ${{unsurePct}}%"></div>
                <div class="progress-segment progress-unreviewed" style="width: ${{unreviewedPct}}%"></div>
            `;
        }}
        
        // Inline Correction
        function showCorrectionPanel(cardId) {{
            const panel = document.querySelector(`#card-${{cardId}} .correction-panel`);
            if (panel) {{
                panel.classList.toggle('active');
                if (panel.classList.contains('active')) {{
                    const input = panel.querySelector('input');
                    if (input) input.focus();
                }}
            }}
        }}
        
        function searchMembers(cardId, query) {{
            const results = document.querySelector(`#card-${{cardId}} .correction-results`);
            if (!results) return;
            
            if (query.length < 2) {{
                results.classList.remove('active');
                return;
            }}
            
            // Filter members by query
            const matches = ALL_MEMBERS.filter(m => 
                m.name.toLowerCase().includes(query.toLowerCase()) ||
                m.district.toLowerCase().includes(query.toLowerCase())
            ).slice(0, 10);
            
            if (matches.length > 0) {{
                results.innerHTML = matches.map(m => `
                    <div class="correction-result-item" onclick="selectCorrectedMember(${{cardId}}, '${{m.code}}', '${{m.name}}')">
                        <div class="result-name">${{m.name}}</div>
                        <div class="result-details">${{m.chamber}} - ${{m.district}}</div>
                    </div>
                `).join('');
                results.classList.add('active');
            }} else {{
                results.innerHTML = '<div class="correction-result-item">No matches found</div>';
                results.classList.add('active');
            }}
        }}
        
        function selectCorrectedMember(cardId, memberCode, memberName) {{
            const card = document.getElementById(`card-${{cardId}}`);
            const input = card.querySelector('.correction-search input');
            const results = card.querySelector('.correction-results');
            
            if (input) input.value = memberName;
            if (results) results.classList.remove('active');
            
            // Store correction
            card.setAttribute('data-corrected-member', memberCode);
            card.setAttribute('data-corrected-name', memberName);
            
            // Update notes field
            const notesField = document.getElementById(`notes-${{cardId}}`);
            if (notesField) {{
                notesField.value = `Should be: ${{memberName}} (${{memberCode}})`;
            }}
            
            // Save to localStorage
            const saved = localStorage.getItem(`audit-${{cardId}}`);
            const data = saved ? JSON.parse(saved) : {{}};
            data.correctedMember = memberCode;
            data.correctedName = memberName;
            localStorage.setItem(`audit-${{cardId}}`, JSON.stringify(data));
        }}
        
        // Metadata Editing Functions
        function toggleMetadataEdit(cardId) {{
            const panel = document.getElementById(`metadata-edit-${{cardId}}`);
            if (panel) {{
                const isVisible = panel.style.display !== 'none';
                panel.style.display = isVisible ? 'none' : 'block';
                
                // Focus first input when opening
                if (!isVisible) {{
                    const firstInput = panel.querySelector('input');
                    if (firstInput) {{
                        setTimeout(() => firstInput.focus(), 100);
                    }}
                }}
            }}
        }}
        
        function saveMetadataEdits(cardId) {{
            const card = document.getElementById(`card-${{cardId}}`);
            
            // Get edited values
            const location = document.getElementById(`edit-location-${{cardId}}`).value.trim();
            const organization = document.getElementById(`edit-organization-${{cardId}}`).value.trim();
            const category = document.getElementById(`edit-category-${{cardId}}`).value;
            const lineItem = document.getElementById(`edit-line-item-${{cardId}}`).value.trim();
            const amount = document.getElementById(`edit-amount-${{cardId}}`).value;
            
            // Get original values
            const origLocation = document.getElementById(`edit-location-${{cardId}}`).dataset.original;
            const origOrg = document.getElementById(`edit-organization-${{cardId}}`).dataset.original;
            const origLineItem = document.getElementById(`edit-line-item-${{cardId}}`).dataset.original;
            const origAmount = document.getElementById(`edit-amount-${{cardId}}`).dataset.original;
            const origCategory = document.getElementById(`edit-category-${{cardId}}`).dataset.original;
            
            // Determine which fields were manually edited
            const editedFields = [];
            if (location !== origLocation) editedFields.push('location');
            if (organization !== origOrg) editedFields.push('organization');
            if (category !== origCategory) editedFields.push('category');
            if (lineItem !== origLineItem) editedFields.push('line_item');
            if (amount !== origAmount) editedFields.push('amount');
            
            // Store in card data attributes
            card.setAttribute('data-location', location);
            card.setAttribute('data-organization', organization);
            card.setAttribute('data-category', category);
            card.setAttribute('data-line-item', lineItem);
            card.setAttribute('data-amount', amount);
            card.setAttribute('data-edited-fields', editedFields.join(','));
            
            // Save to localStorage
            const saved = localStorage.getItem(`audit-${{cardId}}`);
            const data = saved ? JSON.parse(saved) : {{}};
            data.metadata = {{
                location: location,
                organization: organization,
                category: category,
                line_item: lineItem,
                amount: parseFloat(amount) || 0,
                edited_fields: editedFields
            }};
            localStorage.setItem(`audit-${{cardId}}`, JSON.stringify(data));
            
            // Visual feedback
            const inputs = [
                document.getElementById(`edit-location-${{cardId}}`),
                document.getElementById(`edit-organization-${{cardId}}`),
                document.getElementById(`edit-line-item-${{cardId}}`),
                document.getElementById(`edit-amount-${{cardId}}`)
            ];
            
            inputs.forEach(input => {{
                if (input && input.value !== input.dataset.original) {{
                    input.classList.add('modified');
                }} else if (input) {{
                    input.classList.remove('modified');
                }}
            }});
            
            // Show success message
            alert(`Metadata saved! ${{editedFields.length}} field(s) modified.`);
        }}
        
        function resetMetadataEdits(cardId) {{
            if (!confirm('Reset all fields to auto-detected values?')) return;
            
            const fields = [
                'edit-location',
                'edit-organization',
                'edit-line-item',
                'edit-amount'
            ];
            
            fields.forEach(fieldId => {{
                const input = document.getElementById(`${{fieldId}}-${{cardId}}`);
                if (input) {{
                    input.value = input.dataset.original;
                    input.classList.remove('modified');
                }}
            }});
            
            // Reset category to empty
            const categorySelect = document.getElementById(`edit-category-${{cardId}}`);
            if (categorySelect) {{
                categorySelect.value = '';
            }}
            
            // Clear from localStorage
            const saved = localStorage.getItem(`audit-${{cardId}}`);
            if (saved) {{
                const data = JSON.parse(saved);
                delete data.metadata;
                localStorage.setItem(`audit-${{cardId}}`, JSON.stringify(data));
            }}
        }}
        
        // Session Management
        function restoreAuditState() {{
            const cards = document.querySelectorAll('.earmark-card');
            cards.forEach((card, idx) => {{
                const saved = localStorage.getItem(`audit-${{idx}}`);
                if (saved) {{
                    const data = JSON.parse(saved);
                    if (data.status) {{
                        markStatus(idx, data.status);
                    }}
                    if (data.notes) {{
                        const notesField = document.getElementById(`notes-${{idx}}`);
                        if (notesField) notesField.value = data.notes;
                    }}
                    if (data.correctedMember) {{
                        card.setAttribute('data-corrected-member', data.correctedMember);
                        if (data.correctedName) {{
                            card.setAttribute('data-corrected-name', data.correctedName);
                        }}
                    }}
                    // Restore metadata edits
                    if (data.metadata) {{
                        const meta = data.metadata;
                        if (meta.location !== undefined) {{
                            const input = document.getElementById(`edit-location-${{idx}}`);
                            if (input) {{
                                input.value = meta.location;
                                if (meta.location !== input.dataset.original) {{
                                    input.classList.add('modified');
                                }}
                            }}
                        }}
                        if (meta.organization !== undefined) {{
                            const input = document.getElementById(`edit-organization-${{idx}}`);
                            if (input) {{
                                input.value = meta.organization;
                                if (meta.organization !== input.dataset.original) {{
                                    input.classList.add('modified');
                                }}
                            }}
                        }}
                        if (meta.category !== undefined) {{
                            const select = document.getElementById(`edit-category-${{idx}}`);
                            if (select) select.value = meta.category;
                        }}
                        if (meta.line_item !== undefined) {{
                            const input = document.getElementById(`edit-line-item-${{idx}}`);
                            if (input) {{
                                input.value = meta.line_item;
                                if (meta.line_item !== input.dataset.original) {{
                                    input.classList.add('modified');
                                }}
                            }}
                        }}
                        if (meta.amount !== undefined) {{
                            const input = document.getElementById(`edit-amount-${{idx}}`);
                            if (input) {{
                                input.value = meta.amount;
                                if (meta.amount !== parseFloat(input.dataset.original)) {{
                                    input.classList.add('modified');
                                }}
                            }}
                        }}
                    }}
                }}
            }});
            
            // Restore position
            const savedPosition = localStorage.getItem('audit-current-position');
            if (savedPosition !== null) {{
                currentCardIndex = parseInt(savedPosition);
            }}
        }}
        
        function resumeAudit() {{
            // Find first unverified card
            const cards = document.querySelectorAll('.earmark-card');
            for (let i = 0; i < cards.length; i++) {{
                const status = cards[i].getAttribute('data-status') || 'unverified';
                if (status === 'unverified') {{
                    currentCardIndex = i;
                    scrollToCurrentCard();
                    return;
                }}
            }}
            
            // All done!
            alert('🎉 All items have been reviewed! Click Export to save your decisions.');
        }}
        
        // Export
        function exportAuditDecisions() {{
            const cards = document.querySelectorAll('.earmark-card');
            const decisions = [];
            let verifiedCount = 0;
            
            cards.forEach((card, idx) => {{
                const saved = localStorage.getItem(`audit-${{idx}}`);
                const amendmentNum = card.querySelector('.amendment-num').textContent.replace('Amendment #', '');
                const assignedTo = card.getAttribute('data-assigned-to') || '';
                const amount = parseFloat(card.getAttribute('data-amount') || '0');
                const chamber = card.getAttribute('data-chamber') || '';
                const sponsorInPdf = card.getAttribute('data-sponsor') || '';
                const fiscalYear = card.getAttribute('data-fiscal-year') || '';
                const lineItem = card.getAttribute('data-line-item') || '';
                const location = card.getAttribute('data-location') || '';
                const organization = card.getAttribute('data-organization') || '';
                
                let status = 'unverified';
                let notes = '';
                let correctedMember = '';
                let correctedName = '';
                let metadata = null;
                let editedFields = [];
                
                if (saved) {{
                    const data = JSON.parse(saved);
                    status = data.status || 'unverified';
                    notes = data.notes || '';
                    correctedMember = data.correctedMember || '';
                    correctedName = data.correctedName || '';
                    if (status !== 'unverified') verifiedCount++;
                    
                    // Get manually edited metadata if it exists
                    if (data.metadata) {{
                        metadata = data.metadata;
                        editedFields = metadata.edited_fields || [];
                    }}
                }}
                
                // Read current values from DOM (in case user edited but didn't click Save)
                const locationInput = document.getElementById(`edit-location-${{idx}}`);
                const organizationInput = document.getElementById(`edit-organization-${{idx}}`);
                const categorySelect = document.getElementById(`edit-category-${{idx}}`);
                const lineItemInput = document.getElementById(`edit-line-item-${{idx}}`);
                const amountInput = document.getElementById(`edit-amount-${{idx}}`);
                
                // Use DOM values if they exist and differ from original, otherwise use saved metadata, otherwise use card attributes
                const finalLocation = (locationInput && locationInput.value !== locationInput.dataset.original) 
                    ? locationInput.value 
                    : (metadata?.location || location);
                    
                const finalOrganization = (organizationInput && organizationInput.value !== organizationInput.dataset.original) 
                    ? organizationInput.value 
                    : (metadata?.organization || organization);
                    
                // For category, prioritize saved metadata over current DOM value since the dropdown
                // might have been reset or never changed from default
                const finalCategory = metadata?.category 
                    || (categorySelect && categorySelect.value && categorySelect.value !== categorySelect.dataset.original ? categorySelect.value : '')
                    || '';
                    
                const finalLineItem = (lineItemInput && lineItemInput.value !== lineItemInput.dataset.original) 
                    ? lineItemInput.value 
                    : (metadata?.line_item || lineItem);
                    
                const finalAmount = (amountInput && amountInput.value !== amountInput.dataset.original) 
                    ? parseFloat(amountInput.value) || 0 
                    : (metadata?.amount || amount);
                
                // Track which fields were actually edited (differ from originals)
                const actualEditedFields = [];
                if (locationInput && locationInput.value && locationInput.value !== locationInput.dataset.original) {{
                    actualEditedFields.push('location');
                }}
                if (organizationInput && organizationInput.value && organizationInput.value !== organizationInput.dataset.original) {{
                    actualEditedFields.push('organization');
                }}
                if (categorySelect && categorySelect.value) {{
                    actualEditedFields.push('category');
                }}
                if (lineItemInput && lineItemInput.value && lineItemInput.value !== lineItemInput.dataset.original) {{
                    actualEditedFields.push('line_item');
                }}
                if (amountInput && amountInput.value && parseFloat(amountInput.value) !== parseFloat(amountInput.dataset.original)) {{
                    actualEditedFields.push('amount');
                }}
                
                decisions.push({{
                    amendment_number: amendmentNum,
                    fiscal_year: fiscalYear,
                    assigned_to: assignedTo,
                    extracted_amount: finalAmount,
                    chamber: chamber,
                    sponsor_in_pdf: sponsorInPdf,
                    line_item: finalLineItem,
                    location: finalLocation,
                    organization_or_recipient: finalOrganization,
                    subject_category: finalCategory,
                    audit_status: status,
                    audit_notes: notes,
                    corrected_member_code: correctedMember,
                    corrected_member_name: correctedName,
                    manually_edited_fields: actualEditedFields,
                    audited_at: new Date().toISOString()
                }});
            }});
            
            // Create export object
            const exportData = {{
                audit_metadata: {{
                    total_items: decisions.length,
                    verified_count: verifiedCount,
                    correct_count: decisions.filter(d => d.audit_status === 'correct').length,
                    wrong_count: decisions.filter(d => d.audit_status === 'wrong').length,
                    unsure_count: decisions.filter(d => d.audit_status === 'unsure').length,
                    unverified_count: decisions.filter(d => d.audit_status === 'unverified').length,
                    exported_at: new Date().toISOString(),
                    audit_session_duration: null  // Could track this
                }},
                decisions: decisions
            }};
            
            // Download as JSON
            const dataStr = JSON.stringify(exportData, null, 2);
            const dataBlob = new Blob([dataStr], {{type: 'application/json'}});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `earmark_audit_decisions_${{new Date().toISOString().split('T')[0]}}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            // Show success message
            const statusEl = document.getElementById('export-status');
            statusEl.textContent = `✓ Exported ${{verifiedCount}} verified items of ${{decisions.length}} total`;
            setTimeout(() => {{
                statusEl.textContent = '';
            }}, 5000);
        }}
        
        // Modals
        function toggleShortcutsModal() {{
            const modal = document.getElementById('shortcuts-modal');
            modal.classList.toggle('active');
        }}
        
        function closeAllModals() {{
            document.querySelectorAll('.shortcuts-modal').forEach(m => {{
                m.classList.remove('active');
            }});
            document.querySelectorAll('.correction-panel').forEach(p => {{
                p.classList.remove('active');
            }});
        }}
        
        // Initialize
        console.log('Enhanced Earmark Audit System loaded');
        console.log('Press ? for keyboard shortcuts');
    </script>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  [+] Enhanced HTML audit report: {output_path}")
    print(f"    ✨ NEW: Keyboard shortcuts, bulk actions, smart queues")
    print(f"    ✨ NEW: Progress tracking, inline corrections")
    print(f"    ✨ NEW: Mobile-responsive, 1000+ entry optimized")


def generate_earmark_card(idx: int, row: dict[str, Any], all_rows: list[dict[str, Any]]) -> str:
    """Generate HTML for a single earmark card with enhanced features."""
    
    amount = row.get('extracted_amount') or 0
    confidence = row.get('match_confidence') or 0
    
    # Determine amount class
    if amount >= 1000000:
        amount_class = 'large'
    elif amount >= 100000:
        amount_class = 'medium'
    else:
        amount_class = ''
    
    # Determine card class
    card_classes = ['earmark-card']
    if row.get('member_code') in ('UNKNOWN', 'UNMATCHED'):
        card_classes.append('unmatched')
    elif confidence < 0.7:
        card_classes.append('low-confidence')
    
    # Confidence badge
    if confidence >= 0.9:
        conf_badge_class = 'badge-high'
        conf_text = f'High: {confidence:.0%}'
        conf_icon = '[OK]'
    elif confidence >= 0.7:
        conf_badge_class = 'badge-medium'
        conf_text = f'Medium: {confidence:.0%}'
        conf_icon = '[~]'
    else:
        conf_badge_class = 'badge-low'
        conf_text = f'Low: {confidence:.0%}'
        conf_icon = '[!]'
    
    confidence_badge = f'<span class="badge badge-confidence {conf_badge_class}">{conf_icon} {conf_text}</span>' if confidence > 0 else ''
    
    # Chamber badge
    chamber = row.get('chamber', '')
    chamber_badge = ''
    if chamber:
        chamber_class = f"badge-{chamber.lower()}"
        chamber_badge = f'<span class="badge {chamber_class}">{chamber}</span>'
    
    # Highlight text
    raw_text = html.escape(row.get('raw_text', ''))
    if amount:
        # Highlight amount
        for pattern in [f"${amount:,.0f}", f"${amount/1000:.0f}K", f"${amount/1000000:.1f}M"]:
            if pattern in raw_text:
                raw_text = raw_text.replace(pattern, f'<span class="highlight">{pattern}</span>')
                break
    
    # Highlight location if present
    location = row.get('location')
    if location:
        loc_escaped = html.escape(location)
        raw_text = raw_text.replace(loc_escaped, f'<span class="highlight-location">{loc_escaped}</span>')
    
    # Highlight organization if present
    organization = row.get('organization_or_recipient')
    if organization:
        org_escaped = html.escape(organization)
        raw_text = raw_text.replace(org_escaped, f'<span class="highlight-org">{org_escaped}</span>')
    
    # Escape values for use in HTML (can't use html.escape() inside f-strings)
    assigned_to_esc = html.escape(row.get('assigned_to', 'N/A'))
    sponsor_esc = html.escape(row.get('sponsor_in_pdf', 'N/A'))
    line_item_esc = html.escape(row.get('line_item', 'N/A'))
    location_esc = html.escape(location or 'Not specified')
    organization_esc = html.escape(organization or 'Not specified')
    district_esc = html.escape(row.get('district', 'N/A'))
    match_method_esc = html.escape(row.get('match_method', 'N/A'))
    
    # Build data attributes
    data_attrs = f"""
        id="card-{idx}"
        data-chamber="{chamber}"
        data-status="unverified"
        data-confidence="{confidence}"
        data-amount="{amount}"
        data-assigned-to="{assigned_to_esc}"
        data-sponsor="{sponsor_esc}"
        data-fiscal-year="{row.get('fiscal_year', '')}"
        data-line-item="{line_item_esc}"
        data-location="{location_esc}"
        data-organization="{organization_esc}"
    """
    
    # Join card classes outside f-string
    card_classes_str = ' '.join(card_classes)
    
    # Build expand text button (avoiding backslashes in f-string)
    expand_text_html = ''
    if len(raw_text) > 500:
        expand_text_html = f'<span class="expand-text" onclick="document.getElementById(\'text-{idx}\').innerHTML = `{raw_text}`; this.style.display=\'none\';">▼ Show full text</span>'
    
    card_html = f"""
        <div class="{card_classes_str}" {data_attrs}>
            <input type="checkbox" class="card-checkbox" data-card-id="{idx}" onchange="toggleSelection(this)">
            
            <div class="earmark-header">
                <div class="header-left">
                    <div class="amendment-num">Amendment #{row.get('amendment_number', 'N/A')}</div>
                    <div class="badges">
                        {chamber_badge}
                        {confidence_badge}
                    </div>
                </div>
                <div class="amount {amount_class}">
                    ${amount:,.2f}
                </div>
            </div>
            
            <div class="comparison-view">
                <div class="comparison-panel comparison-pdf">
                    <div class="panel-title">From PDF</div>
                    <div class="panel-item">
                        <span class="panel-label">Sponsor:</span> {sponsor_esc}
                    </div>
                    <div class="panel-item">
                        <span class="panel-label">Location:</span> {location_esc}
                    </div>
                    <div class="panel-item">
                        <span class="panel-label">Organization:</span> {organization_esc}
                    </div>
                    <div class="panel-item">
                        <span class="panel-label">Line Item:</span> {line_item_esc}
                    </div>
                </div>
                
                <div class="comparison-panel comparison-system">
                    <div class="panel-title">System Assigned</div>
                    <div class="panel-item">
                        <span class="panel-label">To:</span> {assigned_to_esc}
                        <span class="match-indicator">[OK]</span>
                    </div>
                    <div class="panel-item">
                        <span class="panel-label">District:</span> {district_esc}
                    </div>
                    <div class="panel-item">
                        <span class="panel-label">Match Method:</span> {match_method_esc}
                    </div>
                    <div class="panel-item">
                        <span class="panel-label">Confidence:</span> {confidence:.0%}
                    </div>
                </div>
            </div>
            
            <div class="raw-text" id="text-{idx}">
{raw_text[:500]}{'...' if len(raw_text) > 500 else ''}
            </div>
            {expand_text_html}
            
            <div class="verification">
                <button class="btn-correct" onclick="markStatus({idx}, 'correct')">
                    ✓ Correct
                </button>
                <button class="btn-wrong" onclick="markStatus({idx}, 'wrong'); showCorrectionPanel({idx})">
                    ✗ Wrong
                </button>
                <button class="btn-unsure" onclick="markStatus({idx}, 'unsure')">
                    ? Unsure
                </button>
                <button class="btn-skip" onclick="navigateToNextCard()">
                    Skip →
                </button>
                <input type="text" id="notes-{idx}" placeholder="Add notes...">
            </div>
            
            <div class="correction-panel" id="correction-{idx}">
                <h4 style="margin-top: 0;">Correct This Assignment</h4>
                <p style="font-size: 13px; color: #666; margin-bottom: 15px;">
                    Search for the correct member to assign this earmark to:
                </p>
                <div class="correction-search">
                    <input type="text" placeholder="Search member name or district..." 
                           oninput="searchMembers({idx}, this.value)"
                           onfocus="this.select()">
                    <div class="correction-results"></div>
                </div>
            </div>
            
            <div class="metadata-edit-section">
                <button class="btn-edit-metadata" onclick="toggleMetadataEdit({idx})" style="width: 100%; margin-bottom: 10px;">
                    Edit/Add Missing Fields
                </button>
                <div class="metadata-edit-panel" id="metadata-edit-{idx}" style="display: none;">
                    <h4 style="margin-top: 0;">Edit Extracted Fields</h4>
                    <p style="font-size: 12px; color: #666; margin-bottom: 15px;">
                        Fill in or correct fields that weren't auto-detected:
                    </p>
                    
                    <div class="edit-field">
                        <label for="edit-location-{idx}">Location (City/Town):</label>
                        <input type="text" id="edit-location-{idx}" 
                               value="{location_esc if location else ''}"
                               placeholder="e.g., Boston, Worcester County"
                               data-original="{location_esc if location else ''}">
                        <small>Auto-detected: {location_esc if location else 'None'}</small>
                    </div>
                    
                    <div class="edit-field">
                        <label for="edit-organization-{idx}">Organization/Recipient:</label>
                        <input type="text" id="edit-organization-{idx}" 
                               value="{organization_esc if organization else ''}"
                               placeholder="e.g., Boys & Girls Club, Community Center"
                               data-original="{organization_esc if organization else ''}">
                        <small>Auto-detected: {organization_esc if organization else 'None'}</small>
                    </div>
                    
                    <div class="edit-field">
                        <label for="edit-category-{idx}">Subject Category:</label>
                        <select id="edit-category-{idx}" data-original="">
                            <option value="">Not specified</option>
                            <option value="Health">Health</option>
                            <option value="Education">Education</option>
                            <option value="Infrastructure">Infrastructure</option>
                            <option value="Transportation">Transportation</option>
                            <option value="Arts & Culture">Arts & Culture</option>
                            <option value="Economic Development">Economic Development</option>
                            <option value="Public Safety">Public Safety</option>
                            <option value="Environment">Environment</option>
                            <option value="Housing">Housing</option>
                            <option value="Social Services">Social Services</option>
                            <option value="Parks & Recreation">Parks & Recreation</option>
                            <option value="Other">Other</option>
                        </select>
                        <small>Choose category for better organization</small>
                    </div>
                    
                    <div class="edit-field">
                        <label for="edit-line-item-{idx}">Line Item Code:</label>
                        <input type="text" id="edit-line-item-{idx}" 
                               value="{line_item_esc}"
                               placeholder="e.g., 7000-1234"
                               data-original="{line_item_esc}">
                        <small>Auto-detected: {line_item_esc}</small>
                    </div>
                    
                    <div class="edit-field">
                        <label for="edit-amount-{idx}">Amount ($):</label>
                        <input type="number" id="edit-amount-{idx}" 
                               value="{amount}"
                               placeholder="e.g., 250000"
                               data-original="{amount}">
                        <small>Auto-detected: ${amount:,.2f}</small>
                    </div>
                    
                    <div class="edit-actions">
                        <button class="btn btn-primary" onclick="saveMetadataEdits({idx})">
                            Save Changes
                        </button>
                        <button class="btn btn-secondary" onclick="resetMetadataEdits({idx})">
                            Reset to Auto-Detected
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="metadata">
                <span>Page {row.get('page_number', 'N/A')}</span>
                <span>FY{row.get('fiscal_year', 'N/A')}</span>
                <span>Match: {match_method_esc}</span>
            </div>
        </div>
    """
    
    return card_html

