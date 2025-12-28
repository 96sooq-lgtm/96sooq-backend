"""
Pydantic models for request/response validation
Models will be created module by module as needed
"""
from pydantic import BaseModel, EmailStr, constr
from typing import Optional


class UserCreate(BaseModel):
	name: str
	email: EmailStr
	# bcrypt has a 72 byte maximum; enforce a limit to avoid runtime errors
	password: constr(min_length=8, max_length=72)


class UserOut(BaseModel):
	id: Optional[str]
	name: str
	email: EmailStr


class LoginRequest(BaseModel):
	email: EmailStr
	password: constr(min_length=1, max_length=1024)


class ChangePasswordRequest(BaseModel):
	email: EmailStr
	# enforce bcrypt 72-byte max for new passwords as well
	new_password: constr(min_length=8, max_length=72)

# Category schemas
class CategoryCreate(BaseModel):
	name: str
	is_active: bool = True


class CategoryUpdate(BaseModel):
	name: Optional[str] = None
	is_active: Optional[bool] = None


class CategoryOut(BaseModel):
	id: str
	name: str
	is_active: bool
	created_at: Optional[str] = None
	updated_at: Optional[str] = None