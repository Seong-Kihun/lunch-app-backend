import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional
from config.auth_config import AuthConfig

class EmailService:
    """이메일 발송 서비스"""
    
    def __init__(self):
        self.smtp_server = AuthConfig.MAIL_SERVER
        self.smtp_port = AuthConfig.MAIL_PORT
        self.username = AuthConfig.MAIL_USERNAME
        self.password = AuthConfig.MAIL_PASSWORD
        self.use_tls = AuthConfig.MAIL_USE_TLS
    
    def send_magic_link_email(self, email: str, token: str, nickname: Optional[str] = None) -> bool:
        """매직링크 이메일 발송"""
        try:
            # 이메일 내용 구성
            subject = f'[밥플떼기] 시작하기'
            
            # HTML 이메일 템플릿
            html_content = self._create_magic_link_html(email, token, nickname)
            
            # 텍스트 이메일 템플릿
            text_content = self._create_magic_link_text(email, token, nickname)
            
            # 이메일 메시지 생성
            msg = MIMEMultipart('alternative')
            msg['From'] = f'밥플떼기 <{self.username}>'
            msg['To'] = email
            msg['Subject'] = subject
            
            # HTML과 텍스트 버전 모두 첨부
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 이메일 발송
            return self._send_email(msg)
            
        except Exception as e:
            print(f"이메일 발송 실패: {str(e)}")
            return False
    
    def _create_magic_link_html(self, email: str, token: str, nickname: Optional[str] = None) -> str:
        """HTML 이메일 템플릿 생성"""
        magic_link_url = AuthConfig.get_magic_link_url(token)
        
        # 닉네임이 있으면 환영 메시지, 없으면 기본 메시지
        greeting = f"안녕하세요, {nickname}님!" if nickname else "안녕하세요!"
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>밥플떼기 시작하기</title>
            <style>
                body {{
                    font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .container {{
                    background-color: #ffffff;
                    border-radius: 12px;
                    padding: 40px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .logo {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #3B82F6;
                    margin-bottom: 10px;
                }}
                .subtitle {{
                    color: #64748B;
                    font-size: 16px;
                }}
                .content {{
                    margin-bottom: 30px;
                }}
                .button {{
                    display: inline-block;
                    background-color: #3B82F6;
                    color: white;
                    padding: 16px 32px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 16px;
                    text-align: center;
                    margin: 20px 0;
                    transition: background-color 0.3s;
                }}
                .button:hover {{
                    background-color: #2563EB;
                }}
                .warning {{
                    background-color: #FEF3C7;
                    border: 1px solid #F59E0B;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 20px 0;
                    font-size: 14px;
                    color: #92400E;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #E2E8F0;
                    color: #64748B;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">🍽️ 밥플떼기</div>
                    <div class="subtitle">동료와 즐거운 점심</div>
                </div>
                
                <div class="content">
                    <p>{greeting}</p>
                    <p><strong>밥플떼기</strong>를 시작하려면 아래 버튼을 클릭해주세요.</p>
                    
                    <div style="text-align: center;">
                        <a href="{magic_link_url}" class="button">
                            로그인 및 시작하기
                        </a>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ 주의사항:</strong><br>
                        • 이 링크는 10분 동안만 유효합니다<br>
                        • 한 번만 사용할 수 있습니다<br>
                        • 직접 요청한 것이 아니라면 이 메일을 무시해주세요
                    </div>
                </div>
                
                <div class="footer">
                    <p>이 메일은 {email}로 발송되었습니다.</p>
                    <p>© 2024 밥플떼기. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def _create_magic_link_text(self, email: str, token: str, nickname: Optional[str] = None) -> str:
        """텍스트 이메일 템플릿 생성"""
        magic_link_url = AuthConfig.get_magic_link_url(token)
        
        greeting = f"안녕하세요, {nickname}님!" if nickname else "안녕하세요!"
        
        text_template = f"""
{greeting}

밥플떼기'를 시작하려면 아래 링크를 클릭해주세요:

{magic_link_url}

⚠️ 주의사항:
• 이 링크는 10분 동안만 유효합니다
• 한 번만 사용할 수 있습니다
• 직접 요청한 것이 아니라면 이 메일을 무시해주세요

이 메일은 {email}로 발송되었습니다.

© 2024 밥플떼기. All rights reserved.
        """
        
        return text_template.strip()
    
    def _send_email(self, msg: MIMEMultipart) -> bool:
        """이메일 발송 실행"""
        try:
            # SMTP 서버 연결
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            # 로그인
            server.login(self.username, self.password)
            
            # 이메일 발송
            server.send_message(msg)
            
            # 연결 종료
            server.quit()
            
            print(f"이메일 발송 성공: {msg['To']}")
            return True
            
        except Exception as e:
            print(f"이메일 발송 실패: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """SMTP 연결 테스트"""
        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            server.login(self.username, self.password)
            server.quit()
            
            print("SMTP 연결 테스트 성공")
            return True
            
        except Exception as e:
            print(f"SMTP 연결 테스트 실패: {str(e)}")
            return False

# 싱글톤 인스턴스
email_service = EmailService()
