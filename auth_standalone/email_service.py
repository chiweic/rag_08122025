"""
Email service using Resend for 佛學普化小助手
"""
import os
import logging
from typing import Optional
from datetime import datetime
import resend
from config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Email service using Resend API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.resend_api_key
        self.debug_mode = not self.api_key or settings.debug
        
        if self.api_key and not self.debug_mode:
            resend.api_key = self.api_key
            logger.info("Resend email service initialized")
        else:
            logger.info("Email service in debug mode (console output)")
    
    async def send_password_reset_email(
        self, 
        email: str, 
        token: str, 
        user_name: Optional[str] = None
    ) -> bool:
        """Send password reset email"""
        try:
            reset_url = f"{settings.frontend_url}/reset-password?token={token}"
            display_name = user_name or email
            
            if self.debug_mode:
                return self._send_console_email(email, reset_url, display_name)
            else:
                return await self._send_resend_email(email, reset_url, display_name)
                
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")
            return False
    
    def _send_console_email(self, email: str, reset_url: str, display_name: str) -> bool:
        """Send email to console (development mode)"""
        print("\n" + "="*80)
        print("🔑 PASSWORD RESET EMAIL - 佛學普化小助手")
        print("="*80)
        print(f"To: {email}")
        print(f"Name: {display_name}")
        print(f"Reset URL: {reset_url}")
        print(f"Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        print("⚠️  Development mode - No real email sent")
        print("🙏 南無阿彌陀佛")
        print("="*80 + "\n")
        return True
    
    async def _send_resend_email(self, email: str, reset_url: str, display_name: str) -> bool:
        """Send email via Resend API"""
        html_content = self._generate_html_template(reset_url, display_name)
        
        try:
            response = resend.Emails.send({
                "from": settings.email_from,
                "to": email,
                "subject": "重設您的密碼 - 佛學普化小助手",
                "html": html_content
            })
            
            logger.info(f"Password reset email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Resend API error: {e}")
            return False
    
    def _generate_html_template(self, reset_url: str, display_name: str) -> str:
        """Generate beautiful HTML email template"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>重設密碼 - 佛學普化小助手</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 20px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #8B4513 0%, #D2691E 100%); color: white; padding: 40px 20px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px; font-weight: 600;">🙏 佛學普化小助手</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">密碼重設請求</p>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px 30px;">
                    <h2 style="color: #333; margin: 0 0 20px 0; font-size: 20px;">親愛的 {display_name}，</h2>
                    
                    <p style="color: #555; line-height: 1.6; margin: 0 0 25px 0; font-size: 16px;">
                        我們收到了您的密碼重設請求。請點擊下方按鈕來設定新的密碼：
                    </p>
                    
                    <!-- Reset Button -->
                    <div style="text-align: center; margin: 35px 0;">
                        <a href="{reset_url}" 
                           style="display: inline-block; 
                                  padding: 15px 40px; 
                                  background: linear-gradient(135deg, #8B4513 0%, #D2691E 100%); 
                                  color: white; 
                                  text-decoration: none; 
                                  border-radius: 30px; 
                                  font-weight: 600; 
                                  font-size: 16px;
                                  box-shadow: 0 4px 15px rgba(139, 69, 19, 0.3);
                                  transition: all 0.3s ease;">
                            🔑 重設我的密碼
                        </a>
                    </div>
                    
                    <!-- Alternative Link -->
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #8B4513; margin: 25px 0;">
                        <p style="margin: 0 0 10px 0; color: #666; font-size: 14px; font-weight: 500;">
                            如果按鈕無法點擊，請複製以下連結到瀏覽器：
                        </p>
                        <code style="background: #e9ecef; padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #495057; word-break: break-all; display: block;">
                            {reset_url}
                        </code>
                    </div>
                    
                    <!-- Security Notice -->
                    <div style="border: 2px solid #ffeaa7; background: #fdcb6e; padding: 15px; border-radius: 8px; margin: 25px 0;">
                        <p style="margin: 0; color: #333; font-size: 14px; line-height: 1.5;">
                            <strong>⚠️ 安全提醒：</strong><br>
                            • 此連結將在 <strong>24小時</strong> 後失效<br>
                            • 如果您沒有請求重設密碼，請忽略此郵件<br>
                            • 請勿將此連結分享給任何人
                        </p>
                    </div>
                    
                    <p style="color: #777; font-size: 14px; line-height: 1.5; margin: 25px 0 0 0;">
                        如有任何問題，請隨時聯繫我們的技術支援團隊。<br>
                        願您在修行路上平安喜樂，智慧增長。
                    </p>
                </div>
                
                <!-- Footer -->
                <div style="background: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e9ecef;">
                    <p style="margin: 0 0 10px 0; color: #8B4513; font-size: 16px; font-weight: 500;">
                        🙏 南無阿彌陀佛
                    </p>
                    <p style="margin: 0; color: #999; font-size: 12px;">
                        此郵件由佛學普化小助手系統自動發送，請勿直接回覆
                    </p>
                    <p style="margin: 5px 0 0 0; color: #999; font-size: 12px;">
                        © {datetime.now().year} 佛學普化小助手 - 傳播智慧，利益眾生
                    </p>
                </div>
                
            </div>
        </body>
        </html>
        """
    
    async def send_welcome_email(self, email: str, user_name: str) -> bool:
        """Send welcome email to new users"""
        try:
            if self.debug_mode:
                print(f"\n🎉 WELCOME EMAIL to {user_name} ({email})")
                print("歡迎加入佛學普化小助手！🙏")
                return True
            
            # Implementation for welcome email via Resend
            welcome_html = self._generate_welcome_template(user_name)
            
            response = resend.Emails.send({
                "from": settings.email_from,
                "to": email,
                "subject": "歡迎加入佛學普化小助手！🙏",
                "html": welcome_html
            })
            
            logger.info(f"Welcome email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
            return False
    
    def _generate_welcome_template(self, user_name: str) -> str:
        """Generate welcome email template"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <title>歡迎加入 - 佛學普化小助手</title>
        </head>
        <body style="font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #8B4513 0%, #D2691E 100%); color: white; padding: 40px 20px; text-align: center;">
                    <h1 style="margin: 0;">🙏 歡迎加入佛學普化小助手</h1>
                </div>
                <div style="padding: 40px 30px; text-align: center;">
                    <h2 style="color: #8B4513;">歡迎 {user_name}！</h2>
                    <p style="color: #555; line-height: 1.6;">
                        感謝您加入佛學普化小助手的大家庭。<br>
                        在這裡，您可以：
                    </p>
                    <ul style="text-align: left; color: #555; line-height: 1.8;">
                        <li>📖 探索豐富的佛學經典與教法</li>
                        <li>🎧 聆聽高僧大德的開示音檔</li>
                        <li>🏮 參與各種佛學活動與法會</li>
                        <li>📿 記錄您的修行歷程</li>
                        <li>🙏 與同修道友交流心得</li>
                    </ul>
                    <p style="color: #8B4513; font-weight: 500; margin-top: 30px;">
                        願您在此獲得法喜，智慧增長！
                    </p>
                </div>
                <div style="background: #f8f9fa; padding: 20px; text-align: center;">
                    <p style="margin: 0; color: #999; font-size: 14px;">南無阿彌陀佛 🙏</p>
                </div>
            </div>
        </body>
        </html>
        """

# Global email service instance
email_service = EmailService()