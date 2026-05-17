from pydantic import BaseModel, EmailStr, field_validator
from typing import Annotated
from pydantic import StringConstraints

Name        = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
Password    = Annotated[str, StringConstraints(min_length=6, max_length=128)]
OTPCode     = Annotated[str, StringConstraints(min_length=6, max_length=6, pattern=r"^\d{6}$")]
PhoneNumber = Annotated[str, StringConstraints(min_length=7, max_length=20, strip_whitespace=True)]


class UserCreate(BaseModel):
    email:        EmailStr
    password:     Password
    full_name:    Name
    phone_number: PhoneNumber

class UserLogin(BaseModel):
    email:    EmailStr
    password: Password

class Token(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str

class RefreshRequest(BaseModel):
    refresh_token: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp:   OTPCode

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyResetOTP(BaseModel):
    email: EmailStr
    otp:   OTPCode

class ResetPassword(BaseModel):
    email:        EmailStr
    otp:          OTPCode
    new_password: Password
