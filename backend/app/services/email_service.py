"""Email notification service using AgentMail (rlhf@agentmail.to)."""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Any | None = None


def _get_client() -> Any | None:
    global _client
    settings = get_settings()
    if not settings.agentmail_enabled or not settings.agentmail_api_key:
        return None
    if _client is None:
        from agentmail import AgentMail

        _client = AgentMail(api_key=settings.agentmail_api_key)
    return _client


def _inbox_id() -> str | None:
    settings = get_settings()
    return settings.agentmail_inbox_id


def send_email(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    """Send an email via AgentMail. Returns True on success, False on skip/error."""
    client = _get_client()
    inbox_id = _inbox_id()
    if client is None or not inbox_id:
        logger.debug("AgentMail not configured — skipping email to %s", to)
        return False
    try:
        kwargs: dict[str, Any] = {"to": to, "subject": subject, "text": text}
        if html:
            kwargs["html"] = html
        client.inboxes.messages.send(inbox_id, **kwargs)
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s via AgentMail", to)
        return False


def send_exam_submitted_notification(
    annotator_email: str,
    annotator_name: str,
    exam_title: str,
    score: float | None,
    passed: bool | None,
) -> bool:
    score_str = f"{score * 100:.1f}%" if score is not None else "pending review"
    passed_str = "Yes" if passed else ("No" if passed is False else "pending review")
    subject = f"Exam submitted: {exam_title}"
    text = (
        f"Hi {annotator_name},\n\n"
        f"Your attempt on \"{exam_title}\" has been submitted.\n\n"
        f"  Score: {score_str}\n"
        f"  Passed: {passed_str}\n\n"
        "Results will be available after a reviewer releases them.\n\n"
        "— RLHF Annotation Studio"
    )
    html = (
        f"<p>Hi {annotator_name},</p>"
        f'<p>Your attempt on <strong>"{exam_title}"</strong> has been submitted.</p>'
        "<table style='border-collapse:collapse;'>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:600;'>Score</td><td>{score_str}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:600;'>Passed</td><td>{passed_str}</td></tr>"
        "</table>"
        "<p>Results will be available after a reviewer releases them.</p>"
        "<p style='color:#64748b;font-size:13px;'>— RLHF Annotation Studio</p>"
    )
    return send_email(annotator_email, subject, text, html)


def send_exam_released_notification(
    annotator_email: str,
    annotator_name: str,
    exam_title: str,
    score: float | None,
    passed: bool | None,
    review_notes: str | None,
    result_url: str | None = None,
) -> bool:
    score_str = f"{score * 100:.1f}%" if score is not None else "—"
    passed_str = "Yes" if passed else ("No" if passed is False else "—")
    subject = f"Exam results released: {exam_title}"
    text = (
        f"Hi {annotator_name},\n\n"
        f"Results for \"{exam_title}\" have been released by a reviewer.\n\n"
        f"  Score: {score_str}\n"
        f"  Passed: {passed_str}\n"
    )
    if review_notes:
        text += f"  Reviewer notes: {review_notes}\n"
    if result_url:
        text += f"\nView your results: {result_url}\n"
    text += "\n— RLHF Annotation Studio"

    html = (
        f"<p>Hi {annotator_name},</p>"
        f'<p>Results for <strong>"{exam_title}"</strong> have been released by a reviewer.</p>'
        "<table style='border-collapse:collapse;'>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:600;'>Score</td><td>{score_str}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;font-weight:600;'>Passed</td><td>{passed_str}</td></tr>"
    )
    if review_notes:
        html += (
            f"<tr><td style='padding:4px 12px 4px 0;font-weight:600;'>Notes</td>"
            f"<td>{review_notes}</td></tr>"
        )
    html += "</table>"
    if result_url:
        html += (
            f'<p><a href="{result_url}" style="color:#2563eb;">View your results</a></p>'
        )
    html += "<p style='color:#64748b;font-size:13px;'>— RLHF Annotation Studio</p>"
    return send_email(annotator_email, subject, text, html)


def send_review_queue_notification(
    reviewer_email: str,
    reviewer_name: str,
    annotator_name: str,
    exam_title: str,
) -> bool:
    subject = f"New exam submission for review: {exam_title}"
    text = (
        f"Hi {reviewer_name},\n\n"
        f"{annotator_name} submitted an attempt on \"{exam_title}\".\n"
        "Please review and release the results when ready.\n\n"
        "— RLHF Annotation Studio"
    )
    html = (
        f"<p>Hi {reviewer_name},</p>"
        f"<p><strong>{annotator_name}</strong> submitted an attempt on "
        f'<strong>"{exam_title}"</strong>.</p>'
        "<p>Please review and release the results when ready.</p>"
        "<p style='color:#64748b;font-size:13px;'>— RLHF Annotation Studio</p>"
    )
    return send_email(reviewer_email, subject, text, html)


def send_org_created_notification(
    creator_email: str,
    creator_name: str,
    org_name: str,
    org_slug: str,
) -> bool:
    subject = f"Organization created: {org_name}"
    text = (
        f"Hi {creator_name},\n\n"
        f"Your organization \"{org_name}\" (slug: {org_slug}) has been created.\n"
        "You have been assigned the admin role.\n\n"
        "You can now invite team members from the Settings page.\n\n"
        "— RLHF Annotation Studio"
    )
    html = (
        f"<p>Hi {creator_name},</p>"
        f'<p>Your organization <strong>"{org_name}"</strong> '
        f"(slug: <code>{org_slug}</code>) has been created.</p>"
        "<p>You have been assigned the <strong>admin</strong> role.</p>"
        "<p>You can now invite team members from the Settings page.</p>"
        "<p style='color:#64748b;font-size:13px;'>— RLHF Annotation Studio</p>"
    )
    return send_email(creator_email, subject, text, html)


def send_team_member_added_notification(
    member_email: str,
    member_name: str,
    org_name: str,
    added_by_name: str,
) -> bool:
    subject = f"You've been added to {org_name}"
    text = (
        f"Hi {member_name},\n\n"
        f"{added_by_name} added you to the organization \"{org_name}\" "
        "on RLHF Annotation Studio.\n\n"
        "Log in to access your team's tasks, exams, and review workflows.\n\n"
        "— RLHF Annotation Studio"
    )
    html = (
        f"<p>Hi {member_name},</p>"
        f"<p><strong>{added_by_name}</strong> added you to the organization "
        f'<strong>"{org_name}"</strong> on RLHF Annotation Studio.</p>'
        "<p>Log in to access your team's tasks, exams, and review workflows.</p>"
        "<p style='color:#64748b;font-size:13px;'>— RLHF Annotation Studio</p>"
    )
    return send_email(member_email, subject, text, html)


def send_team_member_added_admin_notification(
    admin_email: str,
    admin_name: str,
    member_name: str,
    member_email: str,
    org_name: str,
) -> bool:
    subject = f"New team member joined {org_name}: {member_name}"
    text = (
        f"Hi {admin_name},\n\n"
        f"{member_name} ({member_email}) has been added to \"{org_name}\".\n\n"
        "— RLHF Annotation Studio"
    )
    html = (
        f"<p>Hi {admin_name},</p>"
        f"<p><strong>{member_name}</strong> ({member_email}) has been added to "
        f'<strong>"{org_name}"</strong>.</p>'
        "<p style='color:#64748b;font-size:13px;'>— RLHF Annotation Studio</p>"
    )
    return send_email(admin_email, subject, text, html)


SUBMISSION_INBOX = "rlhf@agentmail.to"


def send_exam_submission_inbox_copy(
    annotator_name: str,
    annotator_email: str,
    exam_title: str,
    exam_id: str,
    attempt_id: str,
    score: float | None,
    passed: bool | None,
    submitted_at: str,
    answers_summary: dict[str, Any] | None = None,
) -> bool:
    """Send a detailed copy of every exam submission to the central inbox."""
    score_str = f"{score * 100:.1f}%" if score is not None else "pending review"
    passed_str = "Yes" if passed else ("No" if passed is False else "pending review")
    subject = f"[Exam Submission] {annotator_name} — {exam_title}"
    text = (
        f"Exam Submission Record\n"
        f"{'=' * 40}\n\n"
        f"Annotator:    {annotator_name} ({annotator_email})\n"
        f"Exam:         {exam_title}\n"
        f"Exam ID:      {exam_id}\n"
        f"Attempt ID:   {attempt_id}\n"
        f"Submitted at: {submitted_at}\n"
        f"Score:        {score_str}\n"
        f"Passed:       {passed_str}\n"
    )
    if answers_summary:
        text += f"\nAnswers submitted: {len(answers_summary)} task(s)\n"
        for task_id, answer in list(answers_summary.items())[:20]:
            preview = str(answer)[:120]
            text += f"  - {task_id}: {preview}\n"
        if len(answers_summary) > 20:
            text += f"  ... and {len(answers_summary) - 20} more\n"
    text += "\n— RLHF Annotation Studio (automated)"

    html = (
        "<div style='font-family:system-ui,sans-serif;max-width:640px;'>"
        "<h2 style='margin:0 0 16px;color:#1e293b;'>Exam Submission Record</h2>"
        "<table style='border-collapse:collapse;width:100%;'>"
        f"<tr><td style='padding:6px 12px 6px 0;font-weight:600;color:#475569;'>Annotator</td>"
        f"<td style='padding:6px 0;'>{annotator_name} ({annotator_email})</td></tr>"
        f"<tr><td style='padding:6px 12px 6px 0;font-weight:600;color:#475569;'>Exam</td>"
        f"<td style='padding:6px 0;'>{exam_title}</td></tr>"
        f"<tr><td style='padding:6px 12px 6px 0;font-weight:600;color:#475569;'>Exam ID</td>"
        f"<td style='padding:6px 0;font-family:monospace;font-size:13px;'>{exam_id}</td></tr>"
        f"<tr><td style='padding:6px 12px 6px 0;font-weight:600;color:#475569;'>Attempt ID</td>"
        f"<td style='padding:6px 0;font-family:monospace;font-size:13px;'>{attempt_id}</td></tr>"
        f"<tr><td style='padding:6px 12px 6px 0;font-weight:600;color:#475569;'>Submitted</td>"
        f"<td style='padding:6px 0;'>{submitted_at}</td></tr>"
        f"<tr><td style='padding:6px 12px 6px 0;font-weight:600;color:#475569;'>Score</td>"
        f"<td style='padding:6px 0;'>{score_str}</td></tr>"
        f"<tr><td style='padding:6px 12px 6px 0;font-weight:600;color:#475569;'>Passed</td>"
        f"<td style='padding:6px 0;'>{passed_str}</td></tr>"
        "</table>"
    )
    if answers_summary:
        html += (
            f"<p style='margin:16px 0 8px;font-weight:600;color:#475569;'>"
            f"Answers submitted: {len(answers_summary)} task(s)</p>"
            "<ul style='margin:0;padding-left:20px;font-size:13px;color:#334155;'>"
        )
        for task_id, answer in list(answers_summary.items())[:20]:
            preview = str(answer)[:120].replace("<", "&lt;").replace(">", "&gt;")
            html += f"<li><code>{task_id}</code>: {preview}</li>"
        if len(answers_summary) > 20:
            html += f"<li><em>... and {len(answers_summary) - 20} more</em></li>"
        html += "</ul>"
    html += (
        "<p style='color:#94a3b8;font-size:12px;margin-top:20px;'>"
        "— RLHF Annotation Studio (automated)</p></div>"
    )
    return send_email(SUBMISSION_INBOX, subject, text, html)
