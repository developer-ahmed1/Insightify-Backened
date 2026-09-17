"""
Authentication schemas — RFC §2 Auth & Onboarding APIs.
"""
from typing import Optional
from pydantic import EmailStr, Field
from app.schemas.common import BaseSchema


# ---------------------------------------------------------------------------
# §2.1 Register
# ---------------------------------------------------------------------------
class RegisterRequest(BaseSchema):
    """POST /api/v1/auth/register"""
    fullName: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)


class AuthUserResponse(BaseSchema):
    """User object returned in auth responses."""
    id: str
    name: Optional[str] = None
    email: str
    username: Optional[str] = None
    avatar: Optional[str] = None
    createdAt: Optional[str] = None


class TokensResponse(BaseSchema):
    """Token envelope per RFC §2."""
    accessToken: str
    refreshToken: str
    expiresIn: int


class AuthResponse(BaseSchema):
    """Full auth response with user + tokens."""
    user: AuthUserResponse
    tokens: TokensResponse


# ---------------------------------------------------------------------------
# §2.2 Login
# ---------------------------------------------------------------------------
class LoginRequest(BaseSchema):
    """POST /api/v1/auth/login"""
    email: EmailStr
    password: str


# ---------------------------------------------------------------------------
# §2.3 Google OAuth
# ---------------------------------------------------------------------------
class GoogleAuthRequest(BaseSchema):
    """POST /api/v1/auth/google"""
    idToken: str


# ---------------------------------------------------------------------------
# §2.4 Forgot Password
# ---------------------------------------------------------------------------
class ForgotPasswordRequest(BaseSchema):
    """POST /api/v1/auth/forgot-password"""
    email: EmailStr


class ForgotPasswordResponse(BaseSchema):
    """Response for forgot password."""
    success: bool = True
    message: str = "Password reset instructions have been sent to your email."


# ---------------------------------------------------------------------------
# §2.5 Reset Password
# ---------------------------------------------------------------------------
class ResetPasswordRequest(BaseSchema):
    """POST /api/v1/auth/reset-password"""
    resetToken: str
    newPassword: str = Field(..., min_length=8)


class ResetPasswordResponse(BaseSchema):
    """Response for reset password."""
    success: bool = True
    message: str = "Password has been reset successfully."


# ---------------------------------------------------------------------------
# §2.6 Logout
# ---------------------------------------------------------------------------
class LogoutRequest(BaseSchema):
    """POST /api/v1/auth/logout"""
    refreshToken: Optional[str] = None


# ---------------------------------------------------------------------------
# §2.7 Refresh Token
# ---------------------------------------------------------------------------
class RefreshTokenRequest(BaseSchema):
    """POST /api/v1/auth/refresh"""
    refreshToken: str


class RefreshTokenResponse(BaseSchema):
    """Response for refresh token."""
    accessToken: str
    expiresIn: int
