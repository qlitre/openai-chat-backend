from djoser.email import PasswordResetEmail as DjoserPasswordResetEmail
from djoser.email import ActivationEmail as DjoserActivationEmail


class ActivationEmail(DjoserActivationEmail):
    """アクティベーションメールの上書き"""
    template_name = "account/activation_email.html"


class PasswordResetEmail(DjoserPasswordResetEmail):
    """パスワードリセットメールの上書き"""
    template_name = "account/reset_password_email.html"
