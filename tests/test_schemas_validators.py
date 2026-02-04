from __future__ import annotations

from auto_recon_api.schemas import FilterDomain, UrlListFilters


def test_filter_domain_strip_q():
    f = FilterDomain(q='  hello  ')
    assert f.q == 'hello'

    f2 = FilterDomain(q='   ')
    assert f2.q is None


def test_url_list_filters_normalize_ext_and_host_and_q():
    f = UrlListFilters(ext='.PDF ', host='  EXAMPLE.COM  ', q='  /p1  ')
    assert f.ext == 'pdf'
    assert f.host == 'example.com'
    assert f.q == '/p1'
