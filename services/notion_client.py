from typing import Any

import requests

from utils.helpers import logger

NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(self, token: str, database_id: str, timeout: int = 15):
        self.database_id = database_id
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        })

    def find_page_by_title(self, title: str) -> str | None:
        try:
            resp = self.session.post(
                f"https://api.notion.com/v1/databases/{self.database_id}/query",
                json={
                    "filter": {"property": "Report Name", "title": {"equals": title}},
                    "page_size": 1,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                page_id = results[0]["id"]
                logger.info("Found existing page: %s", page_id)
                return page_id
        except Exception as exc:
            logger.warning("Could not query for existing page: %s", exc)
        return None

    def clear_page(self, page_id: str) -> None:
        try:
            resp = self.session.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            for block in resp.json().get("results", []):
                self.session.delete(
                    f"https://api.notion.com/v1/blocks/{block['id']}",
                    timeout=self.timeout,
                )
            logger.info("Cleared blocks from page %s", page_id)
        except Exception as exc:
            logger.warning("Failed to clear page blocks: %s", exc)

    def append_blocks(self, page_id: str, blocks: list[dict]) -> None:
        self.session.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            json={"children": blocks},
            timeout=self.timeout,
        ).raise_for_status()

    def create_page(self, title: str, blocks: list[dict], author: str | None = None) -> dict[str, Any] | None:
        properties: dict[str, Any] = {
            "Report Name": {"title": [{"text": {"content": title}}]},
        }
        if author:
            properties["Author"] = {"rich_text": [{"text": {"content": author}}]}

        body = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
            "children": blocks,
        }

        try:
            resp = self.session.post(
                "https://api.notion.com/v1/pages",
                json=body,
                timeout=self.timeout,
            )
            if resp.status_code == 429:
                logger.warning("Notion rate-limited")
                return None
            resp.raise_for_status()
            result = resp.json()
            logger.info("Page created: %s", result.get("url", ""))
            return result
        except requests.exceptions.Timeout:
            logger.error("Timeout creating Notion page")
        except requests.exceptions.HTTPError as exc:
            logger.error("Notion HTTP error: %s – %s", exc, exc.response.text if exc.response else "")
        except requests.exceptions.RequestException as exc:
            logger.error("Notion request failed: %s", exc)
        return None

    def _update_properties(self, page_id: str, author: str | None = None) -> None:
        if not author:
            return
        try:
            self.session.patch(
                f"https://api.notion.com/v1/pages/{page_id}",
                json={"properties": {"Author": {"rich_text": [{"text": {"content": author}}]}}},
                timeout=self.timeout,
            ).raise_for_status()
        except Exception as exc:
            logger.warning("Failed to update Author property: %s", exc)

    def create_or_update_report(self, title: str, blocks: list[dict], author: str | None = None) -> dict[str, Any] | None:
        existing_id = self.find_page_by_title(title)

        if existing_id:
            logger.info("Updating existing page: %s", title)
            self.clear_page(existing_id)
            self.append_blocks(existing_id, blocks)
            self._update_properties(existing_id, author=author)
            return {"id": existing_id, "url": f"https://www.notion.so/{existing_id.replace('-', '')}"}

        logger.info("Creating new page: %s", title)
        return self.create_page(title, blocks, author=author)
