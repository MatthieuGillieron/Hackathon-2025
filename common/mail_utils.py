# -*- coding: utf-8 -*-
import asyncio
import logging
import re
from typing import List, Optional

from ik_apis import IKApi
from ik_apis.mail import GetEmailResponse, get_mail_metadata


def clean_text(text):
    # Replace multiple consecutive occurrences of '\r\n' with a single one
    return re.sub(r"(\r\n){2,}", "\r\n", text)


def starts_with_strings(line, prefixes):
    return any([line.startswith(prefix) for prefix in prefixes])


def remove_lines_starting_with_prefixes(input_text, prefixes, sep="\n"):
    """
    Removes all lines from the input text that start with given prefixes
    """
    # Split the text into lines
    lines = input_text.split(sep)

    # Filter out lines that do not start with '>'
    filtered_lines = [line for line in lines if not starts_with_strings(line, prefixes)]

    # Join the remaining lines back into a single string
    cleaned_text = sep.join(filtered_lines)

    return cleaned_text


async def get_mail(
    context_message_uid: List[str], ik_api: IKApi, mailbox_uuid: str
) -> List[Optional[GetEmailResponse]]:

    async def fetch_mail(msg_id: str, folder_id: str) -> Optional[GetEmailResponse]:
        try:
            return await get_mail_metadata(ik_api, mailbox_uuid, folder_id, msg_id)
        except ValueError as e:
            logging.error(f"Failed to fetch email for msg_id {msg_id}: {e}")
            return None

    tasks = [fetch_mail(*msg_uid.split("@")) for msg_uid in context_message_uid if "@" in msg_uid]
    return await asyncio.gather(*tasks)


def clean_emails_content(mails, email_sep, plain_content=True, html_content=False):
    separator = email_sep if email_sep else "\n--------------------------\n"
    text = ""
    for mail in mails:
        if mail:
            date = mail.data.date.strftime("%A %d. %B %Y")
            from_name = mail.data.from_[0].name
            to_names = ", ".join([recipient.name for recipient in mail.data.to])
            content = remove_lines_starting_with_prefixes(mail.data.body.value, [">"])
            text += f"From: {from_name}\nTo: {to_names}\nDate: {date}\nE-mail: {content}{separator}"

    return text

def extract_unique_emails(text):
    basic_email_pattern = re.compile(r"[^@\s]+@[^@\s]+\.[a-zA-Z0-9]+$")
    return list(set(re.findall(basic_email_pattern, text)))