"""
Quick standalone test — run from the project root with venv active:
    python test_mail.py
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = "saarthii.pscrm@gmail.com"
PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

TO_EMAIL = "grievance.ministry+finance@gmail.com"   # test ministry recipient

print(f"SENDER : {SENDER_EMAIL}")
print(f"TO     : {TO_EMAIL}")
print(f"PASS   : {'*' * len(PASSWORD)}  ({len(PASSWORD)} chars)")

subject = "[Saarthii TEST] Sample Grievance Email"
html = """\
<html>
<body style="font-family: Arial, sans-serif; padding: 24px;">
  <div style="max-width: 520px; margin:auto; border:1px solid #ddd; border-radius:10px; overflow:hidden;">
    <div style="background: linear-gradient(135deg,#1e3a5f,#2d6a9f); padding:20px 28px;">
      <h2 style="margin:0; color:#fff;">🏛️ Test Grievance Email</h2>
      <p style="margin:4px 0 0; color:#c9ddf0; font-size:13px;">Saarthii PS-CRM — Mail Service Test</p>
    </div>
    <div style="padding: 20px 28px; font-size:14px; color:#333;">
      <p>This is a <strong>test email</strong> to verify that the Saarthii mail service is working correctly.</p>
      <table style="width:100%; border-collapse:collapse; margin:12px 0;">
        <tr><td style="padding:6px 0; color:#888; width:120px;">Complaint ID</td><td style="font-weight:600;">TEST-001</td></tr>
        <tr><td style="padding:6px 0; color:#888;">Title</td><td style="font-weight:600;">Broken street lights</td></tr>
        <tr><td style="padding:6px 0; color:#888;">Ministry</td><td>Ministry of Power</td></tr>
        <tr><td style="padding:6px 0; color:#888;">Priority</td>
            <td><span style="background:#f39c12; color:#fff; padding:2px 10px; border-radius:10px; font-size:12px;">MEDIUM</span></td></tr>
        <tr><td style="padding:6px 0; color:#888;">Location</td><td>Sector 15, Chandigarh, Punjab — 160015</td></tr>
      </table>
      <p style="color:#555; line-height:1.6;">Street lights on the main road in Sector 15 have been non-functional for the past two weeks, making it unsafe for pedestrians and commuters after dark.</p>
    </div>
    <div style="background:#f8f9fb; padding:12px 28px; text-align:center; font-size:12px; color:#999;">
      This is a test email from the Saarthii PS-CRM platform.
    </div>
  </div>
</body>
</html>
"""

msg = MIMEMultipart("alternative")
msg["From"] = f"Saarthii PS-CRM <{SENDER_EMAIL}>"
msg["To"] = TO_EMAIL
msg["Subject"] = subject
msg.attach(MIMEText(html, "html"))

try:
    print("\nConnecting to smtp.gmail.com:587 ...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.set_debuglevel(1)      # verbose SMTP debug output
        server.ehlo()
        server.starttls()
        server.ehlo()
        print("Logging in ...")
        server.login(SENDER_EMAIL, PASSWORD)
        print("Sending ...")
        server.sendmail(SENDER_EMAIL, TO_EMAIL, msg.as_string())
    print("\n✅ EMAIL SENT SUCCESSFULLY!")
except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ AUTHENTICATION FAILED: {e}")
    print("   → Make sure GMAIL_APP_PASSWORD in .env is a valid 16-character App Password.")
    print("   → Generate one at: https://myaccount.google.com/apppasswords")
    print("   → Two-Factor Authentication must be enabled on the Gmail account.")
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
