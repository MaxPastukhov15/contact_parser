import random


class RandomUserAgentMiddleware:
    def __init__(self, user_agents: list[str]):
        self._user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        user_agents = crawler.settings.getlist("USER_AGENT_LIST")
        if not user_agents:
            user_agents = [crawler.settings.get("USER_AGENT", "")]
        return cls(user_agents)

    def process_request(self, request, spider):  # noqa: ARG002
        ua = random.choice(self._user_agents)
        request.headers["User-Agent"] = ua
