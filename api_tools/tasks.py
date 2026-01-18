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
            check=True,
            timeout=120
        )

        return result.stdout.strip()

    except FileNotFoundError:
        raise RuntimeError(f"{tool_name} not found")

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{tool_name} timeout")

    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"{tool_name} error: {exc.stderr.strip()}"
        )


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

    subdomains = []
    for line in output.splitlines():
        try:
            data = json.loads(line)
            if 'host' in data:
                subdomains.append({'host': data['host']})
        except json.JSONDecodeError:
            print(f'Invalid JSON line: {line}')
            continue

    return subdomains


def run_discover_urls(subdomain: str):
    command_string = f'gau {subdomain} --config /data/.gau.toml \
    | httpx -silent -json'
    output = run_command([command_string], 'hosts_discover')
    if not output:
        return []
    hosts = []
    for line in output.splitlines():
        try:
            data = json.loads(line)
            if 'url' in data:
                hosts.append({
                    'url': data['url'],
                    'title': data['title'] if 'title' in data else 'unknown',
                    'ip': data['host'],
                    'port': data['port'],
                    'tech': data['tech'] if 'tech' in data else ['unknown'],
                    'status_code': data['status_code']
                })
        except json.JSONDecodeError:
            print(f'Invalid JSON line: {line}')
            continue

    return hosts


def get_ip(lists_subdomains: List[Dict[str, str]]):
    list_ips = []
    for subdomain in lists_subdomains:
        host = subdomain['host']

        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror:
            ip = '0.0.0.0'

        list_ips.append({**subdomain, 'ip': ip})

    return list_ips
