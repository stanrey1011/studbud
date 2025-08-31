from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, PasswordField, TextAreaField, SelectField, SubmitField, IntegerField, SelectMultipleField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange

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
    time_limit = IntegerField('Time Limit (minutes)', default=0, validators=[NumberRange(min=0)])
    num_questions = IntegerField('Number of Questions', validators=[DataRequired(), NumberRange(min=1)], default=1)
    submit = SubmitField('Save Test')

class QuestionForm(FlaskForm):
    type = SelectField('Type', choices=[('mcq', 'Multiple Choice'), ('mrq', 'Multiple Response'), ('tf', 'True/False'), ('flashcard', 'Flashcard')], validators=[DataRequired()])
    text = TextAreaField('Question Text', validators=[DataRequired()])
    options = TextAreaField('Options (JSON array or dict, e.g. ["A. Option", "B. Option"] or {"back": "Answer"})')
    correct = SelectMultipleField('Correct Answer(s)', choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('true', 'True'), ('false', 'False')], validators=[DataRequired()])
    explanation = TextAreaField('Explanation')
    image = FileField('Upload Topology/Image')
    delete_image = BooleanField('Delete current image')
    submit = SubmitField('Save Question')

class ImportForm(FlaskForm):
    json_file = FileField('Upload JSON File')
    overwrite = BooleanField('Overwrite Existing Tests')  # Added
    submit = SubmitField('Import')

class SimStartForm(FlaskForm):
    custom_time = IntegerField('Timer (minutes, 0 for unlimited)', default=0, validators=[NumberRange(min=0)])
    submit = SubmitField('Start Sim')