from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, PasswordField, TextAreaField, SelectField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length
from wtforms import BooleanField

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role = SelectField('Role', choices=[('user', 'User'), ('admin', 'Admin')])
    submit = SubmitField('Create User')

class TestForm(FlaskForm):
    name = StringField('Test Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    time_limit = IntegerField('Time Limit (minutes)', default=0)
    submit = SubmitField('Save Test')

class QuestionForm(FlaskForm):
    type = SelectField('Type', choices=[('mcq', 'Multiple Choice'), ('tf', 'True/False'), ('flashcard', 'Flashcard')], validators=[DataRequired()])
    text = TextAreaField('Question Text', validators=[DataRequired()])
    options = TextAreaField('Options (JSON array or dict, e.g. ["A", "B", "C"] or {"back": "Answer"})')
    correct = StringField('Correct Answer(s) (comma-separated for multi)', validators=[DataRequired()])
    explanation = TextAreaField('Explanation')
    image = FileField('Upload Topology/Image')
    delete_image = BooleanField('Delete current image')
    submit = SubmitField('Save Question')

class ImportForm(FlaskForm):
    json_file = FileField('Upload JSON File')
    submit = SubmitField('Import')

class SimStartForm(FlaskForm):
    custom_time = IntegerField('Timer (minutes, 0 for unlimited)', default=0)
    submit = SubmitField('Start Sim')