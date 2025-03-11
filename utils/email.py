# app/utils/email.py - Email notification functions

import os
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables for email configuration
load_dotenv()

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.sendgrid.net')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME', 'apikey')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'notifications@buyitforlife-tracker.com')
EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'BuyItForLife Sale Tracker')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')


async def send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """
    Send an email using the configured SMTP server.

    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        text_content: Plain text content (optional, will use html_content if not provided)

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Create a multipart message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
        message['To'] = to_email

        # Add plain text part (required)
        if text_content is None:
            # If no text content is provided, convert HTML to plain text (very basic)
            text_content = html_content.replace('<br>', '\n').replace('</p>', '\n').replace('<li>', '- ')
            # Remove HTML tags
            import re
            text_content = re.sub(r'<[^>]*>', '', text_content)

        part1 = MIMEText(text_content, 'plain')
        message.attach(part1)

        # Add HTML part
        part2 = MIMEText(html_content, 'html')
        message.attach(part2)

        # Send the email
        await aiosmtplib.send(
            message,
            hostname=EMAIL_HOST,
            port=EMAIL_PORT,
            username=EMAIL_USERNAME,
            password=EMAIL_PASSWORD,
            use_tls=True
        )

        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False


async def send_verification_email(to_email: str, verification_token: str) -> bool:
    """Send an email verification link."""
    subject = "Verify Your Email - BuyItForLife Sale Tracker"

    verification_url = f"{FRONTEND_URL}/verify-email?token={verification_token}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">Verify Your Email Address</h2>
        <p>Thank you for signing up for BuyItForLife Sale Tracker! Please verify your email address by clicking the button below:</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_url}" style="background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">
                Verify My Email
            </a>
        </div>

        <p>If the button doesn't work, you can also copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #7f8c8d;">{verification_url}</p>

        <p>This link will expire in 24 hours.</p>

        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #7f8c8d; font-size: 12px;">
            If you didn't sign up for BuyItForLife Sale Tracker, you can safely ignore this email.
        </p>
    </div>
    """

    return await send_email(to_email, subject, html_content)


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send a password reset link."""
    subject = "Reset Your Password - BuyItForLife Sale Tracker"

    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">Reset Your Password</h2>
        <p>You requested to reset your password for BuyItForLife Sale Tracker. Click the button below to set a new password:</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">
                Reset Password
            </a>
        </div>

        <p>If the button doesn't work, you can also copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #7f8c8d;">{reset_url}</p>

        <p>This link will expire in 1 hour.</p>

        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #7f8c8d; font-size: 12px;">
            If you didn't request a password reset, you can safely ignore this email.
        </p>
    </div>
    """

    return await send_email(to_email, subject, html_content)


async def send_price_alert_email(to_email: str, item, old_price: float, new_price: float,
                                 percentage_change: float) -> bool:
    """Send a price drop alert email."""
    # Format prices with currency
    old_price_formatted = f"${old_price:.2f}"
    new_price_formatted = f"${new_price:.2f}"
    savings = old_price - new_price
    savings_formatted = f"${savings:.2f}"

    subject = f"💰 Price Drop Alert: {item.title} is now {new_price_formatted}!"

    # Determine which retailer has the price drop
    retailer_with_drop = "a retailer"
    for link in item.retailer_links:
        if link.price_dropped:
            retailer_with_drop = link.name
            break

    # Create the item URL for the frontend
    item_url = f"{FRONTEND_URL}/items/{item.id}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">Price Drop Alert! 📉</h2>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #2c3e50;">{item.title}</h3>

            <p>The price has dropped on {retailer_with_drop}!</p>

            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">Previous Price:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right; text-decoration: line-through;">{old_price_formatted}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">New Price:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right; font-weight: bold; color: #27ae60;">{new_price_formatted}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">You Save:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right; color: #27ae60;">{savings_formatted} ({percentage_change:.1f}%)</td>
                </tr>
            </table>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{item_url}" style="background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">
                    View Item Details
                </a>
            </div>
        </div>

        <p>This price was detected on {datetime.now().strftime('%B %d, %Y')}. Prices may change rapidly, so act quickly if you're interested!</p>

        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #7f8c8d; font-size: 12px;">
            You're receiving this email because you've set up price alerts for this item on BuyItForLife Sale Tracker.
            <br>
            To manage your alert preferences, <a href="{FRONTEND_URL}/account/alerts" style="color: #3498db;">visit your account settings</a>.
        </p>
    </div>
    """

    return await send_email(to_email, subject, html_content)