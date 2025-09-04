import json
import socket
import subprocess
from http import HTTPStatus
from concurrent.futures import ProcessPoolExecutor, as_completed

from fastapi import FastAPI

from schemas import SubdomainResponse

app = FastAPI()


def run_assetfinder(domain: str):
    result = subprocess.run(
        ['assetfinder', '-subs-only', domain],
        capture_output=True,
        text=True,
        check=False,
    )
    subs_dict = [{'host': sub} for sub in result.stdout.splitlines()]

    return subs_dict


def run_subfinder(domain: str):
    result = subprocess.run(
        ['subfinder', '-d', domain, '-oJ', '-silent'],
        capture_output=True,
        text=True,
        check=False,
    )
    
    subdomain_lists = [
        json.loads(subdomains_json)
        for subdomains_json
        in result.stdout.splitlines()
    ]

    tratado = [{'host': subdomain['host']} for subdomain in subdomain_lists]

    return tratado


def get_ip(lists_subdomains):
    list_ips = []
    for subdomain in lists_subdomains:
        try:
            ip = socket.gethostbyname(subdomain['host'])
            list_ips.append({'ip': ip})
        except Exception as err:
            print(err)
            list_ips.append({'ip': '0.0.0.0'})

    final_list = [
        {**subs, **ips} for subs, ips in zip(lists_subdomains, list_ips)
    ]

    return final_list


@app.post(
    '/subdomains', status_code=HTTPStatus.OK, response_model=SubdomainResponse
)
def get_subdomains(domain: str):
    results = []

    with ProcessPoolExecutor(max_workers=2) as executor:
        future_to_func = {
            executor.submit(
                run_subfinder, domain
            ): 'run_subfinder',
            executor.submit(
                run_assetfinder, domain
            ): 'run_assetfinder',
        }
        for future in as_completed(future_to_func):
            func_name = future_to_func[future]
            try:
                results.append(future.result())
                print(f'{func_name} result:\n\n{future.result()}\n')
            except Exception as exc:
                print(f'{func_name} generated an exception: {exc}')

    list_subs_filtered = {
        tuple(sorted(host.items())) for sublist in results for host in sublist
    }
    all_subdomains = [dict(sub) for sub in list_subs_filtered]
    subdomain_list = get_ip(all_subdomains)

    return {'subdomains': subdomain_list}