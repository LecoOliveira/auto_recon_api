import json
import socket
import subprocess
from typing import Dict, List


def run_command(command: List[str], tool_name: str, timeout: int = 120):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout
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
    # command_string = f'gau {subdomain} --config /data/.gau.toml \
    # | httpx -silent -json'
    output_gau = run_command(
        ['gau', subdomain, '--config', '/data/.gau.toml'],
        'gau',
        timeout=120
    )
    if not output_gau:
        return []

    try:
        p = subprocess.run(
            ["httpx", "-silent", "-json"],
            input=output_gau,
            capture_output=True,
            text=True,
            check=True,
            timeout=120
        )
        output = p.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("httpx not found (binary missing in PATH)")
    except subprocess.TimeoutExpired:
        raise RuntimeError("httpx timeout")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"httpx error: {exc.stderr.strip()}")

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
                    'hostname': data['host'],
                    'port': int(data['port']),
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
