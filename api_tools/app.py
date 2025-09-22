from concurrent.futures import ProcessPoolExecutor, as_completed
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

    with ProcessPoolExecutor(max_workers=2) as executor:
        future_to_func = {
            executor.submit(run_subfinder, domain): 'run_subfinder',
            executor.submit(run_assetfinder, domain): 'run_assetfinder',
        }
        for future in as_completed(future_to_func, timeout=120):
            func_name = future_to_func[future]
            try:
                response = future.result(timeout=90)
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
    try:
        with ProcessPoolExecutor() as executor:
            futures = {
                executor.submit(run_discover_urls, sub.host): sub.host
                for sub in subdomains
            }
            for future in as_completed(futures, timeout=120):
                sub_host = futures[future]
                result = future.result()
                hosts.append(
                    {'host': sub_host,'total':len(result), 'result': result}
                )

    except Exception as exc:
        raise HTTPException(
            detail=f'Error {exc}',
            status_code=HTTPStatus.CONFLICT
        )

    return {'hosts': hosts}
