# -*- coding: utf-8 -*-
import logging
from pathlib import Path

from fastapi import APIRouter
from langchain.prompts import ChatPromptTemplate
from common.constants import EMAIL_SORT_LIMIT
from common.ik_apis.mail import get_mail_metadata, list_mailboxes_folders, list_mails, move_mails

from api.dependencies.ik_api import IkApiDep
from common.mail_utils import get_mail, extract_unique_emails, remove_lines_starting_with_prefixes, clean_text
from common.models.request.mail import MailEventSuggestionRequest
from common.models.response.mail import EventResponse, GetEmailResponse, MailFolder, Thread
from common.models.response.summary import SummaryResponse
from common.models.response.reply import ReplyResponse
from common.openai_clients import client_from_config

logger = logging.getLogger(__name__)

router = APIRouter(
        tags=["mail"],
        )

EVENT_PROMPT = ChatPromptTemplate([
    ("system", """You are an efficient and straight-to-the-point assistant that specializes in preparing calendar invites. You will read the following conversation and determine if it contains a confirmation for an event. If no event is detected, answer with 'No'. If an event is detected, you will output a JSON-formatted string containing the following fields: 'e-mails', 'names', 'title', 'description', 'date', 'start_time' based on the information you gathered from the conversation. 
* The field 'e-mails' is a list of each participants e-mail addresses as usually found in the 'To' or 'From' fields.
* List of possible e-mails: {emails}
* The field 'date' must use the format 'YYYY-MM-DD'.
* The field 'start_time' must use the format 'HH:MM'.
* You should try to avoid using e-mails found in the e-mails as the ones found in e-mail headers are often correct. If an e-mail is not found, do not add the corresponding name to the list. If the conversation is simply a confirmation sent by email for an event, the attendee will be the single recipient.
The 'title' and 'description' fields must be written in the same language as the 'text' field."""),
    ("human", """Mail conversation: {text}
JSON-formatted calendar invitation:""")
    ])

VALIDATION_PROMPT = ChatPromptTemplate([
    "system",
    "You are a calendar event validator. Check if the AI's extracted event information is accurate. Return ```valid``` if correct. If incorrect, provide rectification as JSON between ```json``` tags.",
    ("human", """Email: {text}
AI extraction: {answer}
Verification:""")
    ])

SUMMARY_PROMPT = ChatPromptTemplate([
    ("system", """Tu es un assistant spécialisé dans la création de résumés d'emails. Analyse la conversation email fournie et génère un résumé concis en français. Identifie les points clés et les participants."""),
    ("human", """Conversation email: {text}
Génère un résumé structuré:""")
    ])

REPLY_PROMPT = ChatPromptTemplate([
    ("system", """Réponse email (max 200 mots), ton professionnel."""),
    ("human", """Email: {text}
Réponse:""")
    ])

FOLDER_CLASSIFIER_PROMPT = ChatPromptTemplate([
    ("system", """You are an assistant that classifies emails into folders. 
You will receive:
- A list of available folders
- A single email (subject, sender, body preview)

You must return ONLY the folder name where this email should be stored. 
If no folder fits, return "Uncategorized"."""),
    ("human", """Folders: {folders}
Email: {email}

Folder:""")
])

classifier_client = client_from_config(model="qwen3", temperature=0.0, max_tokens=500)
classifier_chain = FOLDER_CLASSIFIER_PROMPT | classifier_client

event_client = client_from_config(model="qwen3", temperature=0.12, max_tokens=5000)
event_chain = EVENT_PROMPT | event_client.with_structured_output(EventResponse)

validation_prompt = client_from_config(model="mistral3", temperature=0.13, max_tokens=5000)
validation_chain = VALIDATION_PROMPT | validation_prompt

summary_client = client_from_config(model="qwen3", temperature=0.3, max_tokens=2000)
summary_chain = SUMMARY_PROMPT | summary_client.with_structured_output(SummaryResponse)

reply_client = client_from_config(model="qwen3", temperature=0.3, max_tokens=1500)
reply_chain = REPLY_PROMPT | reply_client.with_structured_output(ReplyResponse)


@router.post(
        "/mail/{mailbox_uuid}/folder/{folder_id}/thread/{thread_id}/event_suggestion",
        response_model=EventResponse,
        responses={400: {"description": "Bad Request"}},
        operation_id="event_suggestion",
        summary="Suggest an event",
        description=Path("common/docs/event_suggestion.md").read_text(),
        )
async def event_suggestion(
        mailbox_uuid: str,
        folder_id: str,
        thread_id: str,
        request: MailEventSuggestionRequest,
        ik_api: IkApiDep
        ) -> EventResponse:
    """

    Args:
        request:
        ik_api:

    Returns:

    """
    logger.info(f"Request for mailbox uuid: {mailbox_uuid}")
    mails = await get_mail(request.context_message_uid, ik_api, mailbox_uuid)
    email_sep = "\n---------------------------------------\n"
    text = ""
    emails = set()
    subject = None
    for mail in mails:
        if mail:
            date = mail.data.date.strftime("%A %d. %B %Y")
            from_item = mail.data.from_[0]
            from_display = f"{from_item.name} ({from_item.email})"
            to_cc_items = mail.data.to + mail.data.cc
            body = mail.data.body.value
            to_display = ", ".join([f"{r.name} ({r.email})" for r in to_cc_items])
            text += f"From: {from_display}\nTo: {to_display}\nDate: {date}\nE-mail: {body}{email_sep}"
            if subject is None:
                subject = mail.data.subject

            # Update email list
            field_emails = [str(item.email) for item in [from_item] + to_cc_items]
            parsed_emails = extract_unique_emails(body)
            emails.update(field_emails + parsed_emails)

    text = f"Subject: {subject}\n\n{text}"
    text = remove_lines_starting_with_prefixes(text, [">"])
    text = clean_text(text)

    result = event_chain.invoke(
            {"emails": ", ".join(emails), "text": text}
            )

    # Validate output
    valid_emails = [email for email in result.emails if email in emails]
    if len(result.emails) != len(valid_emails):
        wrong_emails = [email for email in result.emails if email not in emails]
        result.emails = valid_emails
        logger.info(f"The following e-mails have been hallucinated and removed: {wrong_emails}")
    validation_result = validation_chain.invoke(
            {"answer": result, "text": text}
            )
    return EventResponse.correct_json(validation_result, result)


@router.post(
        "/mail/{mailbox_uuid}/folder/{folder_id}/thread/{thread_id}/summary",
        response_model=SummaryResponse,
        responses={400: {"description": "Bad Request"}},
        operation_id="email_summary",
        summary="Generate email summary",
        description="Generate a concise summary of the email conversation",
        )
async def email_summary(
        mailbox_uuid: str,
        folder_id: str,
        thread_id: str,
        request: MailEventSuggestionRequest,
        ik_api: IkApiDep
        ) -> SummaryResponse:
    """Generate a summary of the email conversation."""
    logger.info(f"Summary request for mailbox uuid: {mailbox_uuid}")
    mails = await get_mail(request.context_message_uid, ik_api, mailbox_uuid)
    
    email_sep = "\n---------------------------------------\n"
    text = ""
    participants = set()
    subject = None
    
    for mail in mails:
        if mail:
            date = mail.data.date.strftime("%A %d. %B %Y")
            from_item = mail.data.from_[0]
            from_display = f"{from_item.name} ({from_item.email})"
            to_cc_items = mail.data.to + mail.data.cc
            body = mail.data.body.value
            to_display = ", ".join([f"{r.name} ({r.email})" for r in to_cc_items])
            text += f"From: {from_display}\nTo: {to_display}\nDate: {date}\nE-mail: {body}{email_sep}"
            
            if subject is None:
                subject = mail.data.subject
            
            # Collect participants
            participants.add(from_item.name or from_item.email)
            participants.update([r.name or r.email for r in to_cc_items])
    
    text = f"Subject: {subject}\n\n{text}"
    text = remove_lines_starting_with_prefixes(text, [">"])
    text = clean_text(text)
    
    result = summary_chain.invoke({"text": text})
    
    # Ensure participants list is populated
    if not result.participants:
        result.participants = list(participants)
    
    return result


@router.post(
        "/mail/{mailbox_uuid}/folder/{folder_id}/thread/{thread_id}/reply",
        response_model=ReplyResponse,
        responses={400: {"description": "Bad Request"}},
        operation_id="email_reply",
        summary="Generate email reply",
        description="Generate an AI-powered reply to the email conversation",
        )
async def email_reply(
        mailbox_uuid: str,
        folder_id: str,
        thread_id: str,
        request: MailEventSuggestionRequest,
        ik_api: IkApiDep
        ) -> ReplyResponse:
    """Generate an AI-powered reply to the email conversation."""
    logger.info(f"Reply request for mailbox uuid: {mailbox_uuid}")
    mails = await get_mail(request.context_message_uid, ik_api, mailbox_uuid)
    
    email_sep = "\n---------------------------------------\n"
    text = ""
    subject = None
    
    for mail in mails:
        if mail:
            date = mail.data.date.strftime("%A %d. %B %Y")
            from_item = mail.data.from_[0]
            from_display = f"{from_item.name} ({from_item.email})"
            to_cc_items = mail.data.to + mail.data.cc
            body = mail.data.body.value
            to_display = ", ".join([f"{r.name} ({r.email})" for r in to_cc_items])
            text += f"From: {from_display}\nTo: {to_display}\nDate: {date}\nE-mail: {body}{email_sep}"
            
            if subject is None:
                subject = mail.data.subject
    
    text = f"Subject: {subject}\n\n{text}"
    text = remove_lines_starting_with_prefixes(text, [">"])
    text = clean_text(text)
    
    # Limit text length for faster processing (keep only last 1500 chars)
    if len(text) > 2500:
        text = text[-2500:]
    
    try:
        result = reply_chain.invoke({"text": text})
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        # Return a simple fallback response
        result = ReplyResponse(
            subject=f"Re: {subject}" if subject and not subject.startswith("Re:") else (subject or "Re: Votre message"),
            body="Merci pour votre message. Je reviendrai vers vous prochainement.",
            tone="professionnel"
        )
    
    # Ensure subject has "Re:" prefix if not already present
    if result.subject and not result.subject.startswith("Re:"):
        result.subject = f"Re: {result.subject}"
    elif not result.subject and subject:
        result.subject = f"Re: {subject}" if not subject.startswith("Re:") else subject
    
    return result


# suite

def get_folder_id_by_name(folders: list[MailFolder], name: str) -> str | None:
    for folder in folders:
        if folder.name.lower() == name.lower():
            return folder.id
        if folder.children:
            result = get_folder_id_by_name(folder.children, name)
            if result:
                return result
    return None

def get_folder_id_by_path(folders: list[MailFolder], path) -> str | None:
    for folder in folders:
        if folder.path == path:
            return folder.id
        if folder.children:
            result = get_folder_id_by_path(folder.children, path)
            if result:
                return result
    return None

def extract_seen_message_ids(threads: list[Thread], folder_id: str) -> list[str]:
    ids = []
    for thread in threads:
        for message in thread.messages:
            if message.seen:
                parts = message.resource.strip("/").split("/")
                try:
                    folder_index = parts.index("folder")
                    route_folder_id = parts[folder_index + 1]
                    if route_folder_id == folder_id:
                        msg_index = parts.index("message")
                        ids.append(parts[msg_index + 1])
                except (ValueError, IndexError):
                    continue
    return ids

def get_mail_for_ai(mail: GetEmailResponse) -> str:
    text = ""
    emails = set()
    subject = None
    date = mail.data.date.strftime("%A %d. %B %Y")
    from_item = mail.data.from_[0]
    from_display = f"{from_item.name} ({from_item.email})"
    to_cc_items = mail.data.to + mail.data.cc
    body = mail.data.body.value
    to_display = ", ".join([f"{r.name} ({r.email})" for r in to_cc_items])
    text += f"From: {from_display}\nTo: {to_display}\nDate: {date}\nE-mail: {body}"
    if subject is None:
        subject = mail.data.subject

    # Update email list
    field_emails = [str(item.email) for item in [from_item] + to_cc_items]
    parsed_emails = extract_unique_emails(body)
    emails.update(field_emails + parsed_emails)

    text = f"Subject: {subject}\n\n{text}"
    text = remove_lines_starting_with_prefixes(text, [">"])
    text = clean_text(text)
    return text

def get_folders_for_ai(folders: list[MailFolder]) -> str:
    lines = []
    for folder in folders:
        if not folder.role:
            lines.append(folder.path)
            if folder.children:
                lines.append(get_folders_for_ai(folder.children))
    return "\n".join(lines)  

  
@router.post(
        "/mail/{mailbox_uuid}/classifier",
        # response_model=EventResponse,
        responses={400: {"description": "Bad Request"}},
        operation_id="classifier",
        summary="Classify emails in custom folders",
        description=Path("common/docs/event_suggestion.md").read_text(),
        )
async def event_suggestion(
        mailbox_uuid: str,
        ik_api: IkApiDep
        ):
    """

    Args:
        request:
        ik_api:

    Returns:

    """
    print('hello')
    folders = await list_mailboxes_folders(ik_api, mailbox_uuid)
    inbox_id = get_folder_id_by_name(folders.data, 'inbox')
    mails = await list_mails(ik_api, mailbox_uuid, inbox_id)
    ids = extract_seen_message_ids(mails.data.threads, inbox_id)
    folders_for_ai = get_folders_for_ai(folders.data)

    # TODO: RESPONSE (return type + return)
    # TODO: SEE WHEN NO FOLDER

    for i in range(0, min(len(ids), EMAIL_SORT_LIMIT)):
        mail = await get_mail_metadata(ik_api, mailbox_uuid, inbox_id, ids[i])
        mail_for_ai = get_mail_for_ai(mail)
        result = classifier_chain.invoke({"folders": folders_for_ai, "email": mail_for_ai})
        print(result.content)
        if result.content != "Uncategorized":
            result_id = get_folder_id_by_path(folders.data,result.content)
            await move_mails(ik_api,mailbox_uuid, result_id, [mail.data.uid])

    # return EventResponse.correct_json(validation_result, result)