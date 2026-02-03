from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from http import HTTPStatus
from typing import List

from fastapi import FastAPI, HTTPException
from schemas import SubdomainResponse, SubdomainSchema
from tasks import get_ip, run_assetfinder, run_discover_urls, run_subfinder

app = FastAPI()


@app.post(
    '/subdomains', status_code=HTTPStatus.OK, response_model=SubdomainResponse
)
def get_subdomains(domain: str):
    results = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_func = {
            executor.submit(run_subfinder, domain): 'run_subfinder',
            executor.submit(run_assetfinder, domain): 'run_assetfinder',
        }
        for future in as_completed(future_to_func, timeout=120):
            func_name = future_to_func[future]
            try:
                response = future.result(timeout=120)
                if response:
                    results.append(response)
                print(f'{func_name} result:\n\n{future.result()}\n')
            except Exception as exc:
                print(f'{func_name} generated an exception: {exc}')
            except TimeoutError:
                print(f'{func_name} take to much time')

    list_subs_filtered = {
        tuple(sorted(host.items())) for sublist in results for host in sublist
    }
    all_subdomains = [dict(sub) for sub in list_subs_filtered]
    subdomain_list = get_ip(all_subdomains)

    if not subdomain_list:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Any subdomains founded'
        )

    return {'subdomains': subdomain_list}


@app.post('/hosts', status_code=HTTPStatus.OK)
def get_hosts(subdomains: List[SubdomainSchema]):
    hosts = []

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(run_discover_urls, sub.host): sub.host
            for sub in subdomains
        }
        try:
            for future in as_completed(futures, timeout=180):
                sub_host = futures[future]
                try:
                    result = future.result(timeout=180)
                    hosts.append({
                        'host': sub_host,
                        'total': len(result),
                        'result': result
                    })
                except TimeoutError:
                    hosts.append({
                        "host": sub_host,
                        "total": 0,
                        "result": [],
                        "error": "timeout"
                    })
                except Exception as exc:
                    hosts.append({
                        "host": sub_host,
                        "total": 0,
                        "result": [],
                        "error": str(exc)
                    })

        except TimeoutError:
            for f, sub_host in futures.items():
                if not f.done():
                    f.cancel()
                    hosts.append({
                        "host": sub_host,
                        "total": 0,
                        "result": [],
                        "error": "timeout"
                    })

    return {'hosts': hosts}
