import os
import json
import logging
import requests
from flask import Flask, request, jsonify, send_from_directory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
SENDER_EMAIL = "support@adept-link.com"
SENDER_NAME = "Compliance Hub — Adeptlink"
NOTIFY_EMAIL = "support@adept-link.com"
NOTIFY_SENDER_EMAIL = "noreply@adept-link.com"   # khác recipient để tránh spam filter


def send_email(to_email, to_name, subject, html_content, sender_email=None, reply_to=None):
    if not BREVO_API_KEY:
        log.error("BREVO_API_KEY is not set — cannot send email")
        return 500, "No API key"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json",
    }
    from_email = sender_email or SENDER_EMAIL
    payload = {
        "sender": {"name": SENDER_NAME, "email": from_email},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
    }
    if reply_to:
        payload["replyTo"] = {"email": reply_to}
    try:
        resp = requests.post(BREVO_URL, headers=headers, json=payload, timeout=10)
        log.info("Brevo → %s | status=%s | to=%s | subj=%s", to_email, resp.status_code, to_email, subject)
        if resp.status_code not in (200, 201):
            log.error("Brevo error body: %s", resp.text[:300])
        return resp.status_code, resp.text
    except Exception as exc:
        log.exception("Brevo request failed: %s", exc)
        return 0, str(exc)


@app.route("/api/contact", methods=["POST"])
def contact():
    data = request.get_json(force=True, silent=True) or {}
    company = data.get("company", "").strip()
    name    = data.get("name", "").strip()
    title   = data.get("title", "").strip()
    email   = data.get("email", "").strip()
    phone   = data.get("phone", "").strip()
    product = data.get("product", "").strip()
    volume  = data.get("volume", "").strip()
    hs_info = data.get("hs_info", "").strip()

    log.info("Contact form received: company=%s name=%s email=%s", company, name, email)

    if not email or not company or not name:
        return jsonify({"ok": False, "error": "Thiếu thông tin bắt buộc"}), 400

    if not BREVO_API_KEY:
        log.error("BREVO_API_KEY missing in environment")
        return jsonify({"ok": False, "error": "Chưa cấu hình BREVO_API_KEY"}), 500

    def row(label, value, mono=False):
        if not value:
            return ""
        style = "font-family:monospace;" if mono else ""
        return f"<tr><td style='padding:8px 0;color:#5a6b5a;width:150px;vertical-align:top;'><strong>{label}</strong></td><td style='padding:8px 0;color:#0f1a0f;{style}'>{value}</td></tr>"

    # ── Email 1: thông báo nội bộ đến Adeptlink ──
    internal_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1a3320;padding:20px 28px;border-radius:8px 8px 0 0;">
        <h2 style="color:#e6a820;margin:0;font-size:18px;">📋 Yêu cầu tư vấn mới</h2>
        <p style="color:rgba(255,255,255,0.7);margin:4px 0 0;font-size:13px;">Compliance Hub — Adeptlink</p>
      </div>
      <div style="background:#f7f3ec;padding:24px 28px;border-radius:0 0 8px 8px;border:1px solid #ede6d6;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          {row('Công ty', company)}
          {row('Người liên hệ', name)}
          {row('Chức vụ', title)}
          <tr><td style='padding:8px 0;color:#5a6b5a;width:150px;'><strong>Email</strong></td><td style='padding:8px 0;'><a href='mailto:{email}' style='color:#3d7a52;'>{email}</a></td></tr>
          {row('Di động', phone)}
          {row('Sản phẩm', product)}
          {row('Kim ngạch', volume)}
          {row('HS Code', hs_info, mono=True)}
        </table>
        <div style="margin-top:20px;padding:12px 16px;background:#fff;border-radius:6px;border:1px solid #ede6d6;font-size:12px;color:#5a6b5a;">
          Hãy phản hồi trong vòng <strong>24h</strong> qua email hoặc số điện thoại trên.
        </div>
      </div>
    </div>
    """
    status1, body1 = send_email(
        NOTIFY_EMAIL, "Adeptlink Support",
        f"[Compliance Hub] Yêu cầu tư vấn từ {company}",
        internal_html,
        sender_email=NOTIFY_SENDER_EMAIL,
        reply_to=email
    )
    if status1 not in (200, 201):
        log.error("Internal notify email FAILED: status=%s body=%s", status1, body1[:200])
        return jsonify({"ok": False, "error": f"Lỗi gửi email thông báo (Brevo {status1})"}), 500

    # ── Email 2: xác nhận gửi đến khách hàng ──
    confirm_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1a3320;padding:20px 28px;border-radius:8px 8px 0 0;">
        <h2 style="color:#e6a820;margin:0;font-size:18px;">✅ Đã nhận yêu cầu tư vấn!</h2>
        <p style="color:rgba(255,255,255,0.7);margin:4px 0 0;font-size:13px;">Compliance Hub — Adeptlink</p>
      </div>
      <div style="background:#f7f3ec;padding:24px 28px;border-radius:0 0 8px 8px;border:1px solid #ede6d6;">
        <p style="color:#0f1a0f;font-size:15px;margin:0 0 16px;">Xin chào <strong>{name}</strong>{(' — ' + title) if title else ''},</p>
        <p style="color:#5a6b5a;font-size:14px;line-height:1.7;margin:0 0 16px;">
          Chúng tôi đã nhận được yêu cầu tư vấn xuất khẩu thực phẩm sang Canada của công ty
          <strong style="color:#1a3320;">{company}</strong>.
          Đội ngũ Adeptlink sẽ liên hệ với bạn trong vòng <strong>24 giờ làm việc</strong>.
        </p>
        <div style="background:#fff;border-radius:6px;border:1px solid #ede6d6;padding:16px 20px;margin-bottom:20px;">
          <p style="margin:0 0 10px;font-size:12px;color:#8a9e8a;text-transform:uppercase;letter-spacing:0.7px;">Thông tin đã gửi</p>
          {'<p style="margin:4px 0;font-size:13px;color:#0f1a0f;"><strong>Sản phẩm:</strong> ' + product + '</p>' if product else ''}
          {'<p style="margin:4px 0;font-size:13px;color:#0f1a0f;"><strong>Kim ngạch:</strong> ' + volume + '</p>' if volume else ''}
          {'<p style="margin:4px 0;font-size:13px;color:#0f1a0f;"><strong>HS Code:</strong> <span style="font-family:monospace;">' + hs_info + '</span></p>' if hs_info else ''}
          {'<p style="margin:4px 0;font-size:13px;color:#0f1a0f;"><strong>Di động:</strong> ' + phone + '</p>' if phone else ''}
        </div>
        <div style="text-align:center;">
          <a href="https://adept-link.com/registration/" style="display:inline-block;background:#1a3320;color:#e6a820;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px;">
            Đăng ký Adeptlink miễn phí →
          </a>
        </div>
        <p style="margin:20px 0 0;font-size:12px;color:#8a9e8a;text-align:center;">
          © Adeptlink · <a href="https://compliance.adept-link.com" style="color:#3d7a52;">compliance.adept-link.com</a>
        </p>
      </div>
    </div>
    """
    status2, body2 = send_email(
        email, name,
        "Adeptlink đã nhận yêu cầu tư vấn của bạn",
        confirm_html
    )
    if status2 not in (200, 201):
        log.warning("Confirmation email to customer FAILED: status=%s body=%s", status2, body2[:200])
        # Still return ok — internal notify already sent successfully

    log.info("Contact form processed OK: company=%s email=%s", company, email)
    return jsonify({"ok": True})


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and os.path.exists(path):
        return send_from_directory(".", path)
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
