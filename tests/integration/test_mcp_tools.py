import pytest
from fastmcp import Client

from gmac import mcp_server
from gmac.config import Config
from gmac.models import PullRequest, Repo, Source

pytestmark = pytest.mark.integration


@pytest.fixture
def patched(monkeypatch):
    calls = []

    async def repos(cfg, source=None, archived=False):
        calls.append(("repos", source, archived))
        return [Repo(full_name="o/r", owner="o", stars=5)]

    async def pulls(cfg, source=None):
        calls.append(("prs", source))
        return [PullRequest(repo="o/r", number=1, title="t", author="a")]

    monkeypatch.setattr(
        mcp_server.Config,
        "load",
        classmethod(lambda cls, path=None: Config(sources=[Source(name="o", kind="org")])),
    )
    monkeypatch.setattr(mcp_server.service, "list_repos", repos)
    monkeypatch.setattr(mcp_server.service, "list_pulls", pulls)
    return calls


async def test_tools_return_structured_data_and_pass_args(patched):
    async with Client(mcp_server.server) as c:
        src = await c.call_tool("list_sources", {})
        repos = await c.call_tool("list_repos", {"source": "o", "include_archived": True})
        prs = await c.call_tool("list_pull_requests", {})
    assert src.data == [{"name": "o", "kind": "org", "provider": "github"}]
    assert repos.structured_content["result"][0]["full_name"] == "o/r"
    assert prs.structured_content["result"][0]["number"] == 1
    assert patched == [("repos", "o", True), ("prs", None)]


async def test_tool_error_reaches_client_as_error(monkeypatch):
    async def boom(*a, **k):
        raise ValueError("no sources configured")

    monkeypatch.setattr(mcp_server.service, "list_repos", boom)
    monkeypatch.setattr(mcp_server.Config, "load", classmethod(lambda cls, path=None: Config()))
    async with Client(mcp_server.server) as c:
        with pytest.raises(Exception, match="no sources configured"):
            await c.call_tool("list_repos", {})
