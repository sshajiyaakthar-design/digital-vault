from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import DateTimeField, FileField, HiddenField, PasswordField, StringField, TextAreaField
from wtforms.validators import EqualTo, InputRequired, Length, Optional


class RegisterForm(FlaskForm):
    # Avoid WTForms Email() validator to remove the hard dependency on `email_validator`.
    # We still normalize/validate minimally in the route handler.
    email = StringField("Email", validators=[InputRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8, max=72)])
    password_confirm = PasswordField(
        "Confirm Password",
        validators=[InputRequired(), EqualTo("password", message="Passwords must match.")],
    )


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[InputRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8, max=72)])


class CapsuleCreateForm(FlaskForm):
    title = StringField("Title", validators=[InputRequired(), Length(min=1, max=200)])
    message = TextAreaField("Message", validators=[Optional(), Length(max=5000)])
    unlock_local = StringField(
        "Unlock time (your local)",
        validators=[InputRequired()],
        description="Sent as datetime-local string",
    )
    client_tz_offset_minutes = HiddenField("Client timezone offset minutes", validators=[Optional()])

    # Use multiple uploads. WTForms' FileField doesn't directly support multiple in all cases,
    # so we will read files from request.files in the route.
    files = FileField("Files", validators=[Optional()])


class ShareCreateForm(FlaskForm):
    # Placeholder if we later add expiry selection. For now we only need submit.
    submit = StringField("Create share link", validators=[InputRequired()])

