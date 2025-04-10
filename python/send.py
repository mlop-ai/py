import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(config, from_address, to_address, subject, body, html=False):
    email = MIMEMultipart()
    email["From"] = from_address
    email["To"] = to_address
    email["Subject"] = subject
    email.attach(MIMEText(body, "html" if html else "plain"))

    try:
        with smtplib.SMTP(config["server"], config["port"]) as server:
            server.starttls()
            server.login(config["username"], config["password"])
            server.sendmail(from_address, to_address, email.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")
