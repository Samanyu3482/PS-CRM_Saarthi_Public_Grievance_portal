"""
mail_service.py — Send email notifications when a complaint is filed.

Sends two emails via Gmail SMTP:
  1. To the mapped ministry address (using Gmail + alias trick)
  2. To the citizen who filed the complaint (acknowledgement + QR tracking code)
"""

import smtplib
import logging
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, timezone

import qrcode

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Sender configuration ──────────────────────────────────────────────────────
SENDER_EMAIL = "saarthii.pscrm@gmail.com"

# ── Ministry → email mapping ──────────────────────────────────────────────────
MINISTRY_EMAIL_MAP: dict[str, str] = {
    "Ministry of Finance":                  "grievance.ministry+finance@gmail.com",
    "Ministry of Railways":                 "grievance.ministry+railways@gmail.com",
    "Ministry of Petroleum and Natural Gas":"grievance.ministry+petroleum@gmail.com",
    "Ministry of Labour and Employment":    "grievance.ministry+labour@gmail.com",
    "Ministry of Housing and Urban Affairs":"grievance.ministry+housing@gmail.com",
    "Ministry of Power":                    "grievance.ministry+power@gmail.com",
    "Ministry of Communications":           "grievance.ministry+communications@gmail.com",
    "Ministry of Health and Family Welfare":"grievance.ministry+health@gmail.com",
    "Ministry of Education":                "grievance.ministry+education@gmail.com",
    "Ministry of Agriculture":              "grievance.ministry+agriculture@gmail.com",
    "Ministry of Water":                    "grievance.ministry+water@gmail.com",
    "UNKNOWN":                              "grievance.ministry+unclassified@gmail.com",
}


def _generate_qr_png_bytes(url: str) -> bytes:
    """Generate a QR code and return raw PNG bytes."""
    img = qrcode.make(url, box_size=8, border=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_ministry_html(
    complaint_id: str,
    title: str,
    description: str,
    ministry: str,
    department: str | None,
    location: dict,
    priority: str,
    citizen_name: str,
    citizen_email: str,
    filed_at: str,
) -> str:
    """Rich HTML email sent to the ministry."""
    return f"""\
<html>
<body style="font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; padding: 24px;">
  <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 12px;
              box-shadow: 0 2px 12px rgba(0,0,0,0.08); overflow: hidden;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%); padding: 24px 32px;">
      <h1 style="margin: 0; color: #fff; font-size: 22px;">🏛️ New Grievance Received</h1>
      <p style="margin: 6px 0 0; color: #c9ddf0; font-size: 13px;">Saarthii — Public Grievance Portal</p>
    </div>
    <!-- Body -->
    <div style="padding: 28px 32px;">
      <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
        <tr><td style="padding: 8px 0; color: #888; width: 140px;">Complaint ID</td>
            <td style="padding: 8px 0; font-weight: 600;">{complaint_id}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Title</td>
            <td style="padding: 8px 0; font-weight: 600;">{title}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Ministry</td>
            <td style="padding: 8px 0;">{ministry or 'Unclassified'}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Department</td>
            <td style="padding: 8px 0;">{department or '—'}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Priority</td>
            <td style="padding: 8px 0;"><span style="background: {'#e74c3c' if priority == 'critical' else '#f39c12' if priority == 'high' else '#3498db' if priority == 'medium' else '#95a5a6'};
                color: #fff; padding: 2px 10px; border-radius: 10px; font-size: 12px;">{priority.upper()}</span></td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Location</td>
            <td style="padding: 8px 0;">{location.get('address', '')}, {location.get('city', '')}, {location.get('state', '')} — {location.get('pincode', '')}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Filed By</td>
            <td style="padding: 8px 0;">{citizen_name} ({citizen_email})</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Filed At</td>
            <td style="padding: 8px 0;">{filed_at}</td></tr>
      </table>
      <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
      <h3 style="margin: 0 0 8px; font-size: 14px; color: #333;">Description</h3>
      <p style="margin: 0; color: #555; line-height: 1.6; font-size: 14px;">{description}</p>
    </div>
    <!-- Footer -->
    <div style="background: #f8f9fb; padding: 16px 32px; text-align: center; font-size: 12px; color: #999;">
      This email was auto-generated by the Saarthii PS-CRM platform. Please do not reply directly.
    </div>
  </div>
</body>
</html>"""


def _build_citizen_html(
    complaint_id: str,
    title: str,
    description: str,
    ministry: str,
    department: str | None,
    location: dict,
    priority: str,
    citizen_name: str,
    filed_at: str,
    tracking_url: str,
) -> str:
    """Rich HTML acknowledgement email sent to the citizen, with QR tracking code.
    The QR code is referenced via CID (cid:qr_tracking) and attached inline."""
    return f"""\
<html>
<body style="font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; padding: 24px;">
  <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 12px;
              box-shadow: 0 2px 12px rgba(0,0,0,0.08); overflow: hidden;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #0d7c3d 0%, #27ae60 100%); padding: 24px 32px;">
      <h1 style="margin: 0; color: #fff; font-size: 22px;">✅ Complaint Registered Successfully</h1>
      <p style="margin: 6px 0 0; color: #b8f0cf; font-size: 13px;">Saarthii — Public Grievance Portal</p>
    </div>
    <!-- Body -->
    <div style="padding: 28px 32px;">
      <p style="margin: 0 0 16px; font-size: 15px; color: #333;">Dear <strong>{citizen_name}</strong>,</p>
      <p style="margin: 0 0 20px; font-size: 14px; color: #555; line-height: 1.6;">
        Your grievance has been successfully registered on the Saarthii platform.
        It has been forwarded to <strong>{ministry or 'the concerned ministry'}</strong> for action.
        Below are the details for your reference:
      </p>
      <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
        <tr><td style="padding: 8px 0; color: #888; width: 140px;">Complaint ID</td>
            <td style="padding: 8px 0; font-weight: 600;">{complaint_id}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Title</td>
            <td style="padding: 8px 0; font-weight: 600;">{title}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Ministry</td>
            <td style="padding: 8px 0;">{ministry or 'Under Review'}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Department</td>
            <td style="padding: 8px 0;">{department or '—'}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Priority</td>
            <td style="padding: 8px 0;"><span style="background: {'#e74c3c' if priority == 'critical' else '#f39c12' if priority == 'high' else '#3498db' if priority == 'medium' else '#95a5a6'};
                color: #fff; padding: 2px 10px; border-radius: 10px; font-size: 12px;">{priority.upper()}</span></td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Location</td>
            <td style="padding: 8px 0;">{location.get('address', '')}, {location.get('city', '')}, {location.get('state', '')} — {location.get('pincode', '')}</td></tr>
        <tr><td style="padding: 8px 0; color: #888;">Filed At</td>
            <td style="padding: 8px 0;">{filed_at}</td></tr>
      </table>
      <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
      <h3 style="margin: 0 0 8px; font-size: 14px; color: #333;">Your Complaint</h3>
      <p style="margin: 0; color: #555; line-height: 1.6; font-size: 14px;">{description}</p>

      <!-- ── QR Code Tracking Section ── -->
      <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
      <div style="text-align: center; padding: 16px 0;">
        <h3 style="margin: 0 0 4px; font-size: 16px; color: #1e3a5f;">📱 Track Your Grievance</h3>
        <p style="margin: 0 0 16px; font-size: 13px; color: #888; line-height: 1.5;">
          Scan this QR code anytime to see the real-time progress of your complaint.
        </p>
        <img src="cid:qr_tracking" alt="QR Code for tracking" width="180" height="180"
             style="display: block; margin: 0 auto 12px; border: 2px solid #e8ecf1; border-radius: 8px; padding: 8px; background: #fff;" />
        <p style="margin: 0; font-size: 12px; color: #aaa;">
          Or visit: <a href="{tracking_url}" style="color: #2d6a9f; text-decoration: underline;">{tracking_url}</a>
        </p>
      </div>

      <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #888; line-height: 1.5;">
        You can also track the status of your complaint on the
        <strong>Saarthii dashboard</strong>. We will notify you when there are updates.
      </p>
    </div>
    <!-- Footer -->
    <div style="background: #f8f9fb; padding: 16px 32px; text-align: center; font-size: 12px; color: #999;">
      This is an automated acknowledgement from Saarthii PS-CRM. Please do not reply to this email.
    </div>
  </div>
</body>
</html>"""


def _send_email(to_email: str, subject: str, html_body: str, inline_images: dict[str, bytes] | None = None) -> None:
    """Send a single email via Gmail SMTP with TLS.
    
    If inline_images is provided, images are embedded as CID attachments.
    Keys are Content-ID names (without angle brackets), values are PNG bytes.
    """
    password = settings.GMAIL_APP_PASSWORD
    if not password:
        logger.warning("GMAIL_APP_PASSWORD not set — skipping email to %s", to_email)
        return

    # When we have inline images, use "related" so the CID references work
    if inline_images:
        msg = MIMEMultipart("related")
        # HTML goes in an "alternative" sub-part
        msg_alt = MIMEMultipart("alternative")
        msg_alt.attach(MIMEText(html_body, "html"))
        msg.attach(msg_alt)

        # Attach each inline image
        for cid_name, img_bytes in inline_images.items():
            img_part = MIMEImage(img_bytes, _subtype="png")
            img_part.add_header("Content-ID", f"<{cid_name}>")
            img_part.add_header("Content-Disposition", "inline", filename=f"{cid_name}.png")
            msg.attach(img_part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(html_body, "html"))

    msg["From"] = f"Saarthii PS-CRM <{SENDER_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_EMAIL, password)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        print(f"✉️  Email sent → {to_email} | Subject: {subject}")
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()


def send_complaint_emails(
    complaint_id: str,
    title: str,
    description: str,
    ministry: str | None,
    department: str | None,
    location: dict,
    priority: str,
    citizen_name: str,
    citizen_email: str,
) -> None:
    """
    Fire-and-forget: sends notification to the ministry and an
    acknowledgement to the citizen after a complaint is created.
    """
    filed_at = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    # ── 1. Email to the ministry ──────────────────────────────────────────────
    ministry_key = ministry if ministry in MINISTRY_EMAIL_MAP else "UNKNOWN"
    ministry_email = MINISTRY_EMAIL_MAP[ministry_key]
    ministry_subject = f"[Saarthii] New Grievance #{complaint_id}: {title}"

    ministry_html = _build_ministry_html(
        complaint_id=complaint_id,
        title=title,
        description=description,
        ministry=ministry or "Unclassified",
        department=department,
        location=location,
        priority=priority,
        citizen_name=citizen_name,
        citizen_email=citizen_email,
        filed_at=filed_at,
    )
    _send_email(ministry_email, ministry_subject, ministry_html)

    # ── 2. Acknowledgement email to the citizen (with QR code) ────────────────
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    tracking_url = f"{frontend_url}/track/{complaint_id}"

    # Generate QR code as raw PNG bytes for CID attachment
    qr_png_bytes = _generate_qr_png_bytes(tracking_url)

    citizen_subject = f"[Saarthii] Your Complaint #{complaint_id} Has Been Registered"
    citizen_html = _build_citizen_html(
        complaint_id=complaint_id,
        title=title,
        description=description,
        ministry=ministry or "Under Review",
        department=department,
        location=location,
        priority=priority,
        citizen_name=citizen_name,
        filed_at=filed_at,
        tracking_url=tracking_url,
    )
    _send_email(
        citizen_email,
        citizen_subject,
        citizen_html,
        inline_images={"qr_tracking": qr_png_bytes},
    )
