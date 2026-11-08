import httpx
import pytest

from conftest import PR, REPO
from gmac.github import GitHub, GitHubError
from gmac.models import Source

pytestmark = pytest.mark.integration


def client(handler, token="fake"):
    return GitHub(token, transport=httpx.MockTransport(handler))


async def test_pagination_walks_pages_and_respects_limit():
    pages = []

    def h(req):
        page = int(req.url.params["page"])
        pages.append(page)
        n = 100 if page < 3 else 20
        return httpx.Response(200, json=[{**REPO, "full_name": f"o/r{page}-{i}"} for i in range(n)])

    async with client(h) as gh:
        assert len(await gh.repos(Source(name="u"), limit=500)) == 220
        assert pages == [1, 2, 3]
        pages.clear()
        assert len(await gh.repos(Source(name="u"), limit=150)) == 150
        assert pages == [1, 2]


async def test_search_pagination_unwraps_items():
    def h(req):
        return (
            httpx.Response(200, json={"items": [PR] * 100})
            if req.url.params["page"] == "1"
            else httpx.Response(200, json={"items": [PR] * 5})
        )

    async with client(h) as gh:
        assert len(await gh.pulls(Source(name="o", kind="org"), limit=500)) == 105


async def test_paths_and_query_by_kind():
    seen = []

    def h(req):
        seen.append((req.url.path, req.url.params.get("q")))
        return httpx.Response(200, json={"items": []} if "search" in req.url.path else [])

    async with client(h) as gh:
        await gh.repos(Source(name="org1", kind="org"))
        await gh.repos(Source(name="me"))
        await gh.pulls(Source(name="org1", kind="org"))
        await gh.pulls(Source(name="me"))
    assert seen[0][0] == "/orgs/org1/repos" and seen[1][0] == "/users/me/repos"
    assert "org:org1" in seen[2][1] and "user:me" in seen[3][1]
    assert "is:pr is:open" in seen[2][1]


async def test_auth_header_only_with_token():
    got = []

    def h(req):
        got.append(req.headers.get("authorization"))
        return httpx.Response(200, json=[])

    async with client(h, token="fake") as gh:
        await gh.repos(Source(name="u"))
    async with client(h, token=None) as gh:
        await gh.repos(Source(name="u"))
    assert got == ["Bearer fake", None]


@pytest.mark.parametrize(
    ("status", "body", "expect"),
    [
        (403, {"message": "API rate limit exceeded"}, "rate limit"),
        (401, {"message": "Bad credentials"}, "Bad credentials"),
        (404, {}, "404"),
    ],
)
async def test_error_statuses(status, body, expect):
    async with client(lambda r: httpx.Response(status, json=body)) as gh:
        with pytest.raises(GitHubError, match=expect):
            await gh.repos(Source(name="u"))


async def test_non_json_error_body_is_still_a_github_error():
    async with client(lambda r: httpx.Response(502, text="<html>Bad Gateway</html>")) as gh:
        with pytest.raises(GitHubError, match="502.*Bad Gateway"):
            await gh.repos(Source(name="u"))


async def test_missing_optional_fields_tolerated():
    pr = {k: v for k, v in PR.items() if k != "draft"}
    async with client(lambda r: httpx.Response(200, json={"items": [pr]})) as gh:
        assert (await gh.pulls(Source(name="o")))[0].draft is False
