import json
import time

import jwt
import httpx
import asyncio
import contextlib
import threading

from ...enums.apns import ApnsSenderType

_voip = "voip"
_background = "background"
_mutable = "alert"
_max_list_size = 1000

class ResponseCompat:
    """A thin wrapper to mimic hyper's response interface used by callers."""

    def __init__(self, response: httpx.Response):
        self._response = response

    @property
    def status(self):
        return self._response.status_code

    def read(self):
        # Return raw bytes similar to hyper's .read()
        return self._response.content


class ApnsNotification:
    def __init__(self, apns=None):
        if apns is None:
            apns = {}
        with open(apns["APNS_AUTH_KEY"]) as f:
            self.secret_key = f.read()

        self.team_id = apns["TEAM_ID"]
        self.algorithm = apns["ALGORITHM"]
        self.apns_key_id = apns["APNS_KEY_ID"]
        self.bundle_id = apns["BUNDLE_ID"]
        self.ios_http_url = apns["IOS_HTTP_URL"]
        self.ios_http_sandbox_url = apns.get("IOS_HTTP_SANDBOX_URL")
        self.max_list_size = apns.get("MAX_LIST_SIZE", _max_list_size)

    def _get_base_url(self, use_sandbox=False):
        base = self.ios_http_sandbox_url if use_sandbox else self.ios_http_url
        if not isinstance(base, str):
            if use_sandbox:
                raise RuntimeError("IOS_HTTP_SANDBOX_URL is not configured")
            raise RuntimeError("IOS_HTTP_URL must be a string host or URL")
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"https://{base}"
        return base

    @staticmethod
    def get_request_headers(self, push_type, expiration, topic_suffix):
        token = jwt.encode(
            {"iss": self.team_id, "iat": time.time()},
            self.secret_key,
            algorithm=self.algorithm,
            headers={
                "alg": self.algorithm,
                "kid": self.apns_key_id,
            },
        )
        return {
            "apns-expiration": expiration,
            "apns-priority": "10",
            "apns-topic": self.bundle_id + topic_suffix,
            "authorization": "bearer {0}".format(token),
            "apns-push-type": push_type,
            "content-type": "application/json",
        }

    @staticmethod
    def get_path(registration_id):
        return "/3/device/{0}".format(registration_id)

    def _send_request(self, path, payload, headers):
        base_url = self._get_base_url()
        with httpx.Client(http2=True, base_url=base_url, timeout=10.0) as client:
            resp = client.post(path, content=payload, headers=headers)
            if (
                    resp.status_code in [400, 413]
                    and self.ios_http_sandbox_url
                    and self.ios_http_url != self.ios_http_sandbox_url
            ):
                sandbox_base_url = self._get_base_url(use_sandbox=True)
                with httpx.Client(
                        http2=True, base_url=sandbox_base_url, timeout=10.0
                ) as sandbox_client:
                    resp = sandbox_client.post(path, content=payload, headers=headers)
            return ResponseCompat(resp)

    async def _send_request_async(self, client, path, payload, headers):
        resp = await client.post(path, content=payload, headers=headers)
        if (
                resp.status_code in [400, 413]
                and self.ios_http_sandbox_url
                and self.ios_http_url != self.ios_http_sandbox_url
        ):
            sandbox_base_url = self._get_base_url(use_sandbox=True)
            async with httpx.AsyncClient(
                    http2=True, base_url=sandbox_base_url, timeout=10.0
            ) as sandbox_client:
                resp = await sandbox_client.post(path, content=payload, headers=headers)
        return resp

    _PUSH_TYPE_CONFIG = {
        "voip": (_voip, ".voip", 30),
        "background": (_background, "", 30),
        "alert": (_mutable, "", 30 * 24 * 60 * 60),
    }

    _PAYLOAD_BUILDERS = {
        "voip": lambda msg, title, mutable: {"aps": {"payload": msg}},
        "background": lambda msg, title, mutable: {
            "aps": {"content-available": 1},
            "title": title or "Background Message",
            "body": msg,
        },
        "alert": lambda msg, title, mutable: {
            "aps": {
                **({"mutable-content": 1} if mutable else {}),
                "alert": {
                    "title": title or "You have a new message",
                    "body": msg,
                },
            }
        },
    }

    @staticmethod
    def _build_payload(push_type_key, message_body, title=None, mutable_content=True):
        """Build the payload based on push type."""
        builder = ApnsNotification._PAYLOAD_BUILDERS.get(push_type_key)
        if not builder:
            raise ValueError(f"Unknown push type: {push_type_key}")
        payload_data = builder(message_body, title, mutable_content)
        return json.dumps(payload_data).encode("utf-8")

    def _send_notification(
            self,
            push_type_key,
            message_body,
            registration_id,
            title=None,
            mutable_content=True,
            ttl=None,
    ):
        """Unified method to send a single push notification."""
        try:
            push_type, topic_suffix, default_ttl = self._PUSH_TYPE_CONFIG[push_type_key]
            ttl = ttl if ttl is not None else default_ttl

            payload = self._build_payload(push_type_key, message_body, title, mutable_content)
            request_headers = self.get_request_headers(
                self, push_type, str(int(time.time()) + ttl), topic_suffix
            )
            path = self.get_path(registration_id)
            return self._send_request(path, payload, request_headers)
        except Exception as e:
            raise RuntimeError(f"Exception occurred in _send_notification ({push_type_key}): {e}")

    def _send_notification_list(
            self,
            push_type_key,
            message_body,
            registration_ids,
            force_exit_on=None,
            title=None,
            mutable_content=True,
            ttl=None,
    ):
        """Unified method to send push notifications to multiple devices."""
        try:
            push_type, topic_suffix, default_ttl = self._PUSH_TYPE_CONFIG[push_type_key]
            ttl = ttl if ttl is not None else default_ttl

            payload = self._build_payload(push_type_key, message_body, title, mutable_content)
            request_headers = self.get_request_headers(
                self, push_type, str(int(time.time()) + ttl), topic_suffix
            )
            return self.send_to_apns_bulk(
                force_exit_on, payload, registration_ids, request_headers
            )
        except Exception as e:
            raise RuntimeError(f"Exception occurred in _send_notification_list ({push_type_key}): {e}")

    def ios_push_notification_voip(self, message_body, registration_id, ttl=30):
        return self._send_notification("voip", message_body, registration_id, ttl=ttl)

    def ios_push_notification_background(
            self, message_body, registration_id, title="Background Message", ttl=30
    ):
        return self._send_notification("background", message_body, registration_id, title=title, ttl=ttl)

    def ios_push_notification_alert(
            self,
            message_body,
            registration_id,
            title="You have a new message",
            mutable_content=True,
            ttl=30 * 24 * 60 * 60,
    ):
        return self._send_notification(
            "alert", message_body, registration_id, title=title, mutable_content=mutable_content, ttl=ttl
        )

    def ios_push_notification_voip_list(
            self, message_body, registration_ids, force_exit_on=None, ttl=30
    ):
        return self._send_notification_list("voip", message_body, registration_ids, force_exit_on, ttl=ttl)

    def ios_push_notification_background_list(
            self,
            message_body,
            registration_ids,
            force_exit_on=None,
            title="Background Message",
            ttl=30,
    ):
        return self._send_notification_list(
            "background", message_body, registration_ids, force_exit_on, title=title, ttl=ttl
        )

    def ios_push_notification_alert_list(
            self,
            message_body,
            registration_ids,
            force_exit_on=None,
            title="You have a new message",
            mutable_content=True,
            ttl=30 * 24 * 60 * 60,
    ):
        return self._send_notification_list(
            "alert", message_body, registration_ids, force_exit_on, title=title, mutable_content=mutable_content, ttl=ttl
        )

    async def _send_to_apns_bulk_async(
            self,
            force_exit_on,
            payload,
            registration_ids,
            request_headers,
            concurrency: int = 100,
    ):
        base_url = self._get_base_url()
        result = {"responses": []}
        exit_flag = asyncio.Event()
        sem = asyncio.Semaphore(concurrency)

        async def _post_one(http_client: httpx.AsyncClient, reg_id: str):
            if exit_flag.is_set():
                return None
            path = self.get_path(reg_id)
            async with sem:
                if exit_flag.is_set():
                    return None
                try:
                    resp = await self._send_request_async(
                        http_client, path, payload, request_headers
                    )
                    status = resp.status_code
                    res_msg = resp.content.decode("utf-8")
                except Exception as e:
                    status = 0
                    res_msg = f"request_error: {e}"
                response_entry = {reg_id: {"status": status, "message": res_msg, "test": "apns"}}
                if force_exit_on and status in force_exit_on:
                    exit_flag.set()
                return response_entry

        async with httpx.AsyncClient(http2=True, base_url=base_url, timeout=10.0) as client:
            tasks = [asyncio.create_task(_post_one(client, reg_id)) for reg_id in registration_ids]

            try:
                for coro in asyncio.as_completed(tasks):
                    entry = await coro
                    if entry:
                        result["responses"].append(entry)
                    if exit_flag.is_set():
                        # Cancel all pending tasks
                        for t in tasks:
                            if not t.done():
                                t.cancel()
                        result["exit"] = True
                        break
            finally:
                for t in tasks:
                    with contextlib.suppress(asyncio.CancelledError):
                        if not t.done():
                            await t

        return result

    def send_to_apns_bulk(
            self, force_exit_on, payload, registration_ids, request_headers
    ):
        coro = self._send_to_apns_bulk_async(
            force_exit_on, payload, registration_ids, request_headers
        )
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        else:
            result_container = {}

            def _runner():
                result_container["value"] = asyncio.run(coro)

            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join()
            return result_container.get("value")

    def send(self, payload=None):
        send_mode = payload.get("send_mode")
        force_exit_on = payload.get("force_exit_on")
        device_token = payload.get("device_token")
        device_tokens = payload.get("device_tokens")
        notification = payload.get("notification").get("data")
        immutable_notification = payload.get("notification").get("message_body")
        title = payload.get("notification").get("title")
        ttl = payload.get("notification").get("ttl", 30 * 24 * 60 * 60)

        if payload is None:
            raise RuntimeError("Message must be provided.")

        if send_mode is None:
            raise RuntimeError("send_mode must be provided.")

        if device_token is None and device_tokens is None:
            raise RuntimeError("device token(s) must be provided.")

        if device_token:
            if send_mode == ApnsSenderType.VOIP:
                return self.ios_push_notification_voip(
                    notification, device_token, ttl=ttl
                )
            elif send_mode == ApnsSenderType.BACKGROUND:
                return self.ios_push_notification_background(
                    notification, device_token, title, ttl=ttl
                )
            elif send_mode == ApnsSenderType.MUTABLE:
                return self.ios_push_notification_alert(
                    notification, device_token, title, ttl=ttl
                )
            elif send_mode == ApnsSenderType.IMMUTABLE:
                return self.ios_push_notification_alert(
                    immutable_notification,
                    device_token,
                    title,
                    mutable_content=False,
                    ttl=ttl,
                )
        elif device_tokens:
            if len(device_tokens) > self.max_list_size:
                raise RuntimeError(
                    f"Device tokens list size exceeds maximum of {self.max_list_size}."
                )
            if send_mode == ApnsSenderType.VOIP:
                return self.ios_push_notification_voip_list(
                    notification,
                    device_tokens,
                    force_exit_on=force_exit_on,
                    ttl=ttl,
                )
            elif send_mode == ApnsSenderType.BACKGROUND:
                return self.ios_push_notification_background_list(
                    notification,
                    device_tokens,
                    force_exit_on=force_exit_on,
                    title=title,
                    ttl=ttl,
                )
            elif send_mode == ApnsSenderType.MUTABLE:
                return self.ios_push_notification_alert_list(
                    notification,
                    device_tokens,
                    force_exit_on=force_exit_on,
                    title=title,
                    ttl=ttl,
                )
            elif send_mode == ApnsSenderType.IMMUTABLE:
                return self.ios_push_notification_alert_list(
                    immutable_notification,
                    device_tokens,
                    force_exit_on=force_exit_on,
                    title=title,
                    mutable_content=False,
                    ttl=ttl,
                )
        return None

    @staticmethod
    def calculate_payload_size(payload=None, max_list_size=_max_list_size):
        """Return APNS JSON payload size details without sending any request."""
        max_payload_size_bytes = 4096

        if payload is None:
            raise RuntimeError("Message must be provided.")

        send_mode = payload.get("send_mode")
        device_token = payload.get("device_token")
        device_tokens = payload.get("device_tokens")

        notification_payload = payload.get("notification") or {}
        notification = notification_payload.get("data")
        immutable_notification = notification_payload.get("message_body")
        title = notification_payload.get("title")

        if send_mode is None:
            raise RuntimeError("send_mode must be provided.")

        if device_token is None and device_tokens is None:
            raise RuntimeError("device token(s) must be provided.")

        if device_tokens and len(device_tokens) > max_list_size:
            raise RuntimeError(
                f"Device tokens list size exceeds maximum of {max_list_size}."
            )

        if send_mode == ApnsSenderType.VOIP:
            push_type_key = "voip"
            message_body = notification
            mutable_content = True
        elif send_mode == ApnsSenderType.BACKGROUND:
            push_type_key = "background"
            message_body = notification
            mutable_content = True
        elif send_mode == ApnsSenderType.MUTABLE:
            push_type_key = "alert"
            message_body = notification
            mutable_content = True
        elif send_mode == ApnsSenderType.IMMUTABLE:
            push_type_key = "alert"
            message_body = immutable_notification
            mutable_content = False
        else:
            raise RuntimeError("Unsupported send_mode provided.")

        payload_bytes = ApnsNotification._build_payload(
            push_type_key,
            message_body,
            title=title,
            mutable_content=mutable_content,
        )
        payload_size_bytes = len(payload_bytes)

        target_count = 1 if device_token else len(device_tokens)
        total_payload_size_bytes = payload_size_bytes * target_count

        return {
            "send_mode": send_mode,
            "apns_max_payload_size_bytes": max_payload_size_bytes,
            "payload_size_bytes": payload_size_bytes,
            "total_payload_size_bytes": total_payload_size_bytes,
            "target_count": target_count,
            "is_within_limit": payload_size_bytes <= max_payload_size_bytes,
            "overflow_bytes": max(0, payload_size_bytes - max_payload_size_bytes),
        }
