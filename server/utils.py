import asyncio
import datetime
import os
import shutil
import tomllib
from functools import wraps
from typing import Any

for config_file in ["config.toml", "config.template.toml"]:
    if os.path.exists(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/" + config_file
    ):
        break
else:
    raise FileNotFoundError("No config file found.")

with open(config_file, "rb") as f:
    config_data: dict[str, Any] = tomllib.load(f)


def get_config(key: str, default: Any = "") -> Any:
    return config_data.get(key) or os.getenv(key, default)


def log(message: str) -> None:
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def retry_async(times: int, delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == times - 1:
                        raise e
                    log(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying...")
                    await asyncio.sleep(delay)
        return wrapper
    return decorator


CONTRIBUTOR_QUOTA_DEFAULT = get_config("CONTRIBUTOR_QUOTA_DEFAULT")
DB_PATH = get_config("DB_PATH", "data/db.sqlite")
DB_CACHE_PATH = get_config("DB_CACHE_PATH", "data/cache.sqlite")
EMAIL_SENDER = get_config("EMAIL_SENDER", "")
EMAIL_PASSWORD = get_config("EMAIL_PASSWORD", "")
EMAIL_SMTP_SERVER_PORT = get_config("EMAIL_SMTP_SERVER_PORT", None)


async def schedule_daily_backup() -> None:
    while True:
        try:
            now = datetime.datetime.now()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            delay = (target - now).total_seconds()
            log(f"Next database backup scheduled in {(target-now).total_seconds() / 3600:.1f} hours at {target.strftime('%Y-%m-%d %H:%M')}")

            await asyncio.sleep(delay)
            
            # Copy database file
            backup_dir = os.path.dirname(DB_PATH) + "/backups"
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"db_{timestamp}.sqlite"
            backup_path = backup_dir + "/" + backup_filename
            
            await asyncio.to_thread(shutil.copy, DB_PATH, backup_path)
            log(f"Database backup created at {backup_path}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log(f"Error in backup schedule loop: {e}")
            await asyncio.sleep(60)


async def send_email(to_email: str, subject: str, body: str, headers: dict[str, str] | None = None, user_obj: dict | None = None) -> bool:
    """Sends an email asynchronously using the SMTP configuration from config.toml."""

    if not to_email:
        return False

    if user_obj:
        host_public = os.getenv("HOST_PUBLIC") or ""
        host_url = host_public.rstrip('/')
        unsubscribe_link = f"{host_url}/api/unsubscribe?user={user_obj['username']}&token={user_obj['magic_token']}"
        body += f"\n\n---\nTo unsubscribe from these updates, click here:\n{unsubscribe_link}\n"
        if headers is None:
            headers = {}
        headers["List-Unsubscribe"] = f"<{unsubscribe_link}>"
        
    def _send() -> bool:
        import smtplib
        from email.header import Header
        from email.mime.text import MIMEText
        from email.utils import formatdate, make_msgid
        log(f"Sending email to: {to_email}\nSubject: {subject}\n\n{body}\n{'-'*40}\n")

        if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_SMTP_SERVER_PORT:
            log("Email configuration is missing (EMAIL_SENDER, EMAIL_PASSWORD, or EMAIL_SMTP_SERVER_PORT).")
            return False

        # Parse SMTP host and port
        try:
            host, port_str = EMAIL_SMTP_SERVER_PORT.split(":")
            port = int(port_str)
        except (ValueError, AttributeError):
            log("Invalid email server configuration (EMAIL_SMTP_SERVER_PORT).")
            return False
        
        # Create message
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8") # type: ignore
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email
        
        if headers:
            for k, v in headers.items():
                msg[k] = v

        # Extract domain for Message-ID
        domain = EMAIL_SENDER.split("@")[-1] if "@" in EMAIL_SENDER else "localhost"
        msg["Message-ID"] = make_msgid(domain=domain)
        msg["Date"] = formatdate(localtime=True)

        try:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, [to_email], msg.as_string())
            server.quit()
            return True
        except Exception as e:
            log(f"Failed to send email: {e}")
            return False

    return await asyncio.to_thread(_send)

async def schedule_daily_notifications() -> None:
    from .db import get_user_by_id, get_users, save_user
    while True:
        try:
            now = datetime.datetime.now()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            delay = (target - now).total_seconds()
            log(f"Next daily notifications scheduled in {(target-now).total_seconds() / 3600:.1f} hours at {target.strftime('%Y-%m-%d %H:%M')}")
            await asyncio.sleep(delay)
            
            host_url = (os.getenv("HOST_PUBLIC") or "").rstrip("/")

            users = await get_users()
            emails_sent = 0
            for u in users:
                if not u["notification_consent"]:
                    continue
                unread = [n for n in u["notifications"] if n["status"] == "unread"]
                if not unread:
                    continue
                
                accepted = [n for n in unread if n["type"] == "accepted"]
                returned = [n for n in unread if n["type"] in ("returned", "commented")]

                email_body = f"Hello {u['name']},\n\nYou have {len(unread)} unread notifications regarding your submissions on the Last Translation Benchmark:\n\n"
                
                if accepted:
                    email_body += "Accepted submissions:\n"
                    for n in accepted:
                        email_body += f"- {n['type']} ({n['created']}) {n['content']}\n"
                    email_body += "\n"
                    
                if returned:
                    email_body += "Returned/commented submissions, please update and resubmit:\n"
                    for n in returned:
                        email_body += f"- {n['type']} ({n['created']}) {n['content']}\n"
                    email_body += "\n"
                
                email_body += f"View the submissions here: {host_url}\n"
                email_body += "\nBest regards, the LTB Team"
                
                if await send_email(
                    to_email=u["email"],
                    subject="Last Translation Benchmark - Notifications",
                    body=email_body,
                    user_obj=u
                ):
                    emails_sent += 1
                    fresh_u = await get_user_by_id(u["id"])
                    if not fresh_u:
                        continue
                    sent_dates = {x["created"] for x in unread}
                    for n in fresh_u["notifications"]:
                        if n["created"] in sent_dates and n["status"] == "unread":
                            n["status"] = "emailed"
                    await save_user(fresh_u)
            log(f"Daily notifications sent to {emails_sent} users.")
                    
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log(f"Error in notifications schedule loop: {e}")
            await asyncio.sleep(60)
