# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import logging
from typing import Optional

import httpx
from pydantic import ValidationError

from ik_apis import IKApi
from models.response.mail import MailBoxResponse, MailFolderResponse, ListEmailsResponse, GetEmailResponse

logger = logging.getLogger(__name__)


async def list_mailboxes(ik_api: IKApi) -> MailBoxResponse:
    """List available mailboxes for the authenticated user."""
    url = "https://mail.infomaniak.com/api/mailbox"
    headers = {
        **ik_api.security_headers, "Content-Type": "application/json",
        }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return MailBoxResponse.model_validate_json(response.text, strict=False)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error in mail request: {e.response.text}")
            raise ValueError(f"Failed to list mailboxes: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise ValueError(f"Request failed: {e}")


async def list_mailboxes_folders(ik_api: IKApi, mailbox_id: str) -> MailFolderResponse:
    """
    Fetches a list of mail folders for the specified mailbox using the given API instance.

    This function interacts with an external API to retrieve mail folders associated with
    a specified mailbox. It uses asynchronous HTTP requests to communicate with the API.
    The function handles potential errors during the request and logs detailed error
    messages in case of failures.

    Args:
        ik_api: An instance of IKApi providing access to security headers required for
            authorization.
        mailbox_id: The unique identifier of the mailbox for which to retrieve folders.

    Returns:
        MailFolderResponse: An object containing the list of mail folders and additional
            result information, such as error status, in case of failure.
    """
    url = f"https://mail.infomaniak.com/api/mail/{mailbox_id}/folder"
    headers = {
        **ik_api.security_headers, "Content-Type": "application/json",
        }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return MailFolderResponse.model_validate_json(response.text, strict=False)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error in mail request: {e.response.text}")
            return MailFolderResponse(data=[], result="error")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            return MailFolderResponse(data=[], result="error")


async def list_mails(
        ik_api: IKApi,
        mailbox_id: str,
        folder_id: str,
        *,
        from_date: Optional[datetime.datetime] = None,
        to_date: Optional[datetime.datetime] = None,
        kw_search: Optional[str] = None,
        from_search: Optional[str] = None,
        to_search: Optional[str] = None,
        page: int = 1,
        limit: int = 10
        ) -> ListEmailsResponse:
    """List emails in a specific folder with optional filtering."""
    url = f"https://mail.infomaniak.com/api/mail/{mailbox_id}/folder/{folder_id}/message"
    headers = {
        **ik_api.security_headers, "Content-Type": "application/json",
        }

    params = {
        "offset": (page - 1) * limit, "limit": limit, "thread": "on",
        }

    # Only add parameters that have values
    if kw_search:
        params["scontains"] = kw_search
    if from_search:
        params["sfrom"] = from_search
    if to_search:
        params["sto"] = to_search
    if from_date:
        params["sfromdate"] = from_date.strftime("%Y-%m-%d %H:%M:%S")
    if to_date:
        params["stodate"] = to_date.strftime("%Y-%m-%d %H:%M:%S")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return ListEmailsResponse.model_validate_json(response.text, strict=False)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list emails: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Failed to list emails: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise ValueError(f"Request failed: {e}")


def remove_encrypted_data(content: str) -> str:
    """
    Remove all content between 'BEGIN ENCRYPTED DATA' and 'END ENCRYPTED DATA' markers,
    including the markers themselves.

    Args:
        content: The input string that may contain encrypted data sections

    Returns:
        The string with all encrypted data sections removed
    """
    parts: list[str] = []
    first, *rest = content.split("BEGIN ENCRYPTED DATA")
    parts.append(first)

    for chunk in rest:
        try:
            # Split only once – maximum 2 parts
            _, after_close = chunk.split("END ENCRYPTED DATA", 1)
            parts.append(after_close)
        except ValueError:
            # If 'END ENCRYPTED DATA' is not found, skip this chunk
            logger.warning("Found 'BEGIN ENCRYPTED DATA' without matching 'END ENCRYPTED DATA'")
            continue

    return "".join(parts)


# async def get_email(
#         ik_api: IKApi,
#         mailbox_id: str,
#         folder_id: str,
#         msg_id: str
#         ) -> str:
#     """
#     Get email content in plain text format.

#     Args:
#         ik_api: Object for accessing API security headers
#         mailbox_id: The ID of the mailbox to fetch the email from
#         folder_id: The ID of the folder containing the email
#         msg_id: The message ID of the email

#     Returns:
#         The email content in plain text format

#     Raises:
#         ValueError: If the API call fails or the email cannot be retrieved
#     """
#     url = f"https://mail.infomaniak.com/api/mail/{mailbox_id}/folder/{folder_id}/message/{msg_id}"
#     headers = {
#         **ik_api.security_headers, "Content-Type": "application/json",
#         }
#     params = {"prefered_format": "plain"}

#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.get(url, headers=headers, params=params)
#             response.raise_for_status()

#             email_response = GetEmailResponse.model_validate_json(response.text)
#             if not email_response.data.body:
#                 raise ValueError(f"Email {msg_id} has no body content")

#             return email_response.data.body.value

#         except httpx.HTTPStatusError as e:
#             logger.error(f"Failed to get email: {e.response.status_code} - {e.response.text}")
#             raise ValueError(f"Failed to get email: {e.response.status_code}")
#         except httpx.RequestError as e:
#             logger.error(f"Request error: {e}")
#             raise ValueError(f"Request failed: {e}")
#         except ValidationError as e:
#             logger.error(f"Email response validation failed: {e}")
#             raise ValueError(f"Response validation failed: {e}")


# async def async_get_mail(
#         ik_api: IKApi,
#         mailbox_id: str,
#         folder_id: str,
#         msg_id: str
#         ) -> GetEmailResponse:
#     """
#     Asynchronously fetches an email's complete data using the Infomaniak API.

#     Args:
#         ik_api: Object for accessing API security headers
#         mailbox_id: The ID of the mailbox to fetch the email from
#         folder_id: The ID of the folder containing the email
#         msg_id: The message ID of the email

#     Returns:
#         Complete email response with metadata and content

#     Raises:
#         ValueError: If the API call fails or the email cannot be retrieved
#     """
#     url = f"https://mail.infomaniak.com/api/mail/{mailbox_id}/folder/{folder_id}/message/{msg_id}"
#     headers = {
#         **ik_api.security_headers, "Content-Type": "application/json",
#         }
#     params = {"prefered_format": "plain"}

#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.get(url, headers=headers, params=params)
#             response.raise_for_status()

#             email_data = response.json()
#             if email_data["data"]["msg_id"] is None:
#                 email_data["data"]["msg_id"] = msg_id

#             mail = GetEmailResponse.model_validate(email_data)
#             if mail.data.body:
#                 mail.data.body.value = remove_encrypted_data(mail.data.body.value)

#             return mail

#         except httpx.HTTPStatusError as e:
#             logger.error(f"Failed to get email: {e.response.status_code} - {e.response.text}")
#             raise ValueError(f"Failed to get email: {e.response.status_code}")
#         except httpx.RequestError as e:
#             logger.error(f"Request error: {e}")
#             raise ValueError(f"Request failed: {e}")
#         except ValidationError as e:
#             logger.error(f"Email response validation failed: {e}")
#             raise ValueError(f"Response validation failed: {e}")

async def get_mail_body(
        ik_api: IKApi,
        mailbox_id: str,
        folder_id: str,
        msg_id: str
        ) -> str:
    """
    Get email content in plain text format.

    Args:
        ik_api: Object for accessing API security headers
        mailbox_id: The ID of the mailbox to fetch the email from
        folder_id: The ID of the folder containing the email
        msg_id: The message ID of the email

    Returns:
        The email content in plain text format

    Raises:
        ValueError: If the API call fails or the email cannot be retrieved
    """
    url = f"https://mail.infomaniak.com/api/mail/{mailbox_id}/folder/{folder_id}/message/{msg_id}"
    headers = {
        **ik_api.security_headers, "Content-Type": "application/json",
        }
    params = {"prefered_format": "plain"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()

            email_response = GetEmailResponse.model_validate_json(response.text)
            if not email_response.data.body:
                raise ValueError(f"Email {msg_id} has no body content")

            return email_response.data.body.value

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get email: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Failed to get email: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise ValueError(f"Request failed: {e}")
        except ValidationError as e:
            logger.error(f"Email response validation failed: {e}")
            raise ValueError(f"Response validation failed: {e}")


async def get_mail_metadata(
        ik_api: IKApi,
        mailbox_id: str,
        folder_id: str,
        msg_id: str
        ) -> GetEmailResponse:
    """
    Asynchronously fetches an email's complete data using the Infomaniak API.

    Args:
        ik_api: Object for accessing API security headers
        mailbox_id: The ID of the mailbox to fetch the email from
        folder_id: The ID of the folder containing the email
        msg_id: The message ID of the email

    Returns:
        Complete email response with metadata and content

    Raises:
        ValueError: If the API call fails or the email cannot be retrieved
    """
    url = f"https://mail.infomaniak.com/api/mail/{mailbox_id}/folder/{folder_id}/message/{msg_id}"
    headers = {
        **ik_api.security_headers, "Content-Type": "application/json",
        }
    params = {"prefered_format": "plain"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()

            email_data = response.json()
            if email_data["data"]["msg_id"] is None:
                email_data["data"]["msg_id"] = msg_id

            mail = GetEmailResponse.model_validate(email_data)
            if mail.data.body:
                mail.data.body.value = remove_encrypted_data(mail.data.body.value)

            return mail

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get email: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Failed to get email: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise ValueError(f"Request failed: {e}")
        except ValidationError as e:
            logger.error(f"Email response validation failed: {e}")
            raise ValueError(f"Response validation failed: {e}")


async def move_mails(
        ik_api: IKApi,
        mailbox_id: str,
        dest_folder_id: str,
        msg_uids: list[str]
        ):
    url = f"https://mail.infomaniak.com/api/mail/{mailbox_id}/message/move"
    headers = {
        **ik_api.security_headers, "Content-Type": "application/json",
        }
    params = {"prefered_format": "plain"}
    data = {"uids":msg_uids,"to":dest_folder_id,"move_reactions":True}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, params=params, json=data)
            response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to move emails: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Failed to move emails: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise ValueError(f"Request failed: {e}")
        except ValidationError as e:
            logger.error(f"Email response validation failed: {e}")
            raise ValueError(f"Response validation failed: {e}")
