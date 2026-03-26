#!/usr/bin/env python3
"""Generate HTML report for vision matching validation."""

import base64
import io
import json
from pathlib import Path

from PIL import Image


def image_to_base64(path: str, max_size: int = 400) -> str:
    """Convert image to base64 for HTML embedding, resizing if needed."""
    try:
        with Image.open(path) as img:
            if img.width > max_size or img.height > max_size:
                ratio = max_size / max(img.width, img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        print(f"Error loading image {path}: {e}")
        return ""


def generate_html_report(results_file: str = 'vision_matching_results.json',
                         output_file: str = 'validation_report.html'):
    """Generate HTML report with side-by-side comparisons."""

    with open(results_file) as f:
        results = json.load(f)

    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <title>Instagram Vision Matching Validation</title>',
        '    <style>',
        '        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }',
        '        .match-card { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
        '        .match-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #333; }',
        '        .comparison { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }',
        '        .image-box { text-align: center; }',
        '        .image-box img { max-width: 400px; max-height: 400px; border: 1px solid #ddd; border-radius: 4px; }',
        '        .image-label { font-size: 12px; color: #666; margin-top: 5px; word-break: break-all; }',
        '        .score-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 14px; }',
        '        .score-same { background: #4caf50; color: white; }',
        '        .score-uncertain { background: #ff9800; color: white; }',
        '        .score-different { background: #f44336; color: white; }',
        '        .match-info { margin-top: 10px; padding: 10px; background: #f9f9f9; border-radius: 4px; }',
        '        .top-matches { margin-top: 15px; }',
        '        .top-match { display: inline-block; margin: 5px; padding: 10px; background: #e3f2fd; border-radius: 4px; vertical-align: top; }',
        '        .top-match img { max-width: 150px; max-height: 150px; }',
        '        .legend { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }',
        '        .legend-item { display: inline-block; margin-right: 20px; }',
        '        .summary { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }',
        '        h1, h2, h3 { color: #333; }',
        '    </style>',
        '</head>',
        '<body>',
        '    <h1>Instagram Vision Matching Validation Report</h1>',
        '    <div class="legend">',
        '        <h3>Legend:</h3>',
        '        <div class="legend-item"><span class="score-badge score-same">SAME</span> = Confident match</div>',
        '        <div class="legend-item"><span class="score-badge score-uncertain">UNCERTAIN</span> = Needs review</div>',
        '        <div class="legend-item"><span class="score-badge score-different">DIFFERENT</span> = Not a match</div>',
        '    </div>',
    ]

    total = len(results)
    same_count = sum(1 for data in results.values() if data['top_matches'] and data['top_matches'][0]['vision_result'] == 'SAME')
    uncertain_count = sum(1 for data in results.values() if data['top_matches'] and data['top_matches'][0]['vision_result'] == 'UNCERTAIN')
    different_count = sum(1 for data in results.values() if data['top_matches'] and data['top_matches'][0]['vision_result'] == 'DIFFERENT')

    html_parts.append('    <div class="summary">')
    html_parts.append('        <h3>Summary:</h3>')
    html_parts.append(f'        <p>Total Instagram images: {total}</p>')
    html_parts.append(f'        <p>Matches marked as SAME: {same_count}</p>')
    html_parts.append(f'        <p>Matches marked as UNCERTAIN: {uncertain_count}</p>')
    html_parts.append(f'        <p>Matches marked as DIFFERENT: {different_count}</p>')
    html_parts.append('    </div>')

    for _insta_key, data in results.items():
        insta_img = data['insta_image']
        top_matches = data['top_matches']

        if not top_matches:
            continue

        best_match = top_matches[0]
        result = best_match['vision_result']

        if result == 'SAME':
            badge_class = 'score-same'
        elif result == 'UNCERTAIN':
            badge_class = 'score-uncertain'
        else:
            badge_class = 'score-different'

        html_parts.append('<div class="match-card">')
        html_parts.append(f'    <div class="match-title">Instagram: {insta_img.get("filename")} ({insta_img.get("instagram_folder")})</div>')
        html_parts.append('    <div class="comparison">')

        insta_path = insta_img.get('local_path', '')
        insta_b64 = image_to_base64(insta_path)
        html_parts.append('        <div class="image-box">')
        html_parts.append(f'            <img src="{insta_b64}" alt="Instagram">')
        html_parts.append('            <div class="image-label">Instagram Image</div>')
        html_parts.append('        </div>')

        catalog_path = best_match.get('catalog_path', '')
        catalog_b64 = image_to_base64(catalog_path)
        html_parts.append('        <div class="image-box">')
        html_parts.append(f'            <img src="{catalog_b64}" alt="Catalog">')
        html_parts.append(f'            <div class="image-label">Best Match: {best_match.get("catalog_key", "Unknown")}</div>')
        html_parts.append('        </div>')

        html_parts.append('    </div>')

        html_parts.append('    <div class="match-info">')
        html_parts.append(f'        <span class="score-badge {badge_class}">{result}</span>')
        html_parts.append(f'        <span style="margin-left: 10px;">Score: {best_match.get("vision_score", 0)}</span>')
        html_parts.append(f'        <span style="margin-left: 10px;">Date: {best_match.get("catalog_date", "Unknown")}</span>')
        html_parts.append('    </div>')

        if len(top_matches) > 1:
            html_parts.append('    <div class="top-matches">')
            html_parts.append('        <strong>Top 3 Matches:</strong>')
            for j, match in enumerate(top_matches[:3], 1):
                match_path = match.get('catalog_path', '')
                match_b64 = image_to_base64(match_path, max_size=150)
                match_result = match.get('vision_result', 'UNCERTAIN')
                if match_result == 'SAME':
                    match_class = 'score-same'
                elif match_result == 'UNCERTAIN':
                    match_class = 'score-uncertain'
                else:
                    match_class = 'score-different'

                html_parts.append('        <div class="top-match">')
                html_parts.append(f'            <div>#{j}</div>')
                html_parts.append(f'            <img src="{match_b64}" alt="Match {j}">')
                html_parts.append(f'            <div><span class="score-badge {match_class}">{match_result}</span></div>')
                html_parts.append('        </div>')
            html_parts.append('    </div>')

        html_parts.append('</div>')

    html_parts.extend([
        '</body>',
        '</html>',
    ])

    with open(output_file, 'w') as f:
        f.write('\n'.join(html_parts))

    print(f"✓ Report generated: {output_file}")
    print(f"  Open in browser: file://{Path(output_file).absolute()}")


if __name__ == "__main__":
    generate_html_report()
