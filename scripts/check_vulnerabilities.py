#!/usr/bin/env python3
"""Check vulnerability report for critical issues."""
import json
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: check_vulnerabilities.py <vulnerability-report.json>")
        sys.exit(1)
    
    report_file = sys.argv[1]
    try:
        with open(report_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Report file not found: {report_file}")
        sys.exit(0)
    except json.JSONDecodeError:
        print(f"Invalid JSON in {report_file}")
        sys.exit(0)
    
    vulnerabilities = data.get('vulnerabilities', [])
    
    # Check for critical vulnerabilities
    critical = [
        v for v in vulnerabilities
        if v.get('aliases', [{}])[0].get('severity', '').upper() == 'CRITICAL'
    ]
    
    if critical:
        print('Critical vulnerabilities found:')
        for v in critical:
            print(f"  - {v.get('id')}: {v.get('summary', '')}")
        sys.exit(1)
    
    # Check for medium/high vulnerabilities (non-blocking)
    medium = [
        v for v in vulnerabilities
        if v.get('aliases', [{}])[0].get('severity', '').upper() in ['MEDIUM', 'HIGH']
    ]
    
    if medium:
        print(f'Found {len(medium)} medium/high severity vulnerabilities (non-blocking):')
        for v in medium[:5]:  # Show first 5
            print(f"  - {v.get('id')}: {v.get('summary', '')}")
    
    sys.exit(0)

if __name__ == '__main__':
    main()

