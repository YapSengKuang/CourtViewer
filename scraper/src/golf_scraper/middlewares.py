import logging

from scrapy.http import TextResponse

logger = logging.getLogger(__name__)


class FixtureResponseMiddleware:
    """Answer requests that carry a fixture body. Never opens a connection.

    Real spiders leave meta["fixture_body"] unset, so this middleware ignores
    them and the normal downloader runs.
    """

    def process_request(self, request):
        body = request.meta.get("fixture_body")
        if body is None:
            return None
        if isinstance(body, str):
            body = body.encode("utf-8")
        logger.info("serving local fixture for %s", request.url)
        return TextResponse(
            url=request.url,
            body=body,
            encoding="utf-8",
            request=request,
        )
