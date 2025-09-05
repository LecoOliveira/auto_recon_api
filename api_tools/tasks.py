import json
import socket
import subprocess
from typing import Dict, List

def run_command(command: List[str], tool_name: str):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=60
        )
        if result.returncode != 0:
            print(f'{tool_name} returned an error: {result.stderr.strip()}')

        return result.stdout.strip()

    except FileNotFoundError:
        print(f'{tool_name} not founded')
    except subprocess.TimeoutExpired:
        print(f'{tool_name} took a long time and was interrupted')

        return ''


def run_assetfinder(domain: str):
    output = run_command(['assetfinder', '-subs-only', domain], 'assetfinder')

    if not output:
        return []

    subdomains = [
        {'host': sub.strip()} for sub in output.splitlines() if sub.strip()
    ]

    return subdomains


def run_subfinder(domain: str):
    output = run_command(
        ['subfinder', '-d', domain, '-oJ', '-silent'], 'subfinder'
    )
    if not output:
        return []

    subdomains= []
    for line in output.splitlines():
        try:
            data = json.loads(line)
            if 'host' in data:
                subdomains.append({'host': data['host']})
        except json.JSONDecodeError:
            print(f'Invalid JSON line: {line}')
            continue

    return subdomains


def get_ip(lists_subdomains: List[Dict[str, str]]):
    list_ips = []
    for subdomain in lists_subdomains:
        host = subdomain['host']

        try:
            ip = socket.gethostbyname(host)
        except Exception as err:
            ip = '0.0.0.0'

        list_ips.append({**subdomain, 'ip': ip})

    return list_ips
