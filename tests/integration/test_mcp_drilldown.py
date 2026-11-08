import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from gmac import mcp_server, service
from gmac.config import Config
from gmac.github import GitHubError
from gmac.models import Issue, LocalInfo, PullDetail

pytestmark = pytest.mark.integration

ISSUE = Issue(repo="o/r", number=3, title="t", author="a")
PULL = PullDetail(
    repo="o/r", number=7, title="p", author="a", url="u", draft=False, updated_at=None
)
NAMES = ["repo_local_info", "list_issues", "list_repo_pull_requests", "get_pull_request"]


@pytest.fixture(autouse=True)
def patched(monkeypatch):
    calls = []

    async def local_info(cfg, full_name):
        calls.append(("local", full_name))
        return LocalInfo(remote="git@x:o/r.git")

    async def issues(repo, gh=None):
        calls.append(("issues", repo))
        return [ISSUE]

    async def pulls(repo, gh=None):
        calls.append(("pulls", repo))
        return [PULL]

    async def pull(repo, number, gh=None):
        calls.append(("pull", repo, number))
        return PULL

    monkeypatch.setattr(service, "local_info", local_info)
    monkeypatch.setattr(service, "list_issues", issues)
    monkeypatch.setattr(service, "list_repo_pulls", pulls)
    monkeypatch.setattr(service, "get_pull", pull)
    monkeypatch.setattr(mcp_server.Config, "load", classmethod(lambda cls: Config()))
    return calls


async def test_happy_paths(patched):
    async with Client(mcp_server.server) as c:
        r = await c.call_tool("repo_local_info", {"full_name": "o/r"})
        assert r.data.remote == "git@x:o/r.git"
        r = await c.call_tool("list_issues", {"repo": "o/r"})
        assert r.structured_content["result"][0]["number"] == 3
        r = await c.call_tool("list_repo_pull_requests", {"repo": "o/r"})
        assert r.structured_content["result"][0]["number"] == 7
        r = await c.call_tool("get_pull_request", {"repo": "o/r", "number": 7})
        assert r.structured_content["number"] == 7
    assert patched == [
        ("local", "o/r"),
        ("issues", "o/r"),
        ("pulls", "o/r"),
        ("pull", "o/r", 7),
    ]


@pytest.mark.parametrize(
    "bad", ["../x", "a/b/c", "", "a", "a/..", "./b", "a/b\n", "a b/c", "https://x/y"]
)
@pytest.mark.parametrize(
    "tool,arg",
    [
        ("repo_local_info", "full_name"),
        ("list_issues", "repo"),
        ("list_repo_pull_requests", "repo"),
        ("get_pull_request", "repo"),
    ],
)
async def test_invalid_repo_rejected(patched, tool, arg, bad):
    args = {arg: bad} | ({"number": 1} if tool == "get_pull_request" else {})
    async with Client(mcp_server.server) as c:
        with pytest.raises(ToolError, match="invalid"):
            await c.call_tool(tool, args)
    assert patched == []


@pytest.mark.parametrize("n", [0, -1])
async def test_invalid_number_rejected(patched, n):
    async with Client(mcp_server.server) as c:
        with pytest.raises(ToolError, match="positive integer"):
            await c.call_tool("get_pull_request", {"repo": "o/r", "number": n})
    assert patched == []


async def test_annotations_read_only_and_untrusted_note():
    async with Client(mcp_server.server) as c:
        tools = {t.name: t for t in await c.list_tools()}
    for n in NAMES:
        assert tools[n].annotations.readOnlyHint is True
    assert tools["repo_local_info"].annotations.openWorldHint is False
    for n in NAMES[1:]:
        assert tools[n].annotations.openWorldHint is True
        assert "third-party text" in tools[n].description
        assert "not instructions" in tools[n].description


async def test_service_error_propagates(monkeypatch):
    async def boom(repo, number, gh=None):
        raise GitHubError("404 not found")

    monkeypatch.setattr(service, "get_pull", boom)
    async with Client(mcp_server.server) as c:
        with pytest.raises(ToolError, match="404"):
            await c.call_tool("get_pull_request", {"repo": "o/r", "number": 1})
