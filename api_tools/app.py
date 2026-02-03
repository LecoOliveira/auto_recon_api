import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from http import HTTPStatus
from typing import Iterable, List

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from schemas import SubdomainResponse, SubdomainSchema
from settings import get_settings
from tasks import get_ip, run_assetfinder, run_discover_urls, run_subfinder

app = FastAPI()
settings = get_settings()


def _check_internal_token(x_internal_token: str | None):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='forbidden'
        )


def iter_ndjson(items: Iterable[dict]) -> Iterable[bytes]:
    for item in items:
        yield (json.dumps(item, ensure_ascii=False) + '\n').encode('utf-8')


@app.post(
    '/subdomains', status_code=HTTPStatus.OK, response_model=SubdomainResponse
)
def get_subdomains(domain: str):
    results = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_func = {
            executor.submit(run_subfinder, domain): 'run_subfinder',
            executor.submit(run_assetfinder, domain): 'run_assetfinder',
        }
        try:
            for future in as_completed(future_to_func, timeout=120):
                func_name = future_to_func[future]
                try:
                    response = future.result(timeout=120)
                    if response:
                        results.append(response)
                    print(f'{func_name} result:\n\n{response}\n')
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


@app.post('/hosts/stream', status_code=HTTPStatus.OK)
def stream_hosts_urls(
    subdomains: List[SubdomainSchema],
    x_internal_token: str | None = Header(default=None),
):
    _check_internal_token(x_internal_token)

    max_workers = 10

    def generator():
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_discover_urls, sub.host): sub.host
                for sub in subdomains
            }

            try:
                for future in as_completed(futures, timeout=60 * 30):
                    host = futures[future]
                    try:
                        results = future.result(timeout=180)
                        for r in results:
                            payload = {'host': host, **r}
                            yield from iter_ndjson([payload])
                    except TimeoutError:
                        yield from iter_ndjson([{
                            'host': host,
                            'error': 'timeout',
                        }])
                    except Exception as exc:
                        yield from iter_ndjson([{
                            'host': host,
                            'error': str(exc),
                        }])
            except TimeoutError:
                for f, host in futures.items():
                    if not f.done():
                        f.cancel()
                        yield from iter_ndjson([{
                            'host': host,
                            'error': 'timeout',
                        }])

    return StreamingResponse(generator(), media_type='application/x-ndjson')
